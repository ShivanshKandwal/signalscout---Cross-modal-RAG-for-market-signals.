"""
LangGraph multi-agent state definition.
All 5 agents share this typed state dictionary.
"""
from __future__ import annotations

from typing import Annotated, List, Optional
from typing_extensions import TypedDict

from signalscout.models import (
    Citation,
    Contradiction,
    ConfidenceScores,
    InvestmentBrief,
    Modality,
    RetrievedChunk,
)


class SignalScoutState(TypedDict):
    """The shared state object flowing through the LangGraph agent graph."""

    # ── Input ────────────────────────────────────────────────────────────────
    query: str
    ticker: str
    preferred_modalities: Optional[List[Modality]]

    # ── Orchestrator output ───────────────────────────────────────────────────
    parsed_intent: Optional[str]          # e.g. "risk factors", "earnings sentiment"
    time_range: Optional[str]             # e.g. "last 2 quarters"
    retrieval_instructions: Optional[str] # additional context for retrieval agent

    # ── Retrieval Agent output ────────────────────────────────────────────────
    retrieved_chunks: List[RetrievedChunk]
    retrieval_attempts: int               # tracks self-correction loops

    # ── Analysis Agent output ─────────────────────────────────────────────────
    analysis_draft: Optional[str]         # the raw synthesized brief
    audio_claims: List[str]               # claims sourced from audio chunks
    document_claims: List[str]            # claims from SEC filings

    # ── Citation Agent output ─────────────────────────────────────────────────
    citations: List[Citation]

    # ── Contradiction Agent output ────────────────────────────────────────────
    contradictions: List[Contradiction]

    # ── Critique Agent output ─────────────────────────────────────────────────
    critique_score: float                 # 0–1, overall quality
    critique_feedback: Optional[str]      # feedback for retry loop
    confidence: ConfidenceScores

    # ── Final output ──────────────────────────────────────────────────────────
    final_brief: Optional[InvestmentBrief]

    # ── Instrumentation ───────────────────────────────────────────────────────
    agent_hops: int
    total_tokens: int
    latency_ms: float
