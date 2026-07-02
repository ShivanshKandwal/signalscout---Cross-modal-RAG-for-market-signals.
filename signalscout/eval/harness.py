"""
RAGAS evaluation harness.
Runs RAGAS metrics against the 50-sample golden dataset.
Usage: python -m signalscout.eval.harness
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from sqlalchemy.ext.asyncio import AsyncSession

from signalscout.agents.graph import run_graph
from signalscout.config import settings
from signalscout.models.database import AsyncSessionLocal, EvalRunORM, GoldenSampleORM
from sqlalchemy import select

logger = logging.getLogger(__name__)

GOLDEN_DATASET_PATH = Path("data/golden_dataset.jsonl")


# ── Load golden dataset ────────────────────────────────────────────────────────

async def load_golden_samples(db: AsyncSession) -> List[dict]:
    """Load the 50-sample golden dataset from DB or JSONL file."""
    # Try DB first
    stmt = select(GoldenSampleORM)
    result = await db.execute(stmt)
    samples = result.scalars().all()

    if samples:
        return [
            {
                "question": s.question,
                "ground_truth": s.ground_truth,
                "ticker": s.ticker,
            }
            for s in samples
        ]

    # Fallback: load from JSONL file
    if GOLDEN_DATASET_PATH.exists():
        with open(GOLDEN_DATASET_PATH) as f:
            return [json.loads(line) for line in f if line.strip()]

    logger.warning("No golden dataset found. Create data/golden_dataset.jsonl first.")
    return []


# ── Run inference on golden dataset ──────────────────────────────────────────

async def run_inference(samples: List[dict]) -> List[dict]:
    """Run the agent graph on each golden sample, collect answers + contexts."""
    results = []

    async with AsyncSessionLocal() as db:
        for i, sample in enumerate(samples, 1):
            logger.info(f"[EVAL] Sample {i}/{len(samples)}: {sample['question'][:60]}")
            try:
                brief = await run_graph(
                    query=sample["question"],
                    ticker=sample["ticker"],
                    db=db,
                )
                results.append({
                    "question": sample["question"],
                    "answer": brief.summary or brief.brief_markdown[:500],
                    "contexts": [c.chunk_excerpt for c in brief.citations[:5]],
                    "ground_truth": sample["ground_truth"],
                })
            except Exception as e:
                logger.error(f"[EVAL] Sample {i} failed: {e}")
                results.append({
                    "question": sample["question"],
                    "answer": "Error: inference failed",
                    "contexts": [],
                    "ground_truth": sample["ground_truth"],
                })

    return results


# ── RAGAS evaluation ──────────────────────────────────────────────────────────

def run_ragas(inference_results: List[dict]) -> dict:
    """Run RAGAS evaluation on inference results."""
    dataset = Dataset.from_list(inference_results)
    metrics = [faithfulness, answer_relevancy, context_recall, context_precision]

    logger.info(f"[RAGAS] Running evaluation on {len(inference_results)} samples...")
    result = evaluate(dataset, metrics=metrics)
    scores = result.to_pandas().mean().to_dict()
    logger.info(f"[RAGAS] Results: {scores}")
    return scores


# ── Store eval run ────────────────────────────────────────────────────────────

async def store_eval_run(scores: dict, dataset_size: int) -> None:
    """Persist RAGAS scores to the eval_runs table."""
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True
        ).strip()
    except Exception:
        git_sha = "unknown"

    async with AsyncSessionLocal() as db:
        run = EvalRunORM(
            run_timestamp=datetime.utcnow(),
            git_sha=git_sha,
            dataset_size=dataset_size,
            faithfulness=scores.get("faithfulness", 0.0),
            answer_relevancy=scores.get("answer_relevancy", 0.0),
            context_recall=scores.get("context_recall", 0.0),
            context_precision=scores.get("context_precision", 0.0),
        )
        db.add(run)
        await db.commit()
        logger.info(f"[EVAL] Stored eval run: faithfulness={run.faithfulness:.3f}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    logging.basicConfig(level=logging.INFO)

    async with AsyncSessionLocal() as db:
        samples = await load_golden_samples(db)

    if not samples:
        print("❌ No golden samples found. Create data/golden_dataset.jsonl first.")
        print("   Format: one JSON per line: {question, ground_truth, ticker, modality}")
        return

    print(f"✅ Loaded {len(samples)} golden samples")
    print("🤖 Running agent inference (this takes a while)...")

    inference_results = await run_inference(samples)

    print("📊 Running RAGAS evaluation...")
    scores = run_ragas(inference_results)

    print("\n" + "="*50)
    print("RAGAS EVALUATION RESULTS")
    print("="*50)
    for metric, score in scores.items():
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"  {metric:<25} {bar} {score:.3f}")
    print("="*50)

    await store_eval_run(scores, len(samples))
    print("✅ Results saved to eval_runs table.")


if __name__ == "__main__":
    asyncio.run(main())
