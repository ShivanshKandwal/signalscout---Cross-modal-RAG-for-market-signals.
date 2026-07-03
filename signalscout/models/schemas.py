"""
Shared Pydantic domain models used across ingestion, agents, API, and eval.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class Modality(str, Enum):
    AUDIO = "audio"
    DOCUMENT = "document"
    IMAGE = "image"
    NEWS = "news"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    BEARISH = "bearish"


class NLILabel(str, Enum):
    ENTAILMENT = "entailment"
    NEUTRAL = "neutral"
    CONTRADICTION = "contradiction"


class ContradictionSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Core Storage Models ────────────────────────────────────────────────────────

class ChunkMetadata(BaseModel):
    """Metadata stored alongside each vector chunk in pgvector."""
    ticker: str
    modality: Modality
    source_url: Optional[str] = None
    filed_date: Optional[date] = None
    section: Optional[str] = None          # e.g. "Risk Factors", "MD&A"
    speaker: Optional[str] = None          # for audio chunks
    call_date: Optional[date] = None       # for audio chunks
    chart_period: Optional[str] = None     # for image chunks, e.g. "1y"
    sentiment_tag: Optional[Sentiment] = None   # for news chunks
    published_at: Optional[datetime] = None     # for news chunks
    chunk_index: int = 0
    extra: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """A single embedded chunk stored in pgvector."""
    id: UUID = Field(default_factory=uuid4)
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None    # 1024-dim BAAI/bge-m3
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Retrieval Models ──────────────────────────────────────────────────────────

class RetrievedChunk(BaseModel):
    """A chunk returned by the retrieval agent, with relevance scores."""
    chunk: Chunk
    dense_score: float = 0.0       # cosine similarity
    sparse_score: float = 0.0      # BM25 score (normalised)
    rrf_score: float = 0.0         # Reciprocal Rank Fusion score
    reranker_score: float = 0.0    # CrossEncoder score


# ── Citation Models ───────────────────────────────────────────────────────────

class Citation(BaseModel):
    """A source citation linking a claim in the brief to a specific chunk."""
    id: UUID = Field(default_factory=uuid4)
    claim: str                     # the exact sentence in the brief
    chunk_id: UUID                 # the source chunk
    chunk_excerpt: str             # the quoted passage from the chunk
    modality: Modality
    ticker: str
    source_url: Optional[str] = None
    filed_date: Optional[date] = None
    confidence: float = 1.0        # 0–1, from reranker score


# ── Contradiction Models ───────────────────────────────────────────────────────

class Contradiction(BaseModel):
    """A detected semantic contradiction between audio and document evidence."""
    id: UUID = Field(default_factory=uuid4)
    audio_chunk_id: UUID
    audio_claim: str
    document_chunk_id: UUID
    document_claim: str
    nli_label: NLILabel
    nli_score: float               # 0–1 confidence
    severity: ContradictionSeverity
    explanation: Optional[str] = None


# ── Investment Brief ──────────────────────────────────────────────────────────

class ConfidenceScores(BaseModel):
    """RAGAS-style quality scores for the generated brief."""
    faithfulness: float = 0.0          # claims supported by context
    answer_relevancy: float = 0.0      # brief addresses the query
    context_recall: float = 0.0        # retrieved relevant chunks
    context_precision: float = 0.0     # retrieved chunks were relevant
    overall: float = 0.0


class InvestmentBrief(BaseModel):
    """The final structured output from the agent graph."""
    id: UUID = Field(default_factory=uuid4)
    query: str
    ticker: str
    brief_markdown: str                     # rendered markdown brief
    summary: str                            # 2–3 sentence executive summary
    sentiment: Sentiment = Sentiment.NEUTRAL
    citations: List[Citation] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)
    modalities_used: List[Modality] = Field(default_factory=list)
    num_chunks_retrieved: int = 0
    agent_hops: int = 0
    latency_ms: float = 0.0
    token_cost_usd: float = 0.0
    total_tokens: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Eval Models ───────────────────────────────────────────────────────────────

class GoldenSample(BaseModel):
    """One entry in the 50-sample golden eval dataset."""
    id: UUID = Field(default_factory=uuid4)
    question: str
    ground_truth: str
    source_chunk_id: Optional[UUID] = None
    ticker: str
    modality: Modality
    section: Optional[str] = None


class EvalRun(BaseModel):
    """Stores RAGAS metrics for one evaluation run."""
    id: UUID = Field(default_factory=uuid4)
    run_timestamp: datetime = Field(default_factory=datetime.utcnow)
    git_sha: Optional[str] = None
    dataset_size: int = 0
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_recall: float = 0.0
    context_precision: float = 0.0
    notes: Optional[str] = None


# ── API Request/Response ──────────────────────────────────────────────────────

class BriefRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=500)
    ticker: str = Field(..., min_length=1, max_length=10)
    preferred_modalities: Optional[List[Modality]] = None   # filter retrieval
    stream: bool = True


class BriefResponse(BaseModel):
    brief_id: UUID
    status: str = "complete"
    brief: InvestmentBrief


class TickerInfo(BaseModel):
    ticker: str
    chunk_count: int
    modalities: List[Modality]
    last_ingested: Optional[datetime] = None
