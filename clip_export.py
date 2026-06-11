from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
JST = timezone(timedelta(hours=9), name="Asia/Tokyo")


def extract_segments(result: dict[str, Any]) -> list[dict[str, Any]]:
    speaker_chunks: list[dict[str, Any]] = []
    for key, value in result.items():
        if key.startswith("chunks/") and isinstance(value, list):
            speaker_chunks.extend(value)
    raw_chunks = result.get("chunks")
    chunks = speaker_chunks if speaker_chunks else raw_chunks if isinstance(raw_chunks, list) else []

    normalized = []
    for chunk in chunks:
        timestamp = chunk.get("timestamp") or chunk.get("timestamps")
        if not isinstance(timestamp, (list, tuple)) or len(timestamp) < 2:
            continue
        start, end = timestamp[0], timestamp[1]
        text = str(chunk.get("text", "")).strip()
        if start is not None and end is not None and text:
            normalized.append({"start": float(start), "end": float(end), "text": text})
    normalized.sort(key=lambda item: (item["start"], item["end"]))

    unique = []
    seen: set[tuple[float, float, str]] = set()
    for segment in normalized:
        key = (segment["start"], segment["end"], segment["text"])
        if key not in seen:
            seen.add(key)
            unique.append(segment)
    return unique


def group_dialogues(result: dict[str, Any], gap_seconds: float) -> list[dict[str, Any]]:
    segments = extract_segments(result)
    if not segments:
        return []
    groups = [dict(segments[0])]
    for segment in segments[1:]:
        current = groups[-1]
        if segment["start"] - current["end"] >= gap_seconds:
            groups.append(dict(segment))
        else:
            current["end"] = max(current["end"], segment["end"])
            current["text"] += segment["text"]
    return groups


def format_transcript(result: dict[str, Any], gap_seconds: float) -> str:
    groups = group_dialogues(result, gap_seconds)
    if groups:
        return "/".join(group["text"] for group in groups)
    return str(result.get("text", "")).strip()


def safe_filename(text: str, fallback_index: int) -> str:
    name = INVALID_FILENAME.sub("_", text).strip().rstrip(". ")
    name = re.sub(r"\s+", " ", name)[:100].rstrip(". ")
    if not name or name.upper() in RESERVED_NAMES:
        name = f"セリフ_{fallback_index:03d}"
    return name


def create_output_dir(output_root: str | Path, now: datetime | None = None) -> Path:
    timestamp = now or datetime.now(JST)
    output_dir = Path(output_root) / timestamp.strftime("%y%m%d_%H%M")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def export_dialogue_clips(
    audio_path: str,
    result: dict[str, Any],
    gap_seconds: float,
    output_root: str,
) -> tuple[Path, list[Path]]:
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise RuntimeError(
            "MP3切り出し用のimageio-ffmpegがありません。setup-kotoba.cmdを再実行してください。"
        ) from error

    groups = group_dialogues(result, gap_seconds)
    if not groups:
        raise RuntimeError("音声切り出しに必要なタイムスタンプを取得できませんでした。")

    output_dir = create_output_dir(output_root)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    used_names: dict[str, int] = {}
    files = []
    for index, group in enumerate(groups, 1):
        base_name = safe_filename(group["text"], index)
        used_names[base_name] = used_names.get(base_name, 0) + 1
        count = used_names[base_name]
        suffix = f"_{count}" if count > 1 else ""
        output_path = output_dir / f"{base_name}{suffix}.mp3"
        while output_path.exists():
            count += 1
            used_names[base_name] = count
            output_path = output_dir / f"{base_name}_{count}.mp3"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{group['start']:.3f}",
                "-t",
                f"{group['end'] - group['start']:.3f}",
                "-i",
                audio_path,
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(output_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        files.append(output_path)
    return output_dir, files
