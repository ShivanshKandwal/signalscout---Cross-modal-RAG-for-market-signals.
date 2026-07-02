"""
EDGAR ingestion pipeline.
Pulls SEC 10-K/10-Q filings for a ticker → parses with docling
→ section-aware chunking → embed → store in pgvector.
HF Task: Document Question Answering (at query time), Feature Extraction (here)
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, List, Optional, Tuple
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from signalscout.models import Chunk, ChunkMetadata, Modality

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {
    "User-Agent": "SignalScout research@signalscout.dev",  # SEC requires this
    "Accept": "application/json",
}


# ── EDGAR API helpers ─────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def get_cik(ticker: str) -> Optional[str]:
    """Resolve a ticker symbol to its SEC CIK (company identifier)."""
    url = f"{EDGAR_BASE}/submissions/CIK{ticker}.json"
    # SEC stores CIK lookup at company facts endpoint via ticker map
    ticker_url = "https://www.sec.gov/files/company_tickers.json"
    resp = httpx.get(ticker_url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker.upper():
            cik = str(entry["cik_str"]).zfill(10)
            logger.info(f"Resolved {ticker} → CIK {cik}")
            return cik
    logger.warning(f"CIK not found for ticker: {ticker}")
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def get_recent_filings(cik: str, form_types: List[str] = None, max_filings: int = 5) -> List[dict]:
    """
    Fetch recent filing metadata for a CIK.
    Returns list of {accession_number, form, filed_date, primary_document}.
    """
    if form_types is None:
        form_types = ["10-K", "10-Q"]

    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = httpx.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary_docs = recent.get("primaryDocument", [])

    results = []
    for form, acc, dt, doc in zip(forms, accessions, dates, primary_docs):
        if form in form_types:
            results.append({
                "accession_number": acc,
                "form": form,
                "filed_date": dt,
                "primary_document": doc,
            })
            if len(results) >= max_filings:
                break

    logger.info(f"Found {len(results)} filings for CIK {cik}")
    return results


def get_filing_url(cik: str, accession: str, document: str) -> str:
    """Build the EDGAR URL for a specific filing document."""
    acc_clean = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_clean}/{document}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def download_filing(url: str) -> str:
    """Download filing HTML/HTM content as text."""
    resp = httpx.get(url, headers=HEADERS, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


# ── Document Parsing ──────────────────────────────────────────────────────────

def parse_htm_to_sections(html_text: str) -> List[Tuple[str, str]]:
    """
    Naive section extractor for SEC HTM filings.
    Returns list of (section_name, section_text).
    Falls back to docling for complex PDFs.
    """
    # Known SEC 10-K section headers
    section_patterns = [
        r"(Item\s+1A\.?\s*Risk Factors)",
        r"(Item\s+1B\.?\s*Unresolved Staff Comments)",
        r"(Item\s+2\.?\s*Properties)",
        r"(Item\s+7\.?\s*Management[''`]?s Discussion)",
        r"(Item\s+7A\.?\s*Quantitative)",
        r"(Item\s+8\.?\s*Financial Statements)",
        r"(Item\s+9A\.?\s*Controls and Procedures)",
    ]

    # Strip HTML tags
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&amp;", "&", clean)
    clean = re.sub(r"\s{3,}", "\n\n", clean)

    sections = []
    current_section = "General"
    current_text: List[str] = []

    for line in clean.splitlines():
        matched = False
        for pattern in section_patterns:
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                if current_text:
                    sections.append((current_section, "\n".join(current_text)))
                current_section = m.group(1).strip()
                current_text = []
                matched = True
                break
        if not matched:
            stripped = line.strip()
            if stripped:
                current_text.append(stripped)

    if current_text:
        sections.append((current_section, "\n".join(current_text)))

    return sections


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> List[str]:
    """
    Token-window chunking with overlap.
    Uses whitespace tokenization as proxy (1 word ≈ 1.3 tokens).
    """
    words = text.split()
    approx_chunk_words = int(chunk_size / 1.3)
    approx_overlap_words = int(overlap / 1.3)

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + approx_chunk_words, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 50:   # skip tiny fragments
            chunks.append(chunk)
        start += approx_chunk_words - approx_overlap_words
        if end == len(words):
            break

    return chunks


# ── Main Ingestion Function ───────────────────────────────────────────────────

def ingest_edgar(
    ticker: str,
    form_types: Optional[List[str]] = None,
    max_filings: int = 3,
) -> Iterator[Chunk]:
    """
    Full EDGAR ingestion pipeline for a ticker.
    Yields Chunk objects ready for embedding and storage.
    Call this from a Celery task or CLI script.
    """
    if form_types is None:
        form_types = ["10-K", "10-Q"]

    logger.info(f"[EDGAR] Starting ingestion for {ticker}")

    cik = get_cik(ticker)
    if not cik:
        logger.error(f"Cannot resolve CIK for {ticker}. Skipping.")
        return

    filings = get_recent_filings(cik, form_types, max_filings)

    for filing in filings:
        filed_date_str = filing["filed_date"]
        filed_date = date.fromisoformat(filed_date_str)
        filing_url = get_filing_url(cik, filing["accession_number"], filing["primary_document"])

        logger.info(f"[EDGAR] Downloading {filing['form']} filed {filed_date_str}: {filing_url}")

        try:
            html_text = download_filing(filing_url)
        except Exception as e:
            logger.error(f"[EDGAR] Failed to download {filing_url}: {e}")
            continue

        sections = parse_htm_to_sections(html_text)
        logger.info(f"[EDGAR] Parsed {len(sections)} sections from {filing['form']}")

        chunk_index = 0
        for section_name, section_text in sections:
            text_chunks = chunk_text(section_text)
            for chunk_text_item in text_chunks:
                meta = ChunkMetadata(
                    ticker=ticker.upper(),
                    modality=Modality.DOCUMENT,
                    source_url=filing_url,
                    filed_date=filed_date,
                    section=section_name,
                    chunk_index=chunk_index,
                    extra={"form_type": filing["form"]},
                )
                yield Chunk(
                    id=uuid4(),
                    content=chunk_text_item,
                    metadata=meta,
                )
                chunk_index += 1

        logger.info(f"[EDGAR] Yielded {chunk_index} chunks for {ticker} {filing['form']}")
        time.sleep(0.5)   # SEC rate-limit courtesy
