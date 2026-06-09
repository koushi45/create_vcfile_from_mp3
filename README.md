# 自動音声切り抜きアプリ

MP3をドラッグ＆ドロップし、ローカル環境の
[Kotoba-Whisper v2.2](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.2)
で日本語文字起こしを行うWindowsデスクトップアプリです。

## 主な機能

- MP3のドラッグ＆ドロップ
- Kotoba-Whisper v2.2による完全ローカル文字起こし
- 文字起こし結果の編集
- 指定秒数以上の無音区間への `/` 自動挿入
- CUDA対応環境ではGPUを自動使用

## Kotoba-Whisper環境の準備

このアプリのUIと文字起こし環境は分離されています。Python 3.10～3.12の仮想環境を
用意し、必要パッケージとモデルを事前にインストールしてください。

```powershell
py -3.12 -m venv .venv-kotoba
.\.venv-kotoba\Scripts\Activate.ps1
python -m pip install -r requirements-kotoba.txt
python -c "from transformers import pipeline; pipeline(model='kotoba-tech/kotoba-whisper-v2.2', trust_remote_code=True)"
```

初回のモデル取得後、アプリは `HF_HUB_OFFLINE=1` で動作するため音声や文字起こし結果を
外部へ送信しません。アプリ画面の「Pythonを選択」から、上記環境の
`.venv-kotoba\Scripts\python.exe` を選んでください。

## ソースから起動

```powershell
python -m pip install -r requirements-ui.txt
python app.py
```

## exeをビルド

```powershell
.\build.ps1
```

完成したアプリは
`release\AutoVoiceClipper\AutoVoiceClipper.exe` に出力されます。

`release\AutoVoiceClipper` フォルダ全体が配布物です。exe単体を移動したり、
`build` や `.pyinstaller-cache` 内のexeを起動したりしないでください。
配布時は `release\AutoVoiceClipper-Windows.zip` を使用してください。
