"""SQLAlchemy ORM models and async database engine setup."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from signalscout.config import settings


def _async_url(url: str) -> str:
    """
    Ensure the database URL uses an async-compatible driver.
    Rewrites postgresql:// and postgres:// to postgresql+asyncpg://
    so psycopg2 (sync) is never accidentally loaded by the async engine.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


# ── Engine ────────────────────────────────────────────────────────────────────

_db_url = _async_url(settings.effective_database_url)
_is_supabase_pooler = ":6543/" in _db_url

if _is_supabase_pooler:
    # Supabase Transaction Pooler: requires NullPool (no persistent connections)
    # and prepared_statement_cache_size=0 to prevent prepared statement errors on transaction poolers.
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(
        _db_url,
        echo=settings.app_env == "development",
        poolclass=NullPool,
        connect_args={
            "ssl": "require",
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0
        },
    )
else:
    engine = create_async_engine(
        _db_url,
        echo=settings.app_env == "development",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields a database session."""
    async with AsyncSessionLocal() as session:
        yield session


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Tables ────────────────────────────────────────────────────────────────────

class ChunkORM(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(20), nullable=False, index=True)
    modality = Column(String(20), nullable=False, index=True)  # audio|document|image|news
    source_url = Column(Text, nullable=True)
    filed_date = Column(Date, nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)            # BAAI/bge-m3
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_chunks_ticker_modality", "ticker", "modality"),
        Index("ix_chunks_filed_date", "filed_date"),
    )


class BriefORM(Base):
    __tablename__ = "briefs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(Text, nullable=False)
    ticker = Column(String(20), nullable=False, index=True)
    brief_markdown = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    sentiment = Column(String(20), default="neutral")
    confidence_json = Column("confidence", JSON, default=dict)
    modalities_used = Column(JSON, default=list)
    num_chunks_retrieved = Column(Integer, default=0)
    agent_hops = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    token_cost_usd = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    citations_json = Column("citations", JSON, default=list)
    contradictions_json = Column("contradictions", JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class RequestLogORM(Base):
    __tablename__ = "request_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False) # "success" or "failed"
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalRunORM(Base):
    __tablename__ = "eval_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_timestamp = Column(DateTime, default=datetime.utcnow)
    git_sha = Column(String(40), nullable=True)
    dataset_size = Column(Integer, default=0)
    faithfulness = Column(Float, default=0.0)
    answer_relevancy = Column(Float, default=0.0)
    context_recall = Column(Float, default=0.0)
    context_precision = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)


class GoldenSampleORM(Base):
    __tablename__ = "golden_samples"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    ground_truth = Column(Text, nullable=False)
    source_chunk_id = Column(UUID(as_uuid=True), nullable=True)
    ticker = Column(String(20), nullable=False)
    modality = Column(String(20), nullable=False)
    section = Column(String(100), nullable=True)


class DriftReportORM(Base):
    __tablename__ = "drift_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String(20), nullable=False)
    week_of = Column(Date, nullable=False)
    cosine_drift = Column(Float, nullable=False)
    flagged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Init ──────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create tables and enable pgvector extension."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
