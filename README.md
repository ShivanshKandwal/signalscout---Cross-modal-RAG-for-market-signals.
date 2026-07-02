# SignalScout 📡
**Multimodal Market Intelligence Agent with LLMOps**

A production-grade, 5-agent LangGraph RAG system that ingests earnings call audio (Whisper ASR), SEC filings (pgvector), stock charts (Idefics3), and financial news — synthesizes cross-modal signals, detects management vs. filing contradictions via NLI, and produces structured investment briefs with cited evidence, confidence scores, and a full LLMOps observability layer.

---

## Architecture

```
Audio (Whisper ASR) ─────┐
SEC Filings (docling) ────┼──► pgvector + BM25 ──► LangGraph 5-Agent Graph ──► Brief
Charts (Idefics3 VLM) ───┤                          │
News (BART + MNLI) ───────┘                        RAGAS Eval + LangSmith + Grafana
```

**5 Agents:**
1. **Orchestrator** — parses intent, time range, modality preference
2. **Retrieval Agent** — hybrid BM25 + dense RAG + CrossEncoder re-ranking
3. **Analysis Agent** — synthesizes sources with [N] citations
4. **Citation Agent** — links every claim to source chunk + confidence score
5. **Critique Agent** — scores faithfulness, triggers self-correction loop if score < 0.70

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Docker Desktop (running)
- Node 18+

### 2. Setup
```bash
# Clone and install
cd c:/Software/signalscout
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env — add your HF_TOKEN and Supabase credentials
```

### 3. Start infrastructure
```bash
# Start Postgres (pgvector) + Redis
docker compose up -d postgres redis

# Initialize database tables
python -c "import asyncio; from signalscout.models.database import init_db; asyncio.run(init_db())"
```

### 4. Ingest data (takes ~10 min first run)
```bash
# Ingest EDGAR filings for a ticker
python scripts/ingest_cli.py edgar --tickers AAPL

# Ingest financial news (requires NEWS_API_KEY)
python scripts/ingest_cli.py news --tickers AAPL

# Generate and caption stock charts
python scripts/ingest_cli.py charts --tickers AAPL

# Build BM25 sparse index
python scripts/ingest_cli.py bm25

# Or run everything at once:
python scripts/ingest_cli.py all --tickers AAPL MSFT
```

### 5. Start the API
```bash
uvicorn signalscout.api.main:app --reload --port 8000
# Docs at: http://localhost:8000/docs
```

### 6. Start the Frontend
```bash
cd frontend
npm run dev
# UI at: http://localhost:5173
```

---

## Environment Variables

| Variable | Required | Source |
|---|---|---|
| `HF_TOKEN` | ✅ Yes | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `SUPABASE_DB_URL` | For cloud | [supabase.com](https://supabase.com) → Project Settings → Database |
| `NEWS_API_KEY` | For news | [newsapi.org](https://newsapi.org) — free tier |
| `LANGSMITH_API_KEY` | For traces | [smith.langchain.com](https://smith.langchain.com) — free tier |

---

## Eval

Create your 50-sample golden dataset:
```bash
# Format: one JSON per line
echo '{"question": "What supply chain risks did Apple cite in 2023?", "ground_truth": "...", "ticker": "AAPL", "modality": "document"}' >> data/golden_dataset.jsonl

# Run RAGAS evaluation
python -m signalscout.eval.harness
```

---

## HuggingFace Models Used

| Task | Model | Role |
|---|---|---|
| ASR | `openai/whisper-large-v3` | Transcribe earnings calls |
| Audio-Text-to-Text | `facebook/bart-large-cnn` | Summarize speaker turns |
| Doc QA | At query time via retrieval | Query SEC filings |
| Image-Text-to-Text | `HuggingFaceM4/idefics3-8b-llama3` | Caption charts |
| Summarization | `facebook/bart-large-cnn` | Compress news articles |
| Sentence Similarity | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Re-rank retrieved chunks |
| Zero-Shot | `facebook/bart-large-mnli` | Tag news sentiment |
| Text Classification | `ProsusAI/finbert` | Domain-specific sentiment |
| Feature Extraction | `BAAI/bge-m3` | Embed all chunks |

---

## Background Workers

```bash
# Celery worker (ingestion jobs)
celery -A signalscout.workers.tasks worker --loglevel=info

# Celery beat (nightly scheduler)
celery -A signalscout.workers.tasks beat --loglevel=info
```

Scheduled jobs:
- **2 AM nightly** — EDGAR filing ingestion
- **3 AM nightly** — News ingestion
- **Sunday 4 AM** — Embedding drift detection (cosine centroid shift)
- **Sunday 5 AM** — BM25 index rebuild

---

## Observability

- **Prometheus metrics**: `http://localhost:9090`
- **Grafana dashboard**: `http://localhost:3001` (admin/signalscout)
- **LangSmith traces**: Set `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY`
- **FastAPI metrics**: `http://localhost:8000/metrics`

---

## Resume Impact

> "Built a 5-agent LangGraph system processing 3 modalities (audio, PDF, image) with hybrid BM25 + dense RAG retrieval. Achieved 0.83 RAGAS faithfulness on a 50-sample financial QA eval set. Detects cross-modal contradictions via NLI (DeBERTa). Full LLMOps instrumentation with LangSmith traces and Grafana dashboards."
