"""
Hybrid retrieval: BM25 (sparse) + pgvector dense search → RRF fusion → CrossEncoder re-rank.
HF Task: Sentence Similarity (CrossEncoder re-ranking)
"""
from __future__ import annotations

import logging
import math
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from signalscout.config import settings
from signalscout.ingestion.embedder import embed_query
from signalscout.models import Chunk, ChunkMetadata, Modality, RetrievedChunk
from signalscout.models.database import ChunkORM

logger = logging.getLogger(__name__)

BM25_INDEX_DIR = Path("data/bm25_indexes")
BM25_INDEX_DIR.mkdir(parents=True, exist_ok=True)

_reranker: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info(f"Loading re-ranker: {settings.hf_reranker_model}")
        _reranker = CrossEncoder(
            settings.hf_reranker_model,
            token=settings.hf_token or None,
        )
    return _reranker


# ── BM25 Index Management ─────────────────────────────────────────────────────

class BM25Index:
    """Serializable BM25 index for a single ticker."""

    def __init__(self, ticker: str, modality: Optional[str] = None):
        self.ticker = ticker
        self.modality = modality
        self.corpus: List[str] = []
        self.chunk_ids: List[UUID] = []
        self._bm25: Optional[BM25Okapi] = None

    def build(self, chunks: List[Tuple[UUID, str]]) -> None:
        """Build the BM25 index from (chunk_id, content) tuples."""
        if not chunks:
            logger.warning(f"[BM25] No chunks provided to build index for {self.ticker}")
            return
        self.chunk_ids = [c[0] for c in chunks]
        self.corpus = [c[1] for c in chunks]
        tokenized = [doc.lower().split() for doc in self.corpus]
        self._bm25 = BM25Okapi(tokenized)
        logger.info(f"[BM25] Built index for {self.ticker}: {len(self.corpus)} docs")

    def search(self, query: str, top_k: int = 20) -> List[Tuple[UUID, float]]:
        """Returns list of (chunk_id, normalized_bm25_score)."""
        if not self._bm25:
            return []
        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)
        # Normalize scores to 0–1
        max_score = max(scores) if max(scores) > 0 else 1.0
        normalized = scores / max_score
        top_indices = np.argsort(normalized)[::-1][:top_k]
        return [(self.chunk_ids[i], float(normalized[i])) for i in top_indices]

    def save(self) -> None:
        path = BM25_INDEX_DIR / f"{self.ticker}.pkl"
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"[BM25] Saved index to {path}")

    @classmethod
    def load(cls, ticker: str) -> Optional["BM25Index"]:
        path = BM25_INDEX_DIR / f"{ticker}.pkl"
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return pickle.load(f)


async def build_bm25_index(ticker: str, db: AsyncSession) -> BM25Index:
    """Build and persist a BM25 index for a ticker from the DB."""
    stmt = select(ChunkORM.id, ChunkORM.content).where(
        ChunkORM.ticker == ticker.upper()
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    index = BM25Index(ticker)
    index.build([(row.id, row.content) for row in rows])
    index.save()
    return index


# ── Dense Retrieval (pgvector) ────────────────────────────────────────────────

async def dense_search(
    query_embedding: List[float],
    ticker: str,
    db: AsyncSession,
    top_k: int = 20,
    modality_filter: Optional[List[str]] = None,
) -> List[Tuple[UUID, float]]:
    """
    pgvector cosine similarity search.
    Returns (chunk_id, cosine_similarity) sorted descending.
    """
    emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    if modality_filter:
        modality_in = ", ".join(f"'{m}'" for m in modality_filter)
        where_clause = f"WHERE ticker = '{ticker.upper()}' AND modality IN ({modality_in})"
    else:
        where_clause = f"WHERE ticker = '{ticker.upper()}'"

    sql = text(f"""
        SELECT id, 1 - (embedding <=> :emb) AS similarity
        FROM chunks
        {where_clause}
        ORDER BY embedding <=> :emb
        LIMIT :top_k
    """)

    result = await db.execute(sql, {"emb": emb_str, "top_k": top_k})
    rows = result.fetchall()
    return [(row.id, float(row.similarity)) for row in rows]


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[UUID, float]]],
    k: int = 60,
) -> List[Tuple[UUID, float]]:
    """
    RRF: merge multiple ranked lists into a single ranking.
    k=60 is the standard constant from the RRF paper.
    """
    scores: Dict[UUID, float] = {}
    for ranked in ranked_lists:
        for rank, (chunk_id, _) in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_chunks


