"""
News ingestion pipeline.
NewsAPI → deduplicate (MinHash) → summarize (BART) → zero-shot classify → embed.
HF Tasks: Summarization, Zero-Shot Classification, Feature Extraction
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Iterator, List, Optional
from uuid import uuid4

import httpx
from datasketch import MinHash, MinHashLSH
from tenacity import retry, stop_after_attempt, wait_exponential
from transformers import pipeline

from signalscout.config import settings
from signalscout.models import Chunk, ChunkMetadata, Modality, Sentiment

logger = logging.getLogger(__name__)

# Singleton HF pipelines
_summarizer = None
_zero_shot = None
_lsh: Optional[MinHashLSH] = None   # in-memory dedup index per run


def _get_summarizer():
    global _summarizer
    if _summarizer is None:
        logger.info(f"Loading summarizer: {settings.hf_summarization_model}")
        _summarizer = pipeline(
            "summarization",
            model=settings.hf_summarization_model,
            token=settings.hf_token or None,
            device=-1,    # CPU; set device=0 for GPU
        )
    return _summarizer


def _get_zero_shot():
    global _zero_shot
    if _zero_shot is None:
        logger.info(f"Loading zero-shot classifier: {settings.hf_zero_shot_model}")
        _zero_shot = pipeline(
            "zero-shot-classification",
            model=settings.hf_zero_shot_model,
            token=settings.hf_token or None,
            device=-1,
        )
    return _zero_shot


# ── MinHash deduplication ────────────────────────────────────────────────────

def _minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for word in text.lower().split():
        m.update(word.encode("utf-8"))
    return m


def _is_duplicate(text: str, lsh: MinHashLSH, threshold: float = 0.8) -> bool:
    m = _minhash(text)
    result = lsh.query(m)
    if result:
        return True
    key = hashlib.md5(text[:100].encode()).hexdigest()
    lsh.insert(key, m)
    return False


# ── NewsAPI fetch ─────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_news(ticker: str, company_name: Optional[str] = None, page_size: int = 20) -> List[dict]:
    """
    Fetch recent news articles for a ticker from NewsAPI.
    Returns raw article dicts.
    Requires NEWS_API_KEY in .env.
    """
    if not settings.news_api_key:
        logger.warning("NEWS_API_KEY not set — skipping news fetch.")
        return []

    query = company_name or ticker
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f'"{query}" stock OR earnings OR financial',
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": settings.news_api_key,
    }
    resp = httpx.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    articles = data.get("articles", [])
    logger.info(f"[NEWS] Fetched {len(articles)} articles for {ticker}")
    return articles


# ── Summarize ─────────────────────────────────────────────────────────────────

def summarize_article(content: str, max_length: int = 150, min_length: int = 40) -> str:
    """
    Summarize an article with BART.
    Returns a concise ~150-word summary for embedding.
    """
    if len(content.split()) < 60:
        return content   # too short to summarize

    summarizer = _get_summarizer()
    # Truncate input to avoid BART's 1024-token limit
    truncated = " ".join(content.split()[:800])
    try:
        result = summarizer(
            truncated,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            truncation=True,
        )
        return result[0]["summary_text"]
    except Exception as e:
        logger.warning(f"Summarization failed: {e}. Using raw content.")
        return content[:500]


# ── Zero-shot classify ────────────────────────────────────────────────────────

def classify_sentiment(text: str) -> tuple[Sentiment, float]:
    """
    Zero-shot classify article sentiment as bullish/bearish/neutral.
    Returns (Sentiment, confidence_score).
    HF Task: Zero-Shot Classification
    """
    classifier = _get_zero_shot()
    labels = ["bullish", "bearish", "neutral"]
    try:
        result = classifier(text[:512], candidate_labels=labels)
        top_label = result["labels"][0]
        top_score = result["scores"][0]
        sentiment_map = {
            "bullish": Sentiment.BULLISH,
            "bearish": Sentiment.BEARISH,
            "neutral": Sentiment.NEUTRAL,
        }
        return sentiment_map[top_label], top_score
    except Exception as e:
        logger.warning(f"Zero-shot classification failed: {e}")
        return Sentiment.NEUTRAL, 0.5


# ── Main ingestion ────────────────────────────────────────────────────────────

def ingest_news(ticker: str, company_name: Optional[str] = None) -> Iterator[Chunk]:
    """
    Full news ingestion pipeline for a ticker.
    Yields Chunk objects ready for embedding and storage.
    """
    logger.info(f"[NEWS] Starting news ingestion for {ticker}")

    articles = fetch_news(ticker, company_name)
    if not articles:
        return

    # Fresh LSH index for dedup within this run
    lsh = MinHashLSH(threshold=0.8, num_perm=128)

    for article in articles:
        title = article.get("title") or ""
        description = article.get("description") or ""
        content = article.get("content") or ""
        full_text = f"{title}. {description}. {content}".strip()

        if len(full_text.split()) < 30:
            continue   # skip near-empty articles

        # Dedup
        if _is_duplicate(full_text, lsh):
            logger.debug(f"[NEWS] Duplicate skipped: {title[:60]}")
            continue

        # Summarize
        summary = summarize_article(full_text)

        # Zero-shot sentiment
        sentiment, sentiment_score = classify_sentiment(summary)

        published_str = article.get("publishedAt", "")
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except Exception:
            published_at = datetime.utcnow()

        meta = ChunkMetadata(
            ticker=ticker.upper(),
            modality=Modality.NEWS,
            source_url=article.get("url"),
            sentiment_tag=sentiment,
            published_at=published_at,
            extra={
                "title": title,
                "source": article.get("source", {}).get("name", ""),
                "sentiment_score": sentiment_score,
            },
        )
        yield Chunk(
            id=uuid4(),
            content=summary,
            metadata=meta,
        )

    logger.info(f"[NEWS] News ingestion complete for {ticker}")
