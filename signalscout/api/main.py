"""
FastAPI backend — streaming investment brief API.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from signalscout.agents.graph import run_graph, stream_graph
from signalscout.config import settings
from signalscout.models import BriefRequest, BriefResponse, TickerInfo
from signalscout.models.database import (
    BriefORM,
    ChunkORM,
    EvalRunORM,
    get_db,
    init_db,
)
from signalscout.observability.metrics import BRIEF_LATENCY, BRIEF_REQUESTS

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init database, enable pgvector extension."""
    logger.info("SignalScout API starting up...")
    await init_db()
    logger.info("Database initialized.")
    yield
    logger.info("SignalScout API shutting down.")


app = FastAPI(
    title="SignalScout API",
    description="Multimodal Market Intelligence Agent with LLMOps",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)


# ── Brief Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/brief", response_model=BriefResponse, tags=["Briefs"])
async def create_brief(
    request: BriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the full agent graph and return a structured investment brief."""
    if not request.stream:
        brief = await run_graph(request.query, request.ticker, db)

        # Persist to DB
        orm = BriefORM(
            id=brief.id,
            query=brief.query,
            ticker=brief.ticker,
            brief_markdown=brief.brief_markdown,
            summary=brief.summary,
            sentiment=brief.sentiment.value,
            confidence_json=brief.confidence.model_dump(),
            modalities_used=[m.value for m in brief.modalities_used],
            num_chunks_retrieved=brief.num_chunks_retrieved,
            agent_hops=brief.agent_hops,
            latency_ms=brief.latency_ms,
            citations_json=[c.model_dump(mode="json") for c in brief.citations],
            contradictions_json=[c.model_dump(mode="json") for c in brief.contradictions],
        )
        db.add(orm)
        await db.commit()

        BRIEF_REQUESTS.labels(ticker=request.ticker).inc()
        BRIEF_LATENCY.labels(ticker=request.ticker).observe(brief.latency_ms / 1000)

        return BriefResponse(brief_id=brief.id, brief=brief)

    raise HTTPException(status_code=400, detail="Use POST /api/brief/stream for streaming.")


@app.post("/api/brief/stream", tags=["Briefs"])
async def stream_brief(
    request: BriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream agent events as Server-Sent Events (SSE).
    Each event is JSON: {"type": "agent_start"|"complete", ...}
    """
    async def event_generator() -> AsyncIterator[str]:
        async for event in stream_graph(request.query, request.ticker, db):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/brief/{brief_id}", tags=["Briefs"])
async def get_brief(brief_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve a stored investment brief by ID."""
    stmt = select(BriefORM).where(BriefORM.id == brief_id)
    result = await db.execute(stmt)
    brief_orm = result.scalar_one_or_none()
    if not brief_orm:
        raise HTTPException(status_code=404, detail="Brief not found")
    return brief_orm


# ── Ticker Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/tickers", response_model=list[TickerInfo], tags=["Data"])
async def list_tickers(db: AsyncSession = Depends(get_db)):
    """List all tickers with ingested data."""
    stmt = select(
        ChunkORM.ticker,
        func.count(ChunkORM.id).label("chunk_count"),
        func.array_agg(ChunkORM.modality.distinct()).label("modalities"),
        func.max(ChunkORM.created_at).label("last_ingested"),
    ).group_by(ChunkORM.ticker)

    result = await db.execute(stmt)
    rows = result.fetchall()

    return [
        TickerInfo(
            ticker=row.ticker,
            chunk_count=row.chunk_count,
            modalities=row.modalities or [],
            last_ingested=row.last_ingested,
        )
        for row in rows
    ]


# ── Eval Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/eval/latest", tags=["Eval"])
async def latest_eval(db: AsyncSession = Depends(get_db)):
    """Return the most recent RAGAS evaluation run."""
    stmt = select(EvalRunORM).order_by(EvalRunORM.run_timestamp.desc()).limit(1)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        return {"message": "No eval runs yet. Run: make eval"}
    return run


@app.get("/api/eval/history", tags=["Eval"])
async def eval_history(
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return recent RAGAS eval history for dashboard plotting."""
    stmt = select(EvalRunORM).order_by(EvalRunORM.run_timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
