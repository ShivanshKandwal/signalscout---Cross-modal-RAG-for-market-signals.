"""
LangGraph multi-agent graph - 5 agents:
Orchestrator → Retrieval → Analysis → Citation → Critique (→ retry loop)

Key improvements:
- Async timeouts on all LLM calls to prevent infinite hangs
- Live data fallback (yfinance + web search) when DB has no chunks
- Graceful handling of empty retrieval (no model crash on 0 chunks)
- Lightweight reranking fallback (RRF scores only) when CrossEncoder unavailable
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, AsyncIterator, Dict, List
from uuid import uuid4

# Windows console UTF-8 fix: prevent 'ascii' codec errors from LLM Unicode output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Also fix logging handlers to use UTF-8
def _fix_logging_unicode():
    """Replace logging stream handlers with UTF-8-safe versions."""
    import io
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if hasattr(handler, 'stream') and hasattr(handler.stream, 'buffer'):
            try:
                handler.stream = io.TextIOWrapper(
                    handler.stream.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
            except Exception:
                pass

_fix_logging_unicode()

logger = logging.getLogger(__name__)


def _safe(msg: str) -> str:
    """Encode message to ASCII-safe string, replacing non-ASCII chars with '?'."""
    return msg.encode('ascii', errors='replace').decode('ascii')


def _slog(logger_fn, msg: str) -> None:
    """Safe log: prevents UnicodeEncodeError on Windows by replacing non-ASCII."""
    try:
        logger_fn(msg)
    except UnicodeEncodeError:
        logger_fn(_safe(msg))

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from signalscout.agents.state import SignalScoutState
from signalscout.config import settings
from signalscout.models import (
    Citation,
    Chunk,
    ChunkMetadata,
    Contradiction,
    ConfidenceScores,
    ContradictionSeverity,
    InvestmentBrief,
    Modality,
    NLILabel,
    RetrievedChunk,
    Sentiment,
)

# ── LLM Factory ───────────────────────────────────────────────────────────────

_gemini_key_index = 0

def _get_gemini_keys() -> list[str]:
    """Parse comma-separated keys from config and env."""
    import os
    raw_key = (
        getattr(settings, 'gemini_api_key', None)
        or os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
    )
    if not raw_key:
        return []
    # Support comma-separated key rotation
    keys = [k.strip() for k in raw_key.split(",") if k.strip()]
    return [k.split()[0] for k in keys if len(k) > 10 and not k.startswith("your_")]


class RetryingLLM:
    """Wrapper that catches 429 / RESOURCE_EXHAUSTED and TimeoutError and retries with key rotation."""
    def __init__(self, timeout: int):
        self.timeout = timeout
        # Hard per-key timeout: 15s max per attempt to detect hanging connections fast
        self._per_key_timeout = min(15.0, float(timeout))

    def _instantiate_gemini(self, api_key: str):
        # Support both AIza... (standard) and AQ... (new format) Gemini keys
        # New AQ-format keys work via the OpenAI-compatible REST endpoint
        if api_key.startswith("AQ"):
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model="gemini-2.0-flash",
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                temperature=0.1,
                max_tokens=2048,
                timeout=self._per_key_timeout,
                max_retries=0,
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.1,
            max_output_tokens=2048,
            timeout=self._per_key_timeout,
            max_retries=0,
        )

    async def ainvoke(self, *args, **kwargs):
        import asyncio
        global _gemini_key_index
        keys = _get_gemini_keys()

        if not keys:
            raise ValueError("No valid Gemini API keys found.")

        max_attempts = len(keys) * 2  # Give every key two chances
        last_exc = None

        for attempt in range(max_attempts):
            key = keys[_gemini_key_index % len(keys)]
            llm = self._instantiate_gemini(key)

            try:
                # Hard timeout per key attempt — catches both hangs and rate limits
                return await asyncio.wait_for(
                    llm.ainvoke(*args, **kwargs),
                    timeout=self._per_key_timeout
                )
            except (asyncio.TimeoutError, Exception) as e:
                last_exc = e
                err_str = str(e).lower()
                is_timeout = isinstance(e, asyncio.TimeoutError) or "timeout" in err_str
                is_rate_limit = "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str

                if (is_rate_limit or is_timeout) and attempt < max_attempts - 1:
                    reason = "Timeout/hang" if is_timeout else "429 Rate limit"
                    _gemini_key_index += 1
                    next_key_idx = _gemini_key_index % len(keys)
                    print(f"[RETRYLLM] {reason} on key {attempt % len(keys)}. Rotating to key {next_key_idx}...")
                    await asyncio.sleep(0.5)  # Short flat delay between key rotations
                else:
                    raise e

        raise last_exc


def _get_llm(timeout: int = 60):
    """
    Returns LLM in priority order: Groq → Gemini (with rotation) → OpenAI
    """
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)

    # ── 1. Groq (fastest, generous free tier) ──────────────────────────────────
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key and len(groq_key) > 10 and not groq_key.startswith("your_"):
        from langchain_openai import ChatOpenAI
        logger.info("Using Groq (llama-3.3-70b-versatile)")
        return ChatOpenAI(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.1,
            max_tokens=2048,
            timeout=timeout,
            max_retries=2,
        )

    # ── 2. Gemini with key rotation ─────────────────────────────────────────────
    keys = _get_gemini_keys()
    if keys:
        return RetryingLLM(timeout)

    # Fallback to OpenAI if configured
    import os
    openai_key = (
        getattr(settings, 'openai_api_key', None)
        or os.environ.get("OPENAI_API_KEY", "")
    )
    if openai_key:
        openai_key = openai_key.strip().split()[0] if openai_key.strip() else ""

    if openai_key and len(openai_key) > 10 and not openai_key.startswith("your_"):
        from langchain_openai import ChatOpenAI
        logger.info("Using OpenAI model (gpt-4o-mini)")
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=openai_key,
            temperature=0.1,
            max_tokens=1024,
            timeout=timeout,
            max_retries=2,
        )
        # Wrap OpenAI as well to benefit from backoff
        class RetryingOpenAI:
            def __init__(self, model): self.model = model
            async def ainvoke(self, *args, **kwargs): return await self.model.ainvoke(*args, **kwargs)
        return RetryingOpenAI(llm)

    raise ValueError("No LLM provider key configured. Please set GEMINI_API_KEY (supports multiple comma-separated keys) or OPENAI_API_KEY in .env")




# ── Live Data Fetcher (fallback when DB is empty) ─────────────────────────────

async def _fetch_live_context(ticker: str, query: str) -> List[RetrievedChunk]:
    """
    Fetch live stock data and news when the database has no chunks.
    Uses yfinance for financial data and DuckDuckGo for news.
    Returns a list of RetrievedChunk objects with live data.
    """
    chunks: List[RetrievedChunk] = []

    # 1. Try yfinance for stock info
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()

        def _get_yf_data():
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            news_list = stock.news or []
            return info, news_list

        info, yf_news = await asyncio.wait_for(
            loop.run_in_executor(None, _get_yf_data),
            timeout=15.0
        )

        # Build a context chunk from stock info
        if info:
            company_name = info.get("longName") or info.get("shortName") or ticker
            summary = info.get("longBusinessSummary") or ""
            mkt_cap = info.get("marketCap")
            pe_ratio = info.get("trailingPE")
            revenue = info.get("totalRevenue")
            eps = info.get("trailingEps")
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            sector = info.get("sector") or ""
            industry = info.get("industry") or ""

            content_parts = [
                f"Company: {company_name} ({ticker})",
                f"Sector: {sector} | Industry: {industry}",
            ]
            if price:
                content_parts.append(f"Current Price: ${price:.2f}")
            if mkt_cap:
                content_parts.append(f"Market Cap: ${mkt_cap/1e9:.1f}B")
            if pe_ratio:
                content_parts.append(f"P/E Ratio: {pe_ratio:.1f}")
            if revenue:
                content_parts.append(f"Revenue (TTM): ${revenue/1e9:.1f}B")
            if eps:
                content_parts.append(f"EPS (TTM): ${eps:.2f}")
            if summary:
                content_parts.append(f"\nBusiness Summary: {summary[:600]}")

            meta = ChunkMetadata(
                ticker=ticker.upper(),
                modality=Modality.DOCUMENT,
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
            )
            chunk = Chunk(id=uuid4(), content="\n".join(content_parts), metadata=meta)
            chunks.append(RetrievedChunk(chunk=chunk, dense_score=0.9, sparse_score=0.9, rrf_score=0.9))
            logger.info(f"[LIVE] Fetched yfinance info for {ticker}")

        # Add recent yfinance news items
        for article in yf_news[:5]:
            title = article.get("title", "")
            link = article.get("link", "")
            if not title:
                continue
            meta = ChunkMetadata(
                ticker=ticker.upper(),
                modality=Modality.NEWS,
                source_url=link,
            )
            chunk = Chunk(id=uuid4(), content=f"[NEWS] {title}", metadata=meta)
            chunks.append(RetrievedChunk(chunk=chunk, dense_score=0.7, sparse_score=0.7, rrf_score=0.7))

    except asyncio.TimeoutError:
        logger.warning(f"[LIVE] yfinance timed out for {ticker}")
    except ImportError:
        logger.warning("[LIVE] yfinance not installed - skipping stock data fetch")
    except Exception as e:
        logger.warning(f"[LIVE] yfinance error for {ticker}: {e}")

    # 2. Try DuckDuckGo search for news
    if len(chunks) < 3:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            loop = asyncio.get_event_loop()

            def _ddg_search():
                search_query = f"{ticker} stock {query} 2024 2025"
                results = []
                with DDGS() as ddgs:
                    for r in ddgs.news(search_query, max_results=5):
                        results.append(r)
                return results

            ddg_results = await asyncio.wait_for(
                loop.run_in_executor(None, _ddg_search),
                timeout=10.0
            )

            for item in ddg_results:
                title = item.get("title", "")
                body = item.get("body", "")
                url = item.get("url", "")
                content = f"{title}. {body}".strip()
                if not content:
                    continue
                meta = ChunkMetadata(
                    ticker=ticker.upper(),
                    modality=Modality.NEWS,
                    source_url=url,
                )
                chunk = Chunk(id=uuid4(), content=content[:500], metadata=meta)
                chunks.append(RetrievedChunk(chunk=chunk, dense_score=0.6, sparse_score=0.6, rrf_score=0.6))

            logger.info(f"[LIVE] DuckDuckGo returned {len(ddg_results)} results for {ticker}")

        except asyncio.TimeoutError:
            logger.warning(f"[LIVE] DuckDuckGo search timed out for {ticker}")
        except ImportError:
            logger.warning("[LIVE] duckduckgo_search not installed - skipping web search")
        except Exception as e:
            logger.warning(f"[LIVE] DuckDuckGo search error: {e}")

    # 3. Fallback: build a minimal context message so analysis can still run
    if not chunks:
        meta = ChunkMetadata(
            ticker=ticker.upper(),
            modality=Modality.NEWS,
            source_url=f"https://finance.yahoo.com/quote/{ticker}",
        )
        chunk = Chunk(
            id=uuid4(),
            content=f"[LIVE CONTEXT] Analysis requested for ticker {ticker}. "
                    f"Query: {query}. Note: No historical data found in the database. "
                    f"Please use your training knowledge to provide a general analysis.",
            metadata=meta,
        )
        chunks.append(RetrievedChunk(chunk=chunk, dense_score=0.5, sparse_score=0.5, rrf_score=0.5))
        logger.warning(f"[LIVE] All live data sources failed - using minimal fallback for {ticker}")

    return chunks


# ── Agent Node Functions ───────────────────────────────────────────────────────

async def orchestrator_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Parses the query to determine intent, time range, and retrieval strategy.
    Routes to the appropriate retrieval instructions.
    """
    logger.info(f"[ORCHESTRATOR] Query: {state['query'][:80]}")
    llm = _get_llm(timeout=30)

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
        text = response.content.strip()
        # Strip markdown code fences if present
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text.strip())
    except asyncio.TimeoutError:
        _slog(logger.warning, "[ORCHESTRATOR] LLM timed out. Using defaults.")
        parsed = {}
    except Exception as e:
        _slog(logger.warning, f"[ORCHESTRATOR] Parse failed: {repr(e)[:200]}. Using defaults.")
        parsed = {}

    return {
        "parsed_intent": parsed.get("intent", state["query"]),
        "time_range": parsed.get("time_range", "recent"),
        "retrieval_instructions": parsed.get("retrieval_instructions", state["query"]),
        "agent_hops": state.get("agent_hops", 0) + 1,
    }


