"""
SignalScout — centralized configuration via pydantic-settings.
All settings are loaded from environment variables or .env file.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/signalscout",
        description="Async SQLAlchemy URL for pgvector",
    )
    sync_database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/signalscout",
        description="Sync SQLAlchemy URL (Alembic, BM25 index builder)",
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── HuggingFace ───────────────────────────────────────────────────────────
    hf_token: str = ""
    hf_embedding_model: str = "BAAI/bge-m3"
    hf_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    hf_sentiment_model: str = "ProsusAI/finbert"
    hf_summarization_model: str = "facebook/bart-large-cnn"
    hf_zero_shot_model: str = "facebook/bart-large-mnli"
    hf_nli_model: str = "cross-encoder/nli-deberta-v3-base"
    hf_asr_model: str = "openai/whisper-large-v3"
    hf_vlm_model: str = "HuggingFaceM4/idefics3-8b-llama3"

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_db_url: str = ""

    # ── External APIs ─────────────────────────────────────────────────────────
    news_api_key: str = ""
    openai_api_key: str = ""

    # ── LangSmith ─────────────────────────────────────────────────────────────
    langsmith_api_key: str = ""
    langsmith_project: str = "signalscout"
    langsmith_tracing: bool = False

    # ── Retrieval ─────────────────────────────────────────────────────────────
    embedding_batch_size: int = 32
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 20
    reranker_top_k: int = 5

    # ── Agent ─────────────────────────────────────────────────────────────────
    critique_score_threshold: float = 0.70
    max_self_correction_loops: int = 2

    # ── Finance ───────────────────────────────────────────────────────────────
    watchlist_tickers_raw: str = Field(
        default="AAPL,MSFT,GOOGL,AMZN,NVDA",
        alias="WATCHLIST_TICKERS",
    )

    @property
    def watchlist_tickers(self) -> List[str]:
        return [t.strip() for t in self.watchlist_tickers_raw.split(",") if t.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_database_url(self) -> str:
        """Use Supabase URL if configured, otherwise local Postgres."""
        if self.supabase_db_url:
            return self.supabase_db_url
        return self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton settings — import this everywhere."""
    return Settings()


# Convenience alias
settings = get_settings()
