from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from clip_export import extract_segments, format_transcript

MODEL_ID = "kotoba-tech/kotoba-whisper-v2.2"


def worker_path() -> Path:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    return base / "transcribe_worker.py"


def run_transcription(
    python_executable: str,
    audio_path: str,
    model: str,
    gap_seconds: float,
    on_status: Callable[[str], None] | None = None,
    on_log: Callable[[str], None] | None = None,
    on_process: Callable[[subprocess.Popen[str]], None] | None = None,
    device: str = "cpu",
    output_root: str | None = None,
) -> dict[str, Any]:
    command = [
        python_executable,
        str(worker_path()),
        "--audio",
        audio_path,
        "--model",
        model,
        "--device",
        device,
        "--gap",
        str(gap_seconds),
        "--output-root",
        output_root or str(worker_path().parent / "output"),
    ]
    env = os.environ.copy()
    env.pop("HF_HUB_OFFLINE", None)
    env.pop("TRANSFORMERS_OFFLINE", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONWARNINGS"] = "ignore"
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if on_process:
        on_process(process)

    result: dict[str, Any] | None = None
    worker_error = ""
    assert process.stdout is not None
    for line in process.stdout:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            if on_log and line.strip():
                on_log(line.rstrip())
            lowered = line.lower()
            if on_status and (
                "gatedrepoerror" in lowered
                or "401" in lowered
                or "403" in lowered
                or "huggingface.co/pyannote" in lowered
            ):
                on_status("Hugging Face認証とPyAnnoteモデルの利用規約を確認してください")
            continue
        if message.get("type") == "status" and on_status:
            on_status(str(message.get("message", "")))
        elif message.get("type") == "result":
            result = message["data"]
        elif message.get("type") == "error":
            worker_error = str(message.get("message", ""))
        elif message.get("type") == "log" and on_log:
            on_log(str(message.get("message", "")))

    return_code = process.wait()
    if return_code != 0:
        if worker_error:
            raise RuntimeError(worker_error)
        raise RuntimeError("文字起こし処理が異常終了しました。実行ログを確認してください。")
    if result is None:
        raise RuntimeError("文字起こし結果を取得できませんでした。")
    return {
        "text": format_transcript(result["transcription"], gap_seconds),
        "output_dir": str(result["output_dir"]),
        "files": list(result["files"]),
    }