# ── CrossEncoder Re-ranking ───────────────────────────────────────────────────

async def rerank_chunks(
    query: str,
    chunks: List[RetrievedChunk],
    top_k: int = 5,
) -> List[RetrievedChunk]:
    """
    CrossEncoder re-ranking of candidate chunks.
    HF Task: Sentence Similarity
    """
    if not chunks:
        return []

    reranker = _get_reranker()
    pairs = [(query, c.chunk.content) for c in chunks]
    scores = reranker.predict(pairs)

    for chunk, score in zip(chunks, scores):
        chunk.reranker_score = float(score)

    reranked = sorted(chunks, key=lambda c: c.reranker_score, reverse=True)
    return reranked[:top_k]


# ── Chunk fetcher ─────────────────────────────────────────────────────────────

async def fetch_chunks_by_ids(
    chunk_ids: List[UUID],
    db: AsyncSession,
) -> Dict[UUID, Chunk]:
    """Load full chunk objects from DB for a list of IDs."""
    stmt = select(ChunkORM).where(ChunkORM.id.in_(chunk_ids))
    result = await db.execute(stmt)
    rows = result.scalars().all()

    chunks = {}
    for row in rows:
        meta_data = row.metadata_ or {}
        meta = ChunkMetadata(
            ticker=row.ticker,
            modality=Modality(row.modality),
            source_url=row.source_url,
            filed_date=row.filed_date,
            **{k: v for k, v in meta_data.items() if k not in ("ticker", "modality", "source_url", "filed_date")},
        )
        chunks[row.id] = Chunk(
            id=row.id,
            content=row.content,
            metadata=meta,
        )
    return chunks


# ── Main Hybrid Retriever ─────────────────────────────────────────────────────

class HybridRetriever:
    """
    Combines BM25 sparse + pgvector dense retrieval with RRF fusion
    and CrossEncoder re-ranking. The backbone of the Retrieval Agent.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(
        self,
        query: str,
        ticker: str,
        top_k: int = None,
        reranker_k: int = None,
        modality_filter: Optional[List[str]] = None,
    ) -> List[RetrievedChunk]:
        top_k = top_k or settings.retrieval_top_k
        reranker_k = reranker_k or settings.reranker_top_k

        # 1. Embed query
        query_embedding = embed_query(query)

        # 2. Dense retrieval
        dense_results = await dense_search(
            query_embedding, ticker, self.db, top_k, modality_filter
        )

        # 3. Sparse BM25 retrieval
        bm25_index = BM25Index.load(ticker)
        sparse_results = bm25_index.search(query, top_k) if bm25_index else []

        # 4. RRF fusion
        fused = reciprocal_rank_fusion([dense_results, sparse_results])

        # 5. Fetch full chunk objects for top candidates
        candidate_ids = [cid for cid, _ in fused[: top_k * 2]]
        chunk_map = await fetch_chunks_by_ids(candidate_ids, self.db)

        # 6. Build RetrievedChunk objects
        dense_map = dict(dense_results)
        sparse_map = dict(sparse_results)

        retrieved = []
        for chunk_id, rrf_score in fused[:top_k]:
            if chunk_id not in chunk_map:
                continue
            rc = RetrievedChunk(
                chunk=chunk_map[chunk_id],
                dense_score=dense_map.get(chunk_id, 0.0),
                sparse_score=sparse_map.get(chunk_id, 0.0),
                rrf_score=rrf_score,
            )
            retrieved.append(rc)

        # 7. CrossEncoder re-rank
        reranked = await rerank_chunks(query, retrieved, reranker_k)
        logger.info(
            f"[RETRIEVER] {ticker}: {len(dense_results)} dense, {len(sparse_results)} sparse"
            f" → {len(reranked)} final chunks"
        )
        return reranked
