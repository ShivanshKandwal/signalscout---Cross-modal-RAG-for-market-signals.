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
            console.print(f"[cyan]Ingesting EDGAR filings for {ticker}...[/cyan]")
            chunks = list(ingest_edgar(ticker))
            stored = await store_chunks(chunks, db)
            results.append((ticker, "document", stored))
            console.print(f"  [green][OK] {stored} chunks stored[/green]")
    return results


async def _ingest_news_for_tickers(tickers: list[str]):
    from signalscout.ingestion.news import ingest_news
    await init_db()
    results = []
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            console.print(f"[cyan]Ingesting news for {ticker}...[/cyan]")
            chunks = list(ingest_news(ticker))
            stored = await store_chunks(chunks, db)
            results.append((ticker, "news", stored))
            console.print(f"  [green][OK] {stored} chunks stored[/green]")
    return results


async def _ingest_charts_for_tickers(tickers: list[str]):
    from signalscout.ingestion.charts import ingest_charts
    await init_db()
    results = []
    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            console.print(f"[cyan]Generating charts for {ticker}...[/cyan]")
            chunks = list(ingest_charts(ticker))
            stored = await store_chunks(chunks, db)
            results.append((ticker, "image", stored))
            console.print(f"  [green][OK] {stored} chunks stored[/green]")
    return results


async def _rebuild_bm25():
    await init_db()
    console.print("[cyan]Rebuilding BM25 indexes...[/cyan]")
    from sqlalchemy import select, func
    from signalscout.models.database import ChunkORM
    async with AsyncSessionLocal() as db:
        for ticker in settings.watchlist_tickers:
            # Check if we have chunks for this ticker
            count_stmt = select(func.count(ChunkORM.id)).where(ChunkORM.ticker == ticker.upper())
            count_res = await db.execute(count_stmt)
            count = count_res.scalar()
            
            if count and count > 0:
                await build_bm25_index(ticker, db)
                console.print(f"  [green][OK] {ticker} index built ({count} chunks)[/green]")
            else:
                console.print(f"  [yellow][WARN] {ticker} skipped (no chunks in database)[/yellow]")


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
    console.print("[green][OK] BM25 indexes rebuilt[/green]")


@app.command()
def pdf(
    path: str = typer.Option(..., "--path", "-p", help="Path to local PDF file"),
    ticker: str = typer.Option(..., "--ticker", "-t", help="Stock ticker to associate the document with"),
):
    """Ingest a local PDF file into the database."""
    async def _ingest():
        import pdfplumber
        from datetime import date
        from uuid import uuid4
        from signalscout.ingestion.edgar import parse_htm_to_sections, chunk_text
        from signalscout.models import Chunk, ChunkMetadata, Modality
        
        await init_db()
        
        pdf_path = Path(path)
        if not pdf_path.exists():
            console.print(f"[red]Error: File {path} does not exist[/red]")
            return
            
        console.print(f"[cyan]Reading PDF: {pdf_path.name}...[/cyan]")
        pdf_text_list = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    pdf_text_list.append(txt)
        full_text = "\n".join(pdf_text_list)
        
        console.print(f"[cyan]Parsing sections and chunking...[/cyan]")
        sections = parse_htm_to_sections(full_text)
        chunks_to_store = []
        for section_name, section_text in sections:
            text_chunks = chunk_text(section_text)
            for chunk_str in text_chunks:
                meta = ChunkMetadata(
                    ticker=ticker.upper(),
                    modality=Modality.DOCUMENT,
                    source_url=f"local://{pdf_path.name}",
                    filed_date=date.today(),
                    extra={"section_name": section_name}
                )
                chunks_to_store.append(Chunk(
                    id=uuid4(),
                    content=chunk_str,
                    metadata=meta
                ))
                
        console.print(f"[cyan]Generating embeddings and storing {len(chunks_to_store)} chunks...[/cyan]")
        async with AsyncSessionLocal() as db:
            stored = await store_chunks(chunks_to_store, db)
            console.print(f"[green][OK] {stored} chunks stored in database[/green]")
            
        # Rebuild BM25 for this ticker
        console.print(f"[cyan]Rebuilding BM25 index for {ticker}...[/cyan]")
        async with AsyncSessionLocal() as db:
            await build_bm25_index(ticker, db)
            console.print(f"[green][OK] BM25 index rebuilt[/green]")

    asyncio.run(_ingest())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app()