async def retrieval_node(state: SignalScoutState, db: AsyncSession) -> Dict[str, Any]:
    """
    Runs hybrid RAG retrieval using the query + orchestrator instructions.
    Falls back to live data (yfinance + web search) if DB has no chunks.
    """
    logger.info(f"[RETRIEVAL] Retrieving for {state['ticker']}")

    chunks: List[RetrievedChunk] = []

    # Try DB retrieval first
    try:
        from signalscout.agents.retriever import HybridRetriever
        retriever = HybridRetriever(db)
        modality_filter = None
        if state.get("preferred_modalities"):
            modality_filter = [m.value for m in state["preferred_modalities"]]

        query = state.get("retrieval_instructions") or state["query"]
        if state.get("critique_feedback"):
            query = f"{query}\n\nAdditional context needed: {state['critique_feedback']}"

        chunks = await asyncio.wait_for(
            retriever.retrieve(
                query=query,
                ticker=state["ticker"],
                modality_filter=modality_filter,
            ),
            timeout=60.0  # max 60s for DB retrieval
        )
        logger.info(f"[RETRIEVAL] DB returned {len(chunks)} chunks")
    except asyncio.TimeoutError:
        logger.warning("[RETRIEVAL] DB retrieval timed out after 60s")
        chunks = []
    except Exception as e:
        logger.warning(f"[RETRIEVAL] DB retrieval failed: {e}")
        chunks = []

    # If DB has no data, use live data
    if not chunks:
        logger.info(f"[RETRIEVAL] No DB chunks found - fetching live data for {state['ticker']}")
        chunks = await _fetch_live_context(state["ticker"], state.get("query", ""))

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
    Always completes within timeout — never hangs.
    """
    chunks = state.get("retrieved_chunks", [])
    logger.info(f"[ANALYSIS] Synthesizing {len(chunks)} chunks")

    if not chunks:
        logger.warning("[ANALYSIS] No chunks available - generating minimal response")
        draft = f"""## Analysis for {state['ticker']}

