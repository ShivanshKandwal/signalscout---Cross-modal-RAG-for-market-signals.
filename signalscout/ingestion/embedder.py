"""
Embedding pipeline - wraps BAAI/bge-m3 via sentence-transformers.
Handles batching, device detection, and pgvector INSERT.
HF Task: Feature Extraction
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import numpy as np
from signalscout.config import settings
from signalscout.models import Chunk
from signalscout.models.database import ChunkORM

logger = logging.getLogger(__name__)

# Module-level singleton - loaded once, reused across all ingestion calls
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
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
    """
    Embed a list of strings with BAAI/bge-m3.
    Returns list of 1024-dim float vectors.
    Automatically batches to settings.embedding_batch_size.
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True,   # cosine similarity → dot product
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """Embed a single query string for retrieval."""
    # BGE-M3 benefits from the instruction prefix for retrieval queries
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    return embed_texts([prefixed])[0]


async def store_chunks(chunks: List[Chunk], db: AsyncSession) -> int:
    """
    Embed chunks in batch and persist to pgvector.
    Returns number of successfully stored chunks.
    """
    if not chunks:
        return 0

    texts = [c.content for c in chunks]
    logger.info(f"Embedding {len(texts)} chunks...")

    # Run CPU-bound embedding in thread pool to not block event loop
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
