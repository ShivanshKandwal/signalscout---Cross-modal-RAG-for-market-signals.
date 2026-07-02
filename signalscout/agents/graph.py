"""
LangGraph multi-agent graph — 5 agents:
Orchestrator → Retrieval → Analysis → Citation → Critique (→ retry loop)
"""
from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, Dict
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import HuggingFaceEndpoint
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from signalscout.agents.retriever import HybridRetriever
from signalscout.agents.state import SignalScoutState
from signalscout.config import settings
from signalscout.models import (
    Citation,
    Contradiction,
    ConfidenceScores,
    ContradictionSeverity,
    InvestmentBrief,
    Modality,
    NLILabel,
    Sentiment,
)

logger = logging.getLogger(__name__)


# ── LLM Factory ───────────────────────────────────────────────────────────────

def _get_llm():
    """
    Returns a HuggingFace Inference API LLM.
    Uses Mistral-7B-Instruct or equivalent via HF Inference API (free tier).
    Swap in ChatOpenAI if you have an OpenAI key.
    """
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    llm = HuggingFaceEndpoint(
        repo_id="mistralai/Mistral-7B-Instruct-v0.3",
        huggingfacehub_api_token=settings.hf_token,
        max_new_tokens=1024,
        temperature=0.1,
    )
    return ChatHuggingFace(llm=llm)


# ── Agent Node Functions ───────────────────────────────────────────────────────

async def orchestrator_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Parses the query to determine intent, time range, and retrieval strategy.
    Routes to the appropriate retrieval instructions.
    """
    logger.info(f"[ORCHESTRATOR] Query: {state['query'][:80]}")
    llm = _get_llm()

    system = SystemMessage(content="""You are a financial analysis orchestrator.
Given a user query about a stock ticker, extract:
1. The primary intent (e.g., risk factors, earnings sentiment, growth outlook, financial metrics)
2. Time range preference (e.g., last quarter, last year, recent)
3. Modality preference (audio = management statements, document = SEC filings, news = market news, image = chart patterns)

Respond as JSON: {"intent": "...", "time_range": "...", "preferred_modalities": [...], "retrieval_instructions": "..."}""")

    human = HumanMessage(content=f"Ticker: {state['ticker']}\nQuery: {state['query']}")

    try:
        response = await llm.ainvoke([system, human])
        import json
        parsed = json.loads(response.content.strip().strip("```json").strip("```"))
    except Exception as e:
        logger.warning(f"[ORCHESTRATOR] Parse failed: {e}. Using defaults.")
        parsed = {
            "intent": state["query"],
            "time_range": "recent",
            "preferred_modalities": ["audio", "document", "news"],
            "retrieval_instructions": state["query"],
        }

    return {
        "parsed_intent": parsed.get("intent"),
        "time_range": parsed.get("time_range"),
        "retrieval_instructions": parsed.get("retrieval_instructions", state["query"]),
        "agent_hops": state.get("agent_hops", 0) + 1,
    }


async def retrieval_node(state: SignalScoutState, db: AsyncSession) -> Dict[str, Any]:
    """
    Runs hybrid RAG retrieval using the query + orchestrator instructions.
    """
    logger.info(f"[RETRIEVAL] Retrieving for {state['ticker']}")

    retriever = HybridRetriever(db)
    modality_filter = None
    if state.get("preferred_modalities"):
        modality_filter = [m.value for m in state["preferred_modalities"]]

    query = state.get("retrieval_instructions") or state["query"]
    if state.get("critique_feedback"):
        query = f"{query}\n\nAdditional context needed: {state['critique_feedback']}"

    chunks = await retriever.retrieve(
        query=query,
        ticker=state["ticker"],
        modality_filter=modality_filter,
    )

    audio_claims = [c.chunk.content for c in chunks if c.chunk.metadata.modality == Modality.AUDIO]
    document_claims = [c.chunk.content for c in chunks if c.chunk.metadata.modality == Modality.DOCUMENT]

    return {
        "retrieved_chunks": chunks,
        "audio_claims": audio_claims,
        "document_claims": document_claims,
        "retrieval_attempts": state.get("retrieval_attempts", 0) + 1,
        "agent_hops": state.get("agent_hops", 0) + 1,
    }


async def analysis_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Synthesizes retrieved chunks into a structured investment brief draft.
    Flags semantic tensions between audio and document evidence.
    """
    logger.info(f"[ANALYSIS] Synthesizing {len(state['retrieved_chunks'])} chunks")
    llm = _get_llm()

    # Build context string
    context_parts = []
    for i, rc in enumerate(state["retrieved_chunks"][:10], 1):
        modality_label = rc.chunk.metadata.modality.value.upper()
        context_parts.append(
            f"[{i}][{modality_label}] {rc.chunk.content[:400]}"
        )
    context = "\n\n".join(context_parts)

    system = SystemMessage(content="""You are a senior financial analyst.
Synthesize the provided sources into a structured investment brief with sections:
## Executive Summary (2-3 sentences)
## Key Findings (bullet points with [source number] citations)
## Risk Factors (from SEC filings)
## Management Sentiment (from earnings calls)
## Market Signal (from news/charts)
## Conclusion

Use [1], [2] etc. to cite specific sources. Be factual and evidence-based.""")

    human = HumanMessage(content=f"""
Ticker: {state['ticker']}
Query: {state['query']}
Intent: {state.get('parsed_intent', 'general analysis')}

SOURCES:
{context}

Generate a structured investment brief with citations.""")

    response = await llm.ainvoke([system, human])
    draft = response.content

    return {
        "analysis_draft": draft,
        "agent_hops": state.get("agent_hops", 0) + 1,
    }


