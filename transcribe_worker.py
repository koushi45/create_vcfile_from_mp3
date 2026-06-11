from __future__ import annotations

import argparse
import json
import os
import sys
import warnings


def emit(message_type: str, **payload: object) -> None:
    print(json.dumps({"type": message_type, **payload}, ensure_ascii=False), flush=True)


def friendly_pipeline_error(error: Exception) -> RuntimeError:
    lowered = str(error).lower()
    if "all_tied_weights_keys" in lowered:
        message = "Transformers 5.xとの互換性問題です。setup-kotoba.cmdを再実行してください。"
    elif "diarizeoutput" in lowered and "labels" in lowered:
        message = "PyAnnote 4.xとの互換性問題です。setup-kotoba.cmdを再実行してください。"
    elif "audiometadata" in lowered:
        message = "PyTorchとTorchAudioの互換性問題です。setup-kotoba.cmdを再実行してください。"
    elif "speechbrain.integrations.k2_fsa" in lowered:
        message = "SpeechBrainの互換性問題です。setup-kotoba.cmdを再実行してください。"
    elif "np.nan" in lowered and "removed" in lowered:
        message = "NumPy 2.xとの互換性問題です。setup-kotoba.cmdを再実行してください。"
    elif "gated repo" in lowered or "401" in lowered or "403" in lowered:
        message = "Hugging Face認証またはPyAnnote利用規約への同意が必要です。\n設定画面からtokenを再入力してください。"
    elif "cannot find the requested files in the local cache" in lowered or "trying to locate the file on the hub" in lowered:
        message = "必要なモデルを取得できませんでした。ネットワーク接続とHugging Face認証を確認してください。"
    else:
        return RuntimeError(str(error))
    return RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--gap", type=float, required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    emit("status", message="Kotoba-Whisperを読み込んでいます...")
    warnings.filterwarnings("ignore", category=UserWarning, module=r"pyannote\.audio\.core\.io")
    try:
        import torch
        from transformers import pipeline
    except ImportError as error:
        raise RuntimeError(
            f"Python環境のパッケージを読み込めませんでした。\n詳細: {error}\n"
            "setup-kotoba.cmdを再実行してください。"
        ) from error

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "GPUが選択されていますが、CUDA対応GPUを利用できません。\n"
            "設定画面でCPUを選択するか、CUDA対応版PyTorchとGPUドライバーを確認してください。"
        )
    device = "cuda:0" if args.device == "cuda" else "cpu"
    torch_dtype = torch.float16 if args.device == "cuda" else torch.float32
    model_kwargs = {"attn_implementation": "sdpa"} if args.device == "cuda" else {}

    emit("status", message="モデルを確認・ダウンロードしています...")
    emit("log", message=f"処理デバイス: {device}")
    try:
        pipe = pipeline(
            model=args.model,
            dtype=torch_dtype,
            device=device,
            model_kwargs=model_kwargs,
            batch_size=8,
            trust_remote_code=True,
        )
    except Exception as error:
        raise friendly_pipeline_error(error) from error

    emit("status", message=f"文字起こし中 ({device})...")
    emit("log", message=f"音声ファイル: {os.path.basename(args.audio)}")
    result = pipe(args.audio, chunk_length_s=15)
    emit("status", message="セリフごとのMP3を出力しています...")
    from clip_export import export_dialogue_clips

    output_dir, files = export_dialogue_clips(
        args.audio, result, args.gap, args.output_root
    )
    emit("log", message=f"音声出力先: {output_dir}")
    emit(
        "result",
        data={
            "transcription": result,
            "output_dir": str(output_dir),
            "files": [str(path) for path in files],
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        emit("error", message=str(error))
        raise SystemExit(1)