**Note:** No historical data was found in the database and live data retrieval also failed.

Please try again later or ingest data for this ticker first using the data ingestion pipeline.

**Query:** {state['query']}
"""
        return {
            "analysis_draft": draft,
            "agent_hops": state.get("agent_hops", 0) + 1,
        }

    llm = _get_llm(timeout=60)

    # Build context string (limit to 10 chunks, 400 chars each)
    context_parts = []
    for i, rc in enumerate(chunks[:10], 1):
        modality_label = rc.chunk.metadata.modality.value.upper()
        context_parts.append(
            f"[{i}][{modality_label}] {rc.chunk.content[:400]}"
        )
    context = "\n\n".join(context_parts)

    system = SystemMessage(content="""You are a senior financial analyst.
Synthesize the provided sources into a structured investment brief with sections:
## Executive Summary (2-3 sentences)
## Key Findings (bullet points with [source number] citations)
## Risk Factors (from SEC filings or known risks)
## Management Sentiment (from earnings calls or company statements)
## Market Signal (from news/market data)
## Conclusion

Use [1], [2] etc. to cite specific sources. Be factual and evidence-based.
If sources are limited, note this and provide general analysis based on available information.""")

    human = HumanMessage(content=f"""
Ticker: {state['ticker']}
Query: {state['query']}
Intent: {state.get('parsed_intent', 'general analysis')}

