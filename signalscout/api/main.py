"""
FastAPI backend - streaming investment brief API.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
import pdfplumber
import tempfile
import os
from PIL import Image
from datetime import date, datetime
from uuid import uuid4
from pathlib import Path

from signalscout.agents.graph import run_graph, stream_graph
from signalscout.config import settings
from signalscout.models import BriefRequest, BriefResponse, TickerInfo, Chunk, ChunkMetadata, Modality
from signalscout.ingestion.edgar import parse_htm_to_sections, chunk_text
from signalscout.ingestion.audio import ingest_audio
from signalscout.ingestion.charts import caption_chart, chart_to_text
from signalscout.ingestion.embedder import store_chunks
from signalscout.models.database import (
    BriefORM,
    ChunkORM,
    EvalRunORM,
    RequestLogORM,
    get_db,
    init_db,
    AsyncSessionLocal,
)
from signalscout.observability.metrics import BRIEF_LATENCY, BRIEF_REQUESTS, BRIEF_FAILURES

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init database, enable pgvector extension."""
    logger.info("SignalScout API starting up...")
    try:
        await init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.warning(
            f"Database initialization failed (will use live data fallback): {e}\n"
            "The API will still work using yfinance + web search for live market data."
        )
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

async def _persist_brief(brief, db: AsyncSession):
    try:
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
            token_cost_usd=brief.token_cost_usd,
            total_tokens=brief.total_tokens,
            citations_json=[c.model_dump(mode="json") for c in brief.citations],
            contradictions_json=[c.model_dump(mode="json") for c in brief.contradictions],
        )
        db.add(orm)
        await db.commit()
        logger.info(f"Brief {brief.id} persisted to DB")
    except Exception as db_err:
        logger.warning(f"Could not persist brief to DB: {db_err}")
        try:
            await db.rollback()
        except Exception:
            pass


async def _log_request(ticker: str, status: str, latency_ms: float, db: AsyncSession):
    try:
        orm = RequestLogORM(
            ticker=ticker.upper(),
            status=status,
            latency_ms=latency_ms,
        )
        db.add(orm)
        await db.commit()
    except Exception as err:
        logger.warning(f"Could not log request: {err}")
        try:
            await db.rollback()
        except Exception:
            pass


@app.post("/api/brief", response_model=BriefResponse, tags=["Briefs"])
async def create_brief(
    request: BriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run the full agent graph and return a structured investment brief."""
    if request.stream:
        raise HTTPException(status_code=400, detail="Use POST /api/brief/stream for streaming.")

    start_time = func.now()  # We will track using python time
    import time
    t0 = time.monotonic()
    
    try:
        brief = await run_graph(request.query, request.ticker, db)
        latency = (time.monotonic() - t0) * 1000
        
        # Persist to DB
        await _persist_brief(brief, db)
        await _log_request(request.ticker, "success", latency, db)
        
        BRIEF_REQUESTS.labels(ticker=request.ticker).inc()
        BRIEF_LATENCY.labels(ticker=request.ticker).observe(latency / 1000)
        
        return BriefResponse(brief_id=brief.id, brief=brief)
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        await _log_request(request.ticker, "failed", latency, db)
        BRIEF_FAILURES.labels(ticker=request.ticker).inc()
        logger.error(f"Brief generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Brief generation failed: {str(e)}")


@app.post("/api/brief/stream", tags=["Briefs"])
async def stream_brief(
    request: BriefRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream agent events as Server-Sent Events (SSE).
    Each event is JSON: {"type": "agent_start"|"complete", ...}
    """
    import time
    t0 = time.monotonic()

    async def event_generator() -> AsyncIterator[str]:
        completed_brief = None
        try:
            async for event in stream_graph(request.query, request.ticker, db):
                if event.get("type") == "complete":
                    # Reconstruct brief model to persist it
                    from signalscout.models import InvestmentBrief
                    completed_brief = InvestmentBrief.model_validate(event.get("brief", {}))
                yield f"data: {json.dumps(event)}\n\n"
            
            latency = (time.monotonic() - t0) * 1000
            if completed_brief:
                await _persist_brief(completed_brief, db)
                await _log_request(request.ticker, "success", latency, db)
                BRIEF_REQUESTS.labels(ticker=request.ticker).inc()
                BRIEF_LATENCY.labels(ticker=request.ticker).observe(latency / 1000)
            else:
                # Node finished but no brief constructed
                await _log_request(request.ticker, "failed", latency, db)
                BRIEF_FAILURES.labels(ticker=request.ticker).inc()
                
            yield "data: [DONE]\n\n"
        except Exception as e:
            latency = (time.monotonic() - t0) * 1000
            await _log_request(request.ticker, "failed", latency, db)
            BRIEF_FAILURES.labels(ticker=request.ticker).inc()
            logger.error(f"SSE stream failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/analytics/system", tags=["Analytics"])
async def get_system_analytics(db: AsyncSession = Depends(get_db)):
    """Compute aggregate system metrics: P50 latency, P95 latency, Failure Rate, Total Tokens, Avg TPS, Total Cost."""
    # 1. Fetch failure rate from request_logs
    total_stmt = select(func.count(RequestLogORM.id))
    failed_stmt = select(func.count(RequestLogORM.id)).where(RequestLogORM.status == "failed")
    
    total_res = await db.execute(total_stmt)
    total_count = total_res.scalar() or 0
    
    failed_res = await db.execute(failed_stmt)
    failed_count = failed_res.scalar() or 0
    
    failure_rate = (failed_count / total_count * 100) if total_count > 0 else 0.0
    
    # 2. Fetch successful latencies to compute percentiles
    latency_stmt = select(RequestLogORM.latency_ms).where(RequestLogORM.status == "success")
    latency_res = await db.execute(latency_stmt)
    latencies = [row[0] for row in latency_res.fetchall()]
    
    p50 = 0.0
    p95 = 0.0
    if latencies:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)
        p50_idx = int(n * 0.5)
        p95_idx = int(n * 0.95)
        p50 = latencies_sorted[p50_idx] / 1000.0  # convert to seconds
        p95 = latencies_sorted[p95_idx] / 1000.0
        
    # 3. Fetch token/cost aggregates from BriefORM
    briefs_stmt = select(BriefORM.total_tokens, BriefORM.latency_ms, BriefORM.token_cost_usd)
    briefs_res = await db.execute(briefs_stmt)
    briefs_data = briefs_res.fetchall()
    
    total_tokens_sum = 0
    total_cost_sum = 0.0
    total_latency_sec = 0.0
    
    for row in briefs_data:
        total_tokens_sum += row[0] or 0
        total_latency_sec += (row[1] or 0.0) / 1000.0
        total_cost_sum += row[2] or 0.0
        
    avg_tps = 0.0
    if total_latency_sec > 0:
        avg_tps = total_tokens_sum / total_latency_sec
        
    return {
        "p50_latency_sec": round(p50, 2),
        "p95_latency_sec": round(p95, 2),
        "failure_rate_percent": round(failure_rate, 2),
        "total_requests": total_count,
        "avg_tokens_per_sec": round(avg_tps, 1),
        "total_tokens": total_tokens_sum,
        "total_cost_usd": round(total_cost_sum, 4),
    }


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


