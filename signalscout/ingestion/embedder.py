"""
Embedding pipeline - wraps BAAI/bge-m3 via sentence-transformers.
Handles batching, device detection, and pgvector INSERT.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from signalscout.config import settings
from signalscout.models import Chunk
from signalscout.models.database import ChunkORM

logger = logging.getLogger(__name__)

_model: Optional["SentenceTransformer"] = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {settings.hf_embedding_model}")
        _model = SentenceTransformer(
            settings.hf_embedding_model,
            token=settings.hf_token or None,
        )
        logger.info("Embedding model loaded.")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    import os
    import numpy as np
    from huggingface_hub import InferenceClient

    hf_token = settings.hf_token.strip()
    app_env = getattr(settings, "app_env", os.environ.get("APP_ENV", "development")).lower()

    if hf_token and not hf_token.startswith("your_"):
        for attempt in range(3):
            try:
                logger.info(f"HF InferenceClient attempt {attempt + 1}/3...")
                client = InferenceClient(
                    provider="hf-inference",
                    api_key=hf_token,
                )
                result = client.feature_extraction(
                    texts,
                    model=settings.hf_embedding_model,
                )
                arr = np.array(result)
                if arr.ndim == 3:
                    arr = arr.mean(axis=1)
                logger.info(f"HF InferenceClient succeeded. Shape: {arr.shape}")
                return arr.tolist()

            except Exception as e:
                logger.error(f"HF attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    import time
                    time.sleep(10 * (attempt + 1))
                else:
                    if app_env == "production":
                        raise RuntimeError(
                            "HF Inference unavailable after 3 attempts."
                        ) from e
                    logger.warning("Falling back to local SentenceTransformer...")

    # ── LOCAL DEV FALLBACK ─────────────────────────────────────────────
    # Everything below this line never executes on Render in production
    # because either:
    # (a) HF API succeeded and we already returned above, or
    # (b) HF API failed in production and we already raised above
    #
    # On local dev: HF token missing/failing → falls through to here
    if app_env == "production":
        raise RuntimeError("HF API failed in production — no local fallback.")

    try:
        from sentence_transformers import SentenceTransformer  # lazy import — never loads torch on Render
    except ImportError:
        raise RuntimeError("sentence_transformers not installed and HF API unavailable.")

    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    return embed_texts([prefixed])[0]


async def store_chunks(chunks: List[Chunk], db: AsyncSession) -> int:
    if not chunks:
        return 0

    texts = [c.content for c in chunks]
    logger.info(f"Embedding {len(texts)} chunks...")

    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(None, embed_texts, texts)

    orm_objects = []
    for chunk, emb in zip(chunks, embeddings):
        orm = ChunkORM(
            id=chunk.id,
            ticker=chunk.metadata.ticker,
            modality=chunk.metadata.modality.value,
            source_url=chunk.metadata.source_url,
            filed_date=chunk.metadata.filed_date,
            content=chunk.content,
            embedding=emb,
            metadata_=chunk.metadata.model_dump(mode="json"),
        )
        orm_objects.append(orm)

    db.add_all(orm_objects)
    await db.commit()
    logger.info(f"Stored {len(orm_objects)} chunks in pgvector.")
    return len(orm_objects)