SOURCES:
{context}

Generate a structured investment brief with citations.""")

    try:
        response = await llm.ainvoke([system, human])
        draft = response.content
        # Ensure draft is safe for Windows console (replace unsupported chars)
        if isinstance(draft, str):
            draft = draft.encode('utf-8', errors='replace').decode('utf-8')
    except asyncio.TimeoutError:
        print("[ANALYSIS] LLM timed out after 60s")  # use print instead of logger for safety
        draft = f"""## Analysis for {state['ticker']}

**Note:** Analysis generation timed out. The AI model took too long to respond.

Based on the retrieved sources, here is a brief summary:

{chr(10).join(f"- {rc.chunk.content[:200]}" for rc in chunks[:5])}

Please try again."""
    except UnicodeEncodeError:
        # This is a Windows console encoding issue in logging, NOT an LLM failure
        # The LLM response was actually received - re-get it safely
        try:
            response2 = await llm.ainvoke([system, human])
            draft = response2.content.encode('utf-8', errors='replace').decode('utf-8')
        except Exception:
            draft = f"## Analysis for {state['ticker']}\n\n(Draft generation encountered encoding issues. Please retry.)"
    except Exception as e:
        err_msg = repr(e)[:200]
        print(f"[ANALYSIS] LLM call failed: {err_msg}")
        draft = f"""## Analysis for {state['ticker']}

