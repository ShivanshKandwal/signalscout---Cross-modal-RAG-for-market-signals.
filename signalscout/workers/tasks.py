"""
Celery application + scheduled ingestion tasks.
Run worker:  celery -A signalscout.workers.tasks worker --loglevel=info
Run beat:    celery -A signalscout.workers.tasks beat --loglevel=info
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import List

import numpy as np
from celery import Celery
from celery.schedules import crontab

from signalscout.config import settings

logger = logging.getLogger(__name__)

# ── Celery App ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "signalscout",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ── Beat Schedule ─────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    # Nightly 2 AM UTC: ingest new EDGAR filings
    "nightly-edgar-ingest": {
        "task": "signalscout.workers.tasks.ingest_all_edgar",
        "schedule": crontab(hour=2, minute=0),
    },
    # Nightly 3 AM UTC: ingest news
    "nightly-news-ingest": {
        "task": "signalscout.workers.tasks.ingest_all_news",
        "schedule": crontab(hour=3, minute=0),
    },
    # Weekly Sunday 4 AM: embedding drift detection
    "weekly-drift-check": {
        "task": "signalscout.workers.tasks.check_embedding_drift",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
    # Weekly Sunday 5 AM: rebuild BM25 indexes
    "weekly-bm25-rebuild": {
        "task": "signalscout.workers.tasks.rebuild_bm25_indexes",
        "schedule": crontab(hour=5, minute=0, day_of_week=0),
    },
}


# ── Tasks ─────────────────────────────────────────────────────────────────────

def _run_async(coro):
    """Helper to run async code inside a Celery sync task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="signalscout.workers.tasks.ingest_ticker_edgar", bind=True, max_retries=3)
def ingest_ticker_edgar(self, ticker: str):
    """Ingest EDGAR filings for a single ticker."""
    try:
        from signalscout.ingestion.edgar import ingest_edgar
        from signalscout.ingestion.embedder import store_chunks
        from signalscout.models.database import AsyncSessionLocal

        chunks = list(ingest_edgar(ticker))
        logger.info(f"[TASK] {ticker}: {len(chunks)} EDGAR chunks to store")

        async def _store():
            async with AsyncSessionLocal() as db:
                return await store_chunks(chunks, db)

        stored = _run_async(_store())
        logger.info(f"[TASK] {ticker}: stored {stored} chunks")

        from signalscout.observability.metrics import INGESTION_DOCS
        INGESTION_DOCS.labels(ticker=ticker, modality="document").inc(stored)

        return {"ticker": ticker, "stored": stored}

    except Exception as exc:
        logger.error(f"[TASK] EDGAR ingest failed for {ticker}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="signalscout.workers.tasks.ingest_ticker_news", bind=True, max_retries=3)
def ingest_ticker_news(self, ticker: str):
    """Ingest news for a single ticker."""
    try:
        from signalscout.ingestion.news import ingest_news
        from signalscout.ingestion.embedder import store_chunks
        from signalscout.models.database import AsyncSessionLocal

        chunks = list(ingest_news(ticker))
        logger.info(f"[TASK] {ticker}: {len(chunks)} news chunks to store")

        async def _store():
            async with AsyncSessionLocal() as db:
                return await store_chunks(chunks, db)

        stored = _run_async(_store())

        from signalscout.observability.metrics import INGESTION_DOCS
        INGESTION_DOCS.labels(ticker=ticker, modality="news").inc(stored)

        return {"ticker": ticker, "stored": stored}

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="signalscout.workers.tasks.ingest_all_edgar")
def ingest_all_edgar():
    """Trigger EDGAR ingestion for all watchlist tickers."""
    tickers = settings.watchlist_tickers
    for ticker in tickers:
        ingest_ticker_edgar.delay(ticker)
    return {"tickers": tickers}


@celery_app.task(name="signalscout.workers.tasks.ingest_all_news")
def ingest_all_news():
    """Trigger news ingestion for all watchlist tickers."""
    tickers = settings.watchlist_tickers
    for ticker in tickers:
        ingest_ticker_news.delay(ticker)
    return {"tickers": tickers}


@celery_app.task(name="signalscout.workers.tasks.rebuild_bm25_indexes")
def rebuild_bm25_indexes():
    """Rebuild BM25 sparse indexes for all tickers."""
    from signalscout.agents.retriever import build_bm25_index
    from signalscout.models.database import AsyncSessionLocal

    async def _rebuild():
        async with AsyncSessionLocal() as db:
            for ticker in settings.watchlist_tickers:
                await build_bm25_index(ticker, db)
                logger.info(f"[BM25] Rebuilt index for {ticker}")

    _run_async(_rebuild())
    return {"status": "rebuilt", "tickers": settings.watchlist_tickers}


@celery_app.task(name="signalscout.workers.tasks.check_embedding_drift")
def check_embedding_drift():
    """
    Embedding drift detection.
    Computes cosine distance between this week's centroid vs last week's.
    Flags ticker for re-indexing if drift > 0.15.
    """
    from sqlalchemy import select, and_
    from signalscout.models.database import AsyncSessionLocal, ChunkORM, DriftReportORM

    today = date.today()
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)

    async def _check():
        async with AsyncSessionLocal() as db:
            results = []
            for ticker in settings.watchlist_tickers:
                # Current week embeddings
                stmt_cur = select(ChunkORM.embedding).where(
                    and_(
                        ChunkORM.ticker == ticker,
                        ChunkORM.created_at >= week_ago,
                    )
                ).limit(500)
                stmt_prev = select(ChunkORM.embedding).where(
                    and_(
                        ChunkORM.ticker == ticker,
                        ChunkORM.created_at >= two_weeks_ago,
                        ChunkORM.created_at < week_ago,
                    )
                ).limit(500)

                cur_result = await db.execute(stmt_cur)
                prev_result = await db.execute(stmt_prev)

                cur_embs = [row[0] for row in cur_result.fetchall() if row[0]]
                prev_embs = [row[0] for row in prev_result.fetchall() if row[0]]

                if not cur_embs or not prev_embs:
                    continue

                cur_centroid = np.mean(cur_embs, axis=0)
                prev_centroid = np.mean(prev_embs, axis=0)

                # Cosine distance = 1 - cosine_similarity
                dot = np.dot(cur_centroid, prev_centroid)
                norm = np.linalg.norm(cur_centroid) * np.linalg.norm(prev_centroid)
                cosine_sim = dot / norm if norm > 0 else 0
                drift = float(1 - cosine_sim)

                flagged = drift > 0.15
                report = DriftReportORM(
                    ticker=ticker,
                    week_of=today,
                    cosine_drift=drift,
                    flagged=flagged,
                )
                db.add(report)

                from signalscout.observability.metrics import EMBEDDING_DRIFT
                EMBEDDING_DRIFT.labels(ticker=ticker).set(drift)

                if flagged:
                    logger.warning(f"[DRIFT] {ticker}: drift={drift:.3f} - flagged for re-indexing")
                results.append({"ticker": ticker, "drift": drift, "flagged": flagged})

            await db.commit()
            return results

    return _run_async(_check())
