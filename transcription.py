from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


MODEL_ID = "kotoba-tech/kotoba-whisper-v2.2"


def extract_segments(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return timestamped segments from regular or speaker-separated output."""
    chunks: list[dict[str, Any]] = []
    raw_chunks = result.get("chunks")
    if isinstance(raw_chunks, list):
        chunks.extend(raw_chunks)

    for key, value in result.items():
        if key.startswith("chunks/") and isinstance(value, list):
            chunks.extend(value)

    normalized = []
    for chunk in chunks:
        timestamp = chunk.get("timestamp") or chunk.get("timestamps")
        if not isinstance(timestamp, (list, tuple)) or len(timestamp) < 2:
            continue
        start, end = timestamp[0], timestamp[1]
        if start is None or end is None:
            continue
        text = str(chunk.get("text", "")).strip()
        if text:
            normalized.append(
                {"start": float(start), "end": float(end), "text": text}
            )

    normalized.sort(key=lambda item: (item["start"], item["end"]))
    return normalized


def format_transcript(result: dict[str, Any], gap_seconds: float) -> str:
    segments = extract_segments(result)
    if not segments:
        return str(result.get("text", "")).strip()

    parts = [segments[0]["text"]]
    for previous, current in zip(segments, segments[1:]):
        if current["start"] - previous["end"] >= gap_seconds:
            parts.append("/")
        parts.append(current["text"])
    return "".join(parts)


def worker_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "transcribe_worker.py"


def run_transcription(
    python_executable: str,
    audio_path: str,
    model: str,
    gap_seconds: float,
    on_status: Callable[[str], None] | None = None,
) -> str:
    command = [
        python_executable,
        str(worker_path()),
        "--audio",
        audio_path,
        "--model",
        model,
    ]
    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    result: dict[str, Any] | None = None
    assert process.stdout is not None
    for line in process.stdout:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("type") == "status" and on_status:
            on_status(str(message.get("message", "")))
        elif message.get("type") == "result":
            result = message["data"]

    stderr = process.stderr.read() if process.stderr else ""
    return_code = process.wait()
    if return_code != 0:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else "不明なエラー"
        raise RuntimeError(detail)
    if result is None:
        raise RuntimeError("文字起こし結果を取得できませんでした。")
    return format_transcript(result, gap_seconds)