async def citation_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Links every [N] citation in the draft to its source chunk.
    Builds Citation objects with chunk excerpts and confidence scores.
    """
    logger.info("[CITATION] Building citation index")
    import re

    draft = state.get("analysis_draft", "")
    chunks = state.get("retrieved_chunks", [])

    # Find all [N] references in the draft
    citation_refs = re.findall(r"\[(\d+)\]", draft)
    citations = []

    for ref_str in set(citation_refs):
        ref_idx = int(ref_str) - 1
        if 0 <= ref_idx < len(chunks):
            rc = chunks[ref_idx]
            # Find the sentence in draft containing this reference
            sentences = [s for s in draft.split(".") if f"[{ref_str}]" in s]
            claim = sentences[0].strip() if sentences else f"Reference [{ref_str}]"

            citation = Citation(
                claim=claim,
                chunk_id=rc.chunk.id,
                chunk_excerpt=rc.chunk.content[:300],
                modality=rc.chunk.metadata.modality,
                ticker=rc.chunk.metadata.ticker,
                source_url=rc.chunk.metadata.source_url,
                filed_date=rc.chunk.metadata.filed_date,
                confidence=min(1.0, rc.reranker_score) if rc.reranker_score > 0 else 0.7,
            )
            citations.append(citation)

    logger.info(f"[CITATION] Built {len(citations)} citations")
    return {
        "citations": citations,
        "agent_hops": state.get("agent_hops", 0) + 1,
    }


async def contradiction_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Cross-modal contradiction detection.
    Finds top similar audio-document pairs and runs NLI on them.
    """
    logger.info("[CONTRADICTION] Running cross-modal NLI check")

    audio_claims = state.get("audio_claims", [])
    document_claims = state.get("document_claims", [])

    if not audio_claims or not document_claims:
        return {"contradictions": []}

    try:
        from sentence_transformers import SentenceTransformer
        from transformers import pipeline as hf_pipeline
        import numpy as np

        # Step 1: embed all claims
        embedder = SentenceTransformer(settings.hf_embedding_model)
        audio_embs = embedder.encode(audio_claims[:20], normalize_embeddings=True)
        doc_embs = embedder.encode(document_claims[:20], normalize_embeddings=True)

        # Step 2: find top-5 most similar cross-modal pairs
        sim_matrix = np.dot(audio_embs, doc_embs.T)
        top_pairs = []
        for i in range(sim_matrix.shape[0]):
            for j in range(sim_matrix.shape[1]):
                top_pairs.append((i, j, float(sim_matrix[i, j])))
        top_pairs.sort(key=lambda x: -x[2])
        top_pairs = top_pairs[:5]

        # Step 3: NLI on top pairs
        nli = hf_pipeline("text-classification", model=settings.hf_nli_model, device=-1)
        contradictions = []

        for audio_idx, doc_idx, _ in top_pairs:
            audio_claim = audio_claims[audio_idx]
            doc_claim = document_claims[doc_idx]

            result = nli(
                f"{audio_claim} [SEP] {doc_claim}",
                truncation=True,
                max_length=512,
            )
            label = result[0]["label"].lower()
            score = result[0]["score"]

            nli_label = NLILabel.NEUTRAL
            if "contradiction" in label:
                nli_label = NLILabel.CONTRADICTION
            elif "entail" in label:
                nli_label = NLILabel.ENTAILMENT

            if nli_label == NLILabel.CONTRADICTION and score > 0.6:
                severity = (
                    ContradictionSeverity.HIGH if score > 0.85
                    else ContradictionSeverity.MEDIUM if score > 0.70
                    else ContradictionSeverity.LOW
                )
                chunks = state.get("retrieved_chunks", [])
                audio_chunk = next((c for c in chunks if c.chunk.metadata.modality == Modality.AUDIO), None)
                doc_chunk = next((c for c in chunks if c.chunk.metadata.modality == Modality.DOCUMENT), None)

                contradictions.append(Contradiction(
                    audio_chunk_id=audio_chunk.chunk.id if audio_chunk else uuid4(),
                    audio_claim=audio_claim[:300],
                    document_chunk_id=doc_chunk.chunk.id if doc_chunk else uuid4(),
                    document_claim=doc_claim[:300],
                    nli_label=nli_label,
                    nli_score=score,
                    severity=severity,
                    explanation=f"NLI score: {score:.2f} — management statement may contradict filed disclosure",
                ))

        logger.info(f"[CONTRADICTION] Found {len(contradictions)} contradictions")
        return {"contradictions": contradictions, "agent_hops": state.get("agent_hops", 0) + 1}

    except Exception as e:
        logger.error(f"[CONTRADICTION] Failed: {e}")
        return {"contradictions": []}


