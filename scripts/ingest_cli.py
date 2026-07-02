"""
CLI script for manual ingestion runs.
Usage examples:
  python scripts/ingest_cli.py edgar --tickers AAPL MSFT
  python scripts/ingest_cli.py news --tickers AAPL
  python scripts/ingest_cli.py charts --tickers AAPL TSLA
  python scripts/ingest_cli.py all --tickers AAPL MSFT GOOGL
  python scripts/ingest_cli.py bm25
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from signalscout.config import settings
from signalscout.models.database import AsyncSessionLocal, init_db
from signalscout.ingestion.embedder import store_chunks
from signalscout.agents.retriever import build_bm25_index

app = typer.Typer(help="SignalScout ingestion CLI")
console = Console()


async def _ingest_edgar_for_tickers(tickers: list[str]):
    from signalscout.ingestion.edgar import ingest_edgar
    await init_db()
    results = []
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            console.print(f"[cyan]📄 Ingesting EDGAR filings for {ticker}...[/cyan]")
            chunks = list(ingest_edgar(ticker))
            stored = await store_chunks(chunks, db)
            results.append((ticker, "document", stored))
            console.print(f"  [green]✓ {stored} chunks stored[/green]")
    return results


async def _ingest_news_for_tickers(tickers: list[str]):
    from signalscout.ingestion.news import ingest_news
    await init_db()
    results = []
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            console.print(f"[cyan]📰 Ingesting news for {ticker}...[/cyan]")
            chunks = list(ingest_news(ticker))
            stored = await store_chunks(chunks, db)
            results.append((ticker, "news", stored))
            console.print(f"  [green]✓ {stored} chunks stored[/green]")
    return results


async def _ingest_charts_for_tickers(tickers: list[str]):
    from signalscout.ingestion.charts import ingest_charts
    await init_db()
    results = []
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            console.print(f"[cyan]📊 Generating charts for {ticker}...[/cyan]")
            chunks = list(ingest_charts(ticker))
            stored = await store_chunks(chunks, db)
            results.append((ticker, "image", stored))
            console.print(f"  [green]✓ {stored} chunks stored[/green]")
    return results


async def _rebuild_bm25():
    await init_db()
    console.print("[cyan]🔍 Rebuilding BM25 indexes...[/cyan]")
    async with AsyncSessionLocal() as db:
        for ticker in settings.watchlist_tickers:
            await build_bm25_index(ticker, db)
            console.print(f"  [green]✓ {ticker} index built[/green]")


def _print_summary(results: list[tuple]):
    table = Table(title="Ingestion Summary", show_header=True)
    table.add_column("Ticker", style="cyan")
    table.add_column("Modality", style="blue")
    table.add_column("Chunks Stored", style="green")
    for ticker, modality, count in results:
        table.add_row(ticker, modality, str(count))
    console.print(table)


@app.command()
def edgar(
    tickers: list[str] = typer.Option(
        None, "--tickers", "-t", help="Space-separated ticker list"
    ),
):
    """Ingest SEC EDGAR filings."""
    tickers = tickers or settings.watchlist_tickers
    results = asyncio.run(_ingest_edgar_for_tickers(tickers))
    _print_summary(results)


@app.command()
def news(
    tickers: list[str] = typer.Option(
        None, "--tickers", "-t", help="Space-separated ticker list"
    ),
):
    """Ingest financial news."""
    tickers = tickers or settings.watchlist_tickers
    results = asyncio.run(_ingest_news_for_tickers(tickers))
    _print_summary(results)


@app.command()
def charts(
    tickers: list[str] = typer.Option(
        None, "--tickers", "-t", help="Space-separated ticker list"
    ),
):
    """Generate and ingest stock chart captions."""
    tickers = tickers or settings.watchlist_tickers
    results = asyncio.run(_ingest_charts_for_tickers(tickers))
    _print_summary(results)


@app.command()
def all(
    tickers: list[str] = typer.Option(
        None, "--tickers", "-t", help="Space-separated ticker list"
    ),
):
    """Run full ingestion pipeline: EDGAR + news + charts."""
    tickers = tickers or settings.watchlist_tickers
    console.rule("[bold]Full Ingestion Pipeline[/bold]")
    results = []
    results += asyncio.run(_ingest_edgar_for_tickers(tickers))
    results += asyncio.run(_ingest_news_for_tickers(tickers))
    results += asyncio.run(_ingest_charts_for_tickers(tickers))
    console.rule("[bold]Building BM25 Indexes[/bold]")
    asyncio.run(_rebuild_bm25())
    _print_summary(results)


@app.command()
def bm25():
    """Rebuild BM25 sparse retrieval indexes."""
    asyncio.run(_rebuild_bm25())
    console.print("[green]✓ BM25 indexes rebuilt[/green]")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app()
