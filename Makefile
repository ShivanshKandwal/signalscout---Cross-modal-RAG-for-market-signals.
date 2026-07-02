.PHONY: dev install docker-up docker-down ingest eval test lint format

# ── Setup ─────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

dev:
	uvicorn signalscout.api.main:app --reload --port 8000

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker compose up -d postgres redis
	@echo "Waiting for DB to be ready..."
	@timeout 30 bash -c "until docker exec signalscout_postgres pg_isready; do sleep 1; done"

docker-full:
	docker compose up -d

docker-down:
	docker compose down

docker-clean:
	docker compose down -v

# ── Database ──────────────────────────────────────────────────────────────────
db-init:
	python -c "import asyncio; from signalscout.models.database import init_db; asyncio.run(init_db())"

db-migrate:
	alembic upgrade head

# ── Ingestion ─────────────────────────────────────────────────────────────────
ingest-edgar:
	python scripts/ingest_cli.py edgar --tickers $(TICKERS)

ingest-news:
	python scripts/ingest_cli.py news --tickers $(TICKERS)

ingest-charts:
	python scripts/ingest_cli.py charts --tickers $(TICKERS)

ingest-all:
	python scripts/ingest_cli.py all --tickers $(TICKERS)

build-bm25:
	python scripts/ingest_cli.py bm25

# ── Eval ──────────────────────────────────────────────────────────────────────
eval:
	python -m signalscout.eval.harness

# ── Workers ───────────────────────────────────────────────────────────────────
worker:
	celery -A signalscout.workers.tasks worker --loglevel=info --concurrency=2

beat:
	celery -A signalscout.workers.tasks beat --loglevel=info

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --cov=signalscout --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	ruff check signalscout/ tests/

format:
	ruff format signalscout/ tests/

# ── Frontend ──────────────────────────────────────────────────────────────────
frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
