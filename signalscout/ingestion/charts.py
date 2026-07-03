"""
Image pipeline - stock chart generation and VLM captioning.
yfinance OHLCV → mplfinance chart PNG → Idefics3 structured caption → chunk.
HF Task: Image-Text-to-Text
"""
from __future__ import annotations

import json
import logging
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Iterator, Optional
from uuid import uuid4

import mplfinance as mpf
import pandas as pd
import yfinance as yf
from PIL import Image
from transformers import AutoProcessor, AutoModelForVision2Seq
import torch

from signalscout.config import settings
from signalscout.models import Chunk, ChunkMetadata, Modality

logger = logging.getLogger(__name__)

_vlm_processor = None
_vlm_model = None


def _get_vlm():
    global _vlm_processor, _vlm_model
    if _vlm_model is None:
        logger.info(f"Loading VLM: {settings.hf_vlm_model}")
        _vlm_processor = AutoProcessor.from_pretrained(
            settings.hf_vlm_model,
            token=settings.hf_token or None,
        )
        _vlm_model = AutoModelForVision2Seq.from_pretrained(
            settings.hf_vlm_model,
            token=settings.hf_token or None,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )
    return _vlm_processor, _vlm_model


# ── Chart Generation ──────────────────────────────────────────────────────────

def generate_chart(
    ticker: str,
    period: str = "1y",
    output_path: Optional[Path] = None,
) -> tuple[Image.Image, pd.DataFrame]:
    """
    Download OHLCV data and render a candlestick chart as PIL Image.
    period: '3mo', '6mo', '1y', '2y'
    """
    logger.info(f"[CHART] Fetching OHLCV for {ticker} ({period})")
    data = yf.download(ticker, period=period, progress=False, auto_adjust=True)

    if data.empty:
        raise ValueError(f"No price data for {ticker}")

    # Render candlestick chart
    buf = BytesIO()
    mpf.plot(
        data,
        type="candle",
        style="charles",
        title=f"{ticker} - {period}",
        ylabel="Price (USD)",
        volume=True,
        savefig=dict(fname=buf, dpi=100, bbox_inches="tight"),
    )
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    if output_path:
        img.save(output_path)

    return img, data


# ── VLM Caption ───────────────────────────────────────────────────────────────

CHART_PROMPT = """Analyze this stock chart carefully and respond with a JSON object containing:
{
  "trend": "uptrend" | "downtrend" | "sideways",
  "trend_strength": "strong" | "moderate" | "weak",
  "key_price_levels": [list of notable price levels as floats],
  "volume_pattern": "increasing" | "decreasing" | "stable" | "spike",
  "notable_events": [list of observations about price spikes, gaps, or reversals],
  "technical_summary": "2-3 sentence plain English summary of chart patterns"
}
Respond ONLY with valid JSON."""


def caption_chart(image: Image.Image, ticker: str) -> dict:
    """
    Use Idefics3 to extract structured information from a chart image.
    HF Task: Image-Text-to-Text
    Returns a dict with trend, key levels, volume pattern, etc.
    """
    processor, model = _get_vlm()

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": CHART_PROMPT},
            ],
        }
    ]

    try:
        prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(
            text=prompt,
            images=[image],
            return_tensors="pt",
        )

        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
            )

        # Decode only the new tokens
        generated = processor.decode(
            output_ids[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=True,
        )

        # Parse JSON from the response
        json_match = generated.strip()
        caption_data = json.loads(json_match)
        return caption_data

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"[CHART] VLM parsing failed for {ticker}: {e}")
        return {
            "trend": "unknown",
            "technical_summary": f"Chart analysis unavailable: {str(e)[:100]}",
        }


def chart_to_text(caption: dict, ticker: str, period: str) -> str:
    """Convert a structured chart caption dict to embeddable text."""
    lines = [f"Stock chart analysis for {ticker} ({period}):"]
    if "trend" in caption:
        strength = caption.get("trend_strength", "")
        lines.append(f"Trend: {strength} {caption['trend']}")
    if "key_price_levels" in caption:
        levels = ", ".join(str(p) for p in caption["key_price_levels"][:5])
        lines.append(f"Key price levels: {levels}")
    if "volume_pattern" in caption:
        lines.append(f"Volume pattern: {caption['volume_pattern']}")
    if "notable_events" in caption:
        for event in caption["notable_events"][:3]:
            lines.append(f"- {event}")
    if "technical_summary" in caption:
        lines.append(caption["technical_summary"])
    return "\n".join(lines)


# ── Main ingestion ─────────────────────────────────────────────────────────────

def ingest_charts(
    ticker: str,
    periods: Optional[list] = None,
) -> Iterator[Chunk]:
    """
    Generate chart images for multiple periods and caption them with VLM.
    Yields one Chunk per period.
    """
    if periods is None:
        periods = ["3mo", "1y"]

    logger.info(f"[CHART] Starting chart ingestion for {ticker}")

    for period in periods:
        try:
            image, ohlcv_data = generate_chart(ticker, period)
            caption = caption_chart(image, ticker)
            text_content = chart_to_text(caption, ticker, period)

            # Get the latest price from the data
            latest_price = float(ohlcv_data["Close"].iloc[-1]) if not ohlcv_data.empty else None

            meta = ChunkMetadata(
                ticker=ticker.upper(),
                modality=Modality.IMAGE,
                chart_period=period,
                filed_date=date.today(),
                extra={
                    "caption_json": caption,
                    "latest_price": latest_price,
                    "data_points": len(ohlcv_data),
                },
            )
            yield Chunk(
                id=uuid4(),
                content=text_content,
                metadata=meta,
            )
            logger.info(f"[CHART] Yielded chart chunk for {ticker} {period}")

        except Exception as e:
            logger.error(f"[CHART] Failed for {ticker} {period}: {e}")
            continue

    logger.info(f"[CHART] Chart ingestion complete for {ticker}")
