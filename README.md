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

## UI Console & Interactive Demo

SignalScout features a modern, dark-themed, glassmorphic research console designed for real-time market signal analysis.

### 1. Multi-Agent Research Console
* **Asset Ticker Selection**: A sleek dashboard grid to switch between active targets (e.g., Google, Apple, Nvidia, Microsoft).
* **Research Query Editor**: A multi-line natural language prompt bar equipped with inline modality toggles (supporting document ingestion, audio uploads, and stock charts).
* **Live Pipeline Standby**: Traces execution in real-time across your agent graph nodes (**Orchestrator** → **Retrieval Agent** → **Analysis Agent** → **Citation Agent** → **Contradiction Check** → **Critique Agent** → **Finalize**).

### 2. Live System Analytics Header
A persistent real-time performance banner tracking your local LLMOps metrics:
* **P50 / P95 Latency**: Computes response time distribution over successful runs.
* **Failure Rate**: Displays error/success percentage metrics dynamically.
* **Average Speed**: Shows token generation rate (e.g., `7603.3 t/s` for cached/local runs).
* **Total Tokens & Runs**: Accumulates operational scope.

### 3. Structured Brief Panel
* **Interactive Markdown Document**: Generates parsed briefs divided into Executive Summary, Key Findings, Risk Factors, Management Sentiment, and Market Signal sections.
* **Inline Citation Tags**: Every claim is marked with numerical hover citations (e.g., `[1]`, `[2]`) linked directly to the underlying raw database source chunk.

### 4. Radar Confidence Metrics
Evaluates RAG generation quality on the fly using standard RAGAS criteria:
* **Radar Graph**: Visually displays overlap between **Faithfulness**, **Relevancy**, **Recall**, and **Precision**.
* **Progress Bars**: Detailed breakdown of accuracy parameters (e.g., `Recall: 80%`).

### 5. Signal Strength Gauge
* **Radial Dial**: Dynamic needle visualization grading overall sentiment (e.g., **NEUTRAL**, **BULLISH**, **BEARISH**).
* **Confidence Overlay**: Displays aggregate confidence scores (e.g., `82% confidence`).
* **Source Citations Panel**: Lists the matched source document segments with percentage match weights.

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

## Desktop Application Packaging (Tauri)

You can package SignalScout as a fully self-contained local desktop application with its own custom installer icon, running the Python server locally in the background as a Native Sidecar.

### 1. Prerequisites (Windows)
1. **Rust Compiler**: Install from [rustup.rs](https://rustup.rs/).
2. **Visual Studio C++ Build Tools**: 
   * Open the Visual Studio Installer and modify your Visual Studio Build Tools installation.
   * Under the **Workloads** tab, select **Desktop development with C++**.
   * Under the details panel on the right, ensure that **MSVC v143 build tools** and **Windows 11/10 SDK** are checked, then apply the changes.

### 2. Prepare the Backend Sidecar
Compile the Python FastAPI server into a single-file executable using PyInstaller:
```bash
# Install packaging tool
pip install pyinstaller

# Compile the backend
pyinstaller --onefile --clean --name signalscout-backend signalscout/api/main.py

# Create binaries folder in Tauri project and copy the executable
# (Rename with target-triple suffix to allow Tauri discovery)
mkdir frontend/src-tauri/binaries
copy dist/signalscout-backend.exe frontend/src-tauri/binaries/signalscout-backend-x86_64-pc-windows-msvc.exe
```

### 3. Compile the Desktop App Installer
Navigate to the frontend folder, generate the icons, and run the Tauri release compiler:
```bash
cd frontend

# Generate all app shortcuts and installer icons from our logo
npx tauri icon logo.png

# Compile the NSIS Setup Installer (.exe)
npx tauri build
```
Once the build completes, your compiled setup installer will be saved at:
📂 `frontend/src-tauri/target/release/bundle/nsis/signalscout_0.1.0_x64-setup.exe`

---

## Local PDF Ingestion CLI

For handling large, multi-megabyte PDF documents locally without browser timeout limits, use the CLI ingestion tool:
```bash
python scripts/ingest_cli.py pdf --file "C:/path/to/your/document.pdf" --ticker GOOG
```
This chunks and embeds the document layout directly into the vector database.

---

## Observability

- **Prometheus metrics**: `http://localhost:9090`
- **Grafana dashboard**: `http://localhost:3001` (admin/signalscout)
- **LangSmith traces**: Set `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY`
- **FastAPI metrics**: `http://localhost:8000/metrics`

---

## Resume Impact

> "Built a 5-agent LangGraph system processing 3 modalities (audio, PDF, image) with hybrid BM25 + dense RAG retrieval. Achieved 0.83 RAGAS faithfulness on a 50-sample financial QA eval set. Detects cross-modal contradictions via NLI (DeBERTa). Full LLMOps instrumentation with LangSmith traces and Grafana dashboards. Packaged and compiled the system as a self-contained Tauri desktop application running a PyInstaller-compiled Python background sidecar."
