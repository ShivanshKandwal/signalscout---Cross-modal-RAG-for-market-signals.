"""
Audio ingestion pipeline — earnings call transcription and chunking.
Whisper ASR → pyannote diarization → speaker-turn chunks → Audio-Text-to-Text summary.
HF Tasks: Automatic Speech Recognition, Audio-Text-to-Text
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Iterator, List, Optional, Tuple
from uuid import uuid4

import numpy as np
from transformers import pipeline

from signalscout.config import settings
from signalscout.models import Chunk, ChunkMetadata, Modality

logger = logging.getLogger(__name__)

_asr_pipeline = None
_summarizer = None


def _get_asr():
    global _asr_pipeline
    if _asr_pipeline is None:
        logger.info(f"Loading ASR model: {settings.hf_asr_model}")
        _asr_pipeline = pipeline(
            "automatic-speech-recognition",
            model=settings.hf_asr_model,
            token=settings.hf_token or None,
            device=-1,   # CPU; set 0 for GPU
            chunk_length_s=30,
            return_timestamps="word",
        )
    return _asr_pipeline


def _get_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = pipeline(
            "summarization",
            model=settings.hf_summarization_model,
            token=settings.hf_token or None,
            device=-1,
        )
    return _summarizer


# ── Transcription ──────────────────────────────────────────────────────────────

def transcribe_audio(audio_path: str | Path) -> dict:
    """
    Transcribe an audio file using Whisper.
    Returns dict with 'text' and 'chunks' (word-level timestamps).
    HF Task: Automatic Speech Recognition
    """
    asr = _get_asr()
    logger.info(f"[ASR] Transcribing: {audio_path}")
    result = asr(str(audio_path), batch_size=8)
    logger.info(f"[ASR] Transcription complete. Length: {len(result['text'])} chars")
    return result


# ── Diarization ───────────────────────────────────────────────────────────────

def diarize_audio(audio_path: str | Path) -> Optional[list]:
    """
    Speaker diarization using pyannote.audio.
    Returns list of {speaker, start, end} segments.
    Requires HF_TOKEN with pyannote model access accepted.

    NOTE: User must accept pyannote model license at:
    https://huggingface.co/pyannote/speaker-diarization-3.1
    """
    try:
        from pyannote.audio import Pipeline as PyannotePipeline

        diar = PyannotePipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=settings.hf_token,
        )
        diarization = diar(str(audio_path))
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end,
            })
        logger.info(f"[DIARIZE] Found {len(set(s['speaker'] for s in segments))} speakers.")
        return segments

    except ImportError:
        logger.warning("pyannote.audio not installed. Skipping diarization.")
        return None
    except Exception as e:
        logger.warning(f"Diarization failed: {e}. Returning None.")
        return None


def align_diarization(
    whisper_result: dict,
    diarization: Optional[list],
) -> List[dict]:
    """
    Align speaker labels with Whisper word-level timestamps.
    Returns list of {speaker, start, end, text} turn dicts.
    Falls back to single-speaker if diarization is None.
    """
    if not diarization:
        # No diarization: treat entire transcript as one speaker turn
        return [{
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": 9999.0,
            "text": whisper_result["text"],
        }]

    # Build word → speaker mapping from timestamps
    word_chunks = whisper_result.get("chunks", [])
    speaker_turns = []
    current_speaker = None
    current_words: List[str] = []
    current_start = 0.0

    for word_chunk in word_chunks:
        word = word_chunk.get("text", "")
        timestamps = word_chunk.get("timestamp", [0, 0])
        word_start = timestamps[0] if timestamps[0] else 0.0
        word_end = timestamps[1] if timestamps[1] else 0.0

        # Find speaker for this word's midpoint
        word_mid = (word_start + word_end) / 2
        speaker = "SPEAKER_00"
        for seg in diarization:
            if seg["start"] <= word_mid <= seg["end"]:
                speaker = seg["speaker"]
                break

        if speaker != current_speaker:
            if current_words and current_speaker:
                speaker_turns.append({
                    "speaker": current_speaker,
                    "start": current_start,
                    "end": word_start,
                    "text": " ".join(current_words),
                })
            current_speaker = speaker
            current_words = [word]
            current_start = word_start
        else:
            current_words.append(word)

    if current_words and current_speaker:
        speaker_turns.append({
            "speaker": current_speaker,
            "start": current_start,
            "end": 9999.0,
            "text": " ".join(current_words),
        })

    return speaker_turns


def summarize_turn(turn_text: str) -> str:
    """
    Summarize a speaker turn.
    HF Task: Audio-Text-to-Text (summarization applied to ASR output)
    """
    if len(turn_text.split()) < 50:
        return turn_text   # too short to summarize
    summarizer = _get_summarizer()
    try:
        result = summarizer(
            turn_text[:1024],
            max_length=100,
            min_length=30,
            do_sample=False,
            truncation=True,
        )
        return result[0]["summary_text"]
    except Exception:
        return turn_text[:500]


# ── Main ingestion ─────────────────────────────────────────────────────────────

def ingest_audio(
    audio_path: str | Path,
    ticker: str,
    call_date: Optional[date] = None,
    source_url: Optional[str] = None,
    run_diarization: bool = True,
) -> Iterator[Chunk]:
    """
    Full earnings call audio pipeline.
    Yields Chunk objects per speaker turn, ready for embedding.
    """
    logger.info(f"[AUDIO] Starting audio ingestion for {ticker}: {audio_path}")

    # Step 1: ASR
    whisper_result = transcribe_audio(audio_path)

    # Step 2: Diarization (optional, requires HF token + model access)
    diarization = diarize_audio(audio_path) if run_diarization else None

    # Step 3: Align speaker turns
    turns = align_diarization(whisper_result, diarization)
    logger.info(f"[AUDIO] Produced {len(turns)} speaker turns.")

    chunk_index = 0
    for turn in turns:
        text = turn["text"].strip()
        if len(text.split()) < 15:
            continue   # skip very short turns

        # Step 4: Summarize long turns (Audio-Text-to-Text)
        summary = summarize_turn(text)

        meta = ChunkMetadata(
            ticker=ticker.upper(),
            modality=Modality.AUDIO,
            source_url=source_url,
            call_date=call_date,
            speaker=turn["speaker"],
            chunk_index=chunk_index,
            extra={
                "start_sec": turn["start"],
                "end_sec": turn["end"],
                "raw_text": text[:200],   # store first 200 chars of raw
            },
        )
        yield Chunk(
            id=uuid4(),
            content=summary,
            metadata=meta,
        )
        chunk_index += 1

    logger.info(f"[AUDIO] Audio ingestion complete: {chunk_index} chunks for {ticker}")