**Note:** Analysis generation failed. Error: {err_msg}

Retrieved {len(chunks)} relevant chunks but could not synthesize them.
"""

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
    Lightweight version: only runs NLI if both audio AND document claims are present.
    Skips heavy model loading when data is sparse.
    """
    logger.info("[CONTRADICTION] Running cross-modal NLI check")

    audio_claims = state.get("audio_claims", [])
    document_claims = state.get("document_claims", [])

    if not audio_claims or not document_claims:
        logger.info("[CONTRADICTION] Skipped - need both audio and document claims")
        return {"contradictions": [], "agent_hops": state.get("agent_hops", 0) + 1}

    try:
        from sentence_transformers import SentenceTransformer
        from transformers import pipeline as hf_pipeline
        import numpy as np

        loop = asyncio.get_event_loop()

        def _run_nli():
            # Step 1: embed all claims
            embedder = SentenceTransformer(settings.hf_embedding_model)
            audio_embs = embedder.encode(audio_claims[:5], normalize_embeddings=True)
            doc_embs = embedder.encode(document_claims[:5], normalize_embeddings=True)

            # Step 2: find top-3 most similar cross-modal pairs
            sim_matrix = np.dot(audio_embs, doc_embs.T)
            top_pairs = []
            for i in range(sim_matrix.shape[0]):
                for j in range(sim_matrix.shape[1]):
                    top_pairs.append((i, j, float(sim_matrix[i, j])))
            top_pairs.sort(key=lambda x: -x[2])
            top_pairs = top_pairs[:3]

            # Step 3: NLI on top pairs
            nli = hf_pipeline("text-classification", model=settings.hf_nli_model, device=-1)
            contradictions = []

            chunks = state.get("retrieved_chunks", [])
            for audio_idx, doc_idx, _ in top_pairs:
                if audio_idx >= len(audio_claims) or doc_idx >= len(document_claims):
                    continue
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
                        explanation=f"NLI score: {score:.2f} - management statement may contradict filed disclosure",
                    ))
            return contradictions

        contradictions = await asyncio.wait_for(
            loop.run_in_executor(None, _run_nli),
            timeout=120.0  # NLI can be slow on first load
        )

        logger.info(f"[CONTRADICTION] Found {len(contradictions)} contradictions")
        return {"contradictions": contradictions, "agent_hops": state.get("agent_hops", 0) + 1}

    except asyncio.TimeoutError:
        logger.warning("[CONTRADICTION] NLI timed out - skipping")
        return {"contradictions": [], "agent_hops": state.get("agent_hops", 0) + 1}
    except Exception as e:
        logger.error(f"[CONTRADICTION] Failed: {e}")
        return {"contradictions": [], "agent_hops": state.get("agent_hops", 0) + 1}


async def critique_node(state: SignalScoutState) -> Dict[str, Any]:
    """
    Self-evaluation agent. Scores the draft brief for:
    - Citation coverage (are claims cited?)
    - Factual grounding (does it match retrieved context?)
    - Completeness (does it address the query?)
    Returns a critique_score and feedback for retry loop.
    """
    logger.info("[CRITIQUE] Evaluating draft")
    llm = _get_llm(timeout=30)

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
        text = response.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        scores = json.loads(text.strip())
    except asyncio.TimeoutError:
        _slog(logger.warning, "[CRITIQUE] LLM timed out - using default scores")
        scores = {"overall": 0.75, "feedback": "", "citation_coverage": 0.7, "factual_grounding": 0.75, "query_completeness": 0.8}
    except Exception as e:
        _slog(logger.warning, f"[CRITIQUE] Evaluation failed: {repr(e)[:200]} - using default scores")
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