async def critique_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Self-evaluation agent. Scores the draft brief for:
    - Citation coverage (are claims cited?)
    - Factual grounding (does it match retrieved context?)
    - Completeness (does it address the query?)
    Returns a critique_score and feedback for retry loop.
    """
    logger.info("[CRITIQUE] Evaluating draft")
    llm = _get_llm()

    draft = state.get("analysis_draft", "")
    citations = state.get("citations", [])
    query = state["query"]
    context = "\n".join([c.chunk_excerpt for c in citations[:5]])

    system = SystemMessage(content="""You are a quality evaluator for financial analysis reports.
Score the report on three dimensions (each 0.0–1.0):
1. citation_coverage: Are major claims backed by [N] citations?
2. factual_grounding: Do claims match the provided source excerpts?
3. query_completeness: Does the brief actually answer the original query?

Respond as JSON: {"citation_coverage": 0.X, "factual_grounding": 0.X, "query_completeness": 0.X, "overall": 0.X, "feedback": "..."}""")

    human = HumanMessage(content=f"""Query: {query}

BRIEF:
{draft[:1500]}

SOURCE EXCERPTS:
{context[:800]}

Evaluate and score.""")

    try:
        response = await llm.ainvoke([system, human])
        import json
        scores = json.loads(response.content.strip().strip("```json").strip("```"))
    except Exception:
        scores = {"overall": 0.75, "feedback": "", "citation_coverage": 0.7, "factual_grounding": 0.75, "query_completeness": 0.8}

    critique_score = float(scores.get("overall", 0.75))
    confidence = ConfidenceScores(
        faithfulness=float(scores.get("factual_grounding", 0.75)),
        answer_relevancy=float(scores.get("query_completeness", 0.75)),
        context_precision=float(scores.get("citation_coverage", 0.75)),
        overall=critique_score,
    )

    logger.info(f"[CRITIQUE] Score: {critique_score:.2f}")
    return {
        "critique_score": critique_score,
        "critique_feedback": scores.get("feedback"),
        "confidence": confidence,
        "agent_hops": state.get("agent_hops", 0) + 1,
    }


async def finalize_node(state: SignalScoutState) -> Dict[str, Any]:
    """Assembles the final InvestmentBrief from all agent outputs."""
    modalities_used = list({
        c.chunk.metadata.modality
        for c in state.get("retrieved_chunks", [])
    })

    sentiment = Sentiment.NEUTRAL
    # Infer overall sentiment from FinBERT-tagged news chunks
    news_chunks = [
        c for c in state.get("retrieved_chunks", [])
        if c.chunk.metadata.modality == Modality.NEWS
    ]
    if news_chunks:
        tags = [c.chunk.metadata.sentiment_tag for c in news_chunks if c.chunk.metadata.sentiment_tag]
        bullish = sum(1 for t in tags if t in (Sentiment.BULLISH, Sentiment.POSITIVE))
        bearish = sum(1 for t in tags if t in (Sentiment.BEARISH, Sentiment.NEGATIVE))
        if bullish > bearish:
            sentiment = Sentiment.BULLISH
        elif bearish > bullish:
            sentiment = Sentiment.BEARISH

    brief = InvestmentBrief(
        query=state["query"],
        ticker=state["ticker"],
        brief_markdown=state.get("analysis_draft", ""),
        summary=_extract_summary(state.get("analysis_draft", "")),
        sentiment=sentiment,
        citations=state.get("citations", []),
        contradictions=state.get("contradictions", []),
        confidence=state.get("confidence", ConfidenceScores()),
        modalities_used=modalities_used,
        num_chunks_retrieved=len(state.get("retrieved_chunks", [])),
        agent_hops=state.get("agent_hops", 0),
        latency_ms=state.get("latency_ms", 0.0),
    )

    return {"final_brief": brief}


def _extract_summary(markdown: str) -> str:
    """Extract the executive summary section from the brief markdown."""
    lines = markdown.split("\n")
    in_summary = False
    summary_lines = []
    for line in lines:
        if "executive summary" in line.lower():
            in_summary = True
            continue
        if in_summary and line.startswith("##"):
            break
        if in_summary and line.strip():
            summary_lines.append(line.strip())
    return " ".join(summary_lines)[:500] or markdown[:200]


# ── Conditional Routing ───────────────────────────────────────────────────────

def should_retry(state: SignalScoutState) -> str:
    """Route back to retrieval if critique score is low and attempts are within limit."""
    score = state.get("critique_score", 1.0)
    attempts = state.get("retrieval_attempts", 0)

    if score < settings.critique_score_threshold and attempts < settings.max_self_correction_loops:
        logger.info(f"[ROUTE] Score {score:.2f} < threshold. Retrying (attempt {attempts})")
        return "retry"
    return "done"


# ── Graph Builder ─────────────────────────────────────────────────────────────

def build_graph(db: AsyncSession) -> StateGraph:
    """Build and compile the SignalScout LangGraph agent graph."""

    # Inject DB session into retrieval_node via closure
    async def _retrieval_node(state):
        return await retrieval_node(state, db)

    graph = StateGraph(SignalScoutState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("retrieval", _retrieval_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("citation", citation_node)
    graph.add_node("contradiction", contradiction_node)
    graph.add_node("critique", critique_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "retrieval")
    graph.add_edge("retrieval", "analysis")
    graph.add_edge("analysis", "citation")
    graph.add_edge("citation", "contradiction")
    graph.add_edge("contradiction", "critique")
    graph.add_conditional_edges(
        "critique",
        should_retry,
        {"retry": "retrieval", "done": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()


async def run_graph(
    query: str,
    ticker: str,
    db: AsyncSession,
) -> InvestmentBrief:
    """Run the full agent graph and return the final brief."""
    start_time = time.monotonic()

    graph = build_graph(db)

    initial_state: SignalScoutState = {
        "query": query,
        "ticker": ticker.upper(),
        "preferred_modalities": None,
        "parsed_intent": None,
        "time_range": None,
        "retrieval_instructions": None,
        "retrieved_chunks": [],
        "retrieval_attempts": 0,
        "analysis_draft": None,
        "audio_claims": [],
        "document_claims": [],
        "citations": [],
        "contradictions": [],
        "critique_score": 0.0,
        "critique_feedback": None,
        "confidence": ConfidenceScores(),
        "final_brief": None,
        "agent_hops": 0,
        "total_tokens": 0,
        "latency_ms": 0.0,
    }

    final_state = await graph.ainvoke(initial_state)
    latency = (time.monotonic() - start_time) * 1000

    brief = final_state["final_brief"]
    brief.latency_ms = latency
    return brief


async def stream_graph(
    query: str,
    ticker: str,
    db: AsyncSession,
) -> AsyncIterator[dict]:
    """Stream agent events for SSE consumption by the FastAPI endpoint."""
    graph = build_graph(db)

    initial_state: SignalScoutState = {
        "query": query,
        "ticker": ticker.upper(),
        "preferred_modalities": None,
        "parsed_intent": None,
        "time_range": None,
        "retrieval_instructions": None,
        "retrieved_chunks": [],
        "retrieval_attempts": 0,
        "analysis_draft": None,
        "audio_claims": [],
        "document_claims": [],
        "citations": [],
        "contradictions": [],
        "critique_score": 0.0,
        "critique_feedback": None,
        "confidence": ConfidenceScores(),
        "final_brief": None,
        "agent_hops": 0,
        "total_tokens": 0,
        "latency_ms": 0.0,
    }

    async for event in graph.astream_events(initial_state, version="v2"):
        event_type = event.get("event", "")
        node_name = event.get("name", "")

        if event_type == "on_chain_start" and node_name in (
            "orchestrator", "retrieval", "analysis", "citation", "contradiction", "critique", "finalize"
        ):
            yield {"type": "agent_start", "agent": node_name}

        elif event_type == "on_chain_end" and node_name == "finalize":
            output = event.get("data", {}).get("output", {})
            brief = output.get("final_brief")
            if brief:
                yield {"type": "complete", "brief": brief.model_dump(mode="json")}