# ── Ingestion Endpoints ────────────────────────────────────────────────────────

async def bg_audio_ingest(temp_path: str, ticker: str, call_date_parsed: Optional[date]):
    try:
        chunks = list(ingest_audio(
            audio_path=temp_path,
            ticker=ticker,
            call_date=call_date_parsed,
            source_url="user_upload",
            run_diarization=True
        ))
        async with AsyncSessionLocal() as db_session:
            await store_chunks(chunks, db_session)
        logger.info(f"Background audio ingestion completed for {ticker}")
    except Exception as e:
        logger.error(f"Background audio ingestion failed for {ticker}: {e}")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Could not remove temp file {temp_path}: {e}")


@app.post("/api/ingest/pdf", tags=["Ingestion"])
async def ingest_pdf(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        from io import BytesIO
        file_bytes = await file.read()
        pdf_text_list = []
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    pdf_text_list.append(txt)
        full_text = "\n".join(pdf_text_list)
        
        sections = parse_htm_to_sections(full_text)
        chunks_to_store = []
        for section_name, section_text in sections:
            text_chunks = chunk_text(section_text)
            for chunk_str in text_chunks:
                meta = ChunkMetadata(
                    ticker=ticker.upper(),
                    modality=Modality.DOCUMENT,
                    source_url="user_upload",
                    filed_date=date.today(),
                    extra={"section_name": section_name}
                )
                chunks_to_store.append(Chunk(
                    id=uuid4(),
                    content=chunk_str,
                    metadata=meta
                ))
        
        stored_count = await store_chunks(chunks_to_store, db)
        return {"status": "ok", "chunks_stored": stored_count, "ticker": ticker.upper()}
    except Exception as e:
        logger.error(f"PDF ingestion failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/audio", status_code=202, tags=["Ingestion"])
async def ingest_audio_endpoint(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ticker: str = Form(...),
    call_date: Optional[str] = Form(None),
):
    suffix = Path(file.filename).suffix
    temp_fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(temp_fd, 'wb') as tmp:
            content = await file.read()
            tmp.write(content)
        
        call_date_parsed = None
        if call_date:
            try:
                call_date_parsed = datetime.strptime(call_date, "%Y-%m-%d").date()
            except ValueError:
                pass
                
        background_tasks.add_task(bg_audio_ingest, temp_path, ticker, call_date_parsed)
        return {"status": "processing", "message": "Whisper ASR may take 2-5 min"}
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Audio ingestion startup failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/chart", tags=["Ingestion"])
async def ingest_chart(
    file: UploadFile = File(...),
    ticker: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        image = Image.open(file.file)
        caption = caption_chart(image, ticker)
        text_content = chart_to_text(caption, ticker, "user_upload")
        
        meta = ChunkMetadata(
            ticker=ticker.upper(),
            modality=Modality.IMAGE,
            chart_period="user_upload",
            filed_date=date.today(),
            extra={"caption_json": caption}
        )
        chunk = Chunk(
            id=uuid4(),
            content=text_content,
            metadata=meta
        )
        
        await store_chunks([chunk], db)
        return {"status": "ok", "chunks_stored": 1, "caption": caption}
    except Exception as e:
        logger.error(f"Chart ingestion failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
