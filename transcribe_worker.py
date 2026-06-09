from __future__ import annotations

import argparse
import json
import sys


def emit(message_type: str, **payload: object) -> None:
    print(
        json.dumps({"type": message_type, **payload}, ensure_ascii=False),
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    emit("status", message="Kotoba-Whisper v2.2を読み込んでいます…")
    try:
        import torch
        from transformers import pipeline
    except ImportError as error:
        raise RuntimeError(
            "指定したPython環境に torch と transformers をインストールしてください。"
        ) from error

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    model_kwargs = {"attn_implementation": "sdpa"} if torch.cuda.is_available() else {}

    pipe = pipeline(
        model=args.model,
        torch_dtype=torch_dtype,
        device=device,
        model_kwargs=model_kwargs,
        batch_size=8,
        trust_remote_code=True,
        local_files_only=True,
    )
    emit("status", message=f"文字起こし中（{device}）…")
    result = pipe(args.audio, chunk_length_s=15)
    emit("result", data=result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise
