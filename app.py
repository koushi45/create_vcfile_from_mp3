from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from transcription import MODEL_ID, run_transcription


class TranscriptionThread(QThread):
    status = Signal(str)
    log = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        python_executable: str,
        audio_path: str,
        model: str,
        gap_seconds: float,
        device: str,
        output_root: str,
    ) -> None:
        super().__init__()
        self.python_executable = python_executable
        self.audio_path = audio_path
        self.model = model
        self.gap_seconds = gap_seconds
        self.device = device
        self.output_root = output_root
        self.process: subprocess.Popen[str] | None = None

    def set_process(self, process: subprocess.Popen[str]) -> None:
        self.process = process

    def cancel(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def run(self) -> None:
        try:
            result = run_transcription(
                self.python_executable,
                self.audio_path,
                self.model,
                self.gap_seconds,
                self.status.emit,
                self.log.emit,
                self.set_process,
                self.device,
                self.output_root,
            )
            self.completed.emit(result)
        except Exception as error:
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.failed.emit(str(error))


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(190)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("MP3")
        icon.setObjectName("dropIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("MP3ファイルをここにドロップ")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("または、クリックしてファイルを選択")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(hint)

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self, "MP3ファイルを選択", "", "MP3 Audio (*.mp3)"
            )
            if path:
                self.file_dropped.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".mp3"):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.file_dropped.emit(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("KotobaTools", "AutoVoiceClipper")
        self.audio_path = ""
        self.thread: TranscriptionThread | None = None
        self.current_log_path: Path | None = None
        self.setWindowTitle("自動音声切り抜きアプリ")
        self.resize(1100, 820)
        self.setMinimumSize(780, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(30, 14, 30, 14)
        brand = QLabel("自動音声切り抜きアプリ")
        brand.setObjectName("brand")
        self.process_nav = QPushButton("処理画面")
        self.settings_nav = QPushButton("設定画面")
        for button in (self.process_nav, self.settings_nav):
            button.setObjectName("navButton")
            button.setCheckable(True)
        self.process_nav.setChecked(True)
        self.process_nav.clicked.connect(lambda: self.switch_page(0))
        self.settings_nav.clicked.connect(lambda: self.switch_page(1))
        header_layout.addWidget(brand)
        header_layout.addStretch()
        header_layout.addWidget(self.process_nav)
        header_layout.addWidget(self.settings_nav)
        root_layout.addWidget(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_process_page())
        self.pages.addWidget(self._build_settings_page())
        root_layout.addWidget(self.pages, 1)

    def _scroll_page(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName("mainScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("content")
        content.setMinimumWidth(720)
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 28, 36, 32)
        layout.setSpacing(18)
        return scroll, layout

    def _build_process_page(self) -> QWidget:
        page, layout = self._scroll_page()
        title = QLabel("処理画面")
        title.setObjectName("title")
        subtitle = QLabel("MP3を選択し、ローカルのKotoba-Whisperで日本語を文字起こしします。")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        input_row = QHBoxLayout()
        input_row.setSpacing(18)
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.select_audio)
        self.drop_zone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        input_row.addWidget(self.drop_zone, 2)

        gap_card = QFrame()
        gap_card.setObjectName("card")
        gap_card.setMinimumHeight(190)
        gap_layout = QVBoxLayout(gap_card)
        gap_layout.setContentsMargins(22, 22, 22, 22)
        gap_title = QLabel("セリフ間隔")
        gap_title.setObjectName("sectionTitle")
        gap_help = QLabel("指定秒数以上の無音がある場合、セリフ間に「/」を挿入します。")
        gap_help.setObjectName("muted")
        gap_help.setWordWrap(True)
        self.gap_input = QDoubleSpinBox()
        self.gap_input.setRange(0.0, 60.0)
        self.gap_input.setDecimals(1)
        self.gap_input.setSingleStep(0.1)
        self.gap_input.setValue(float(self.settings.value("gap", 0.5)))
        self.gap_input.setSuffix(" 秒以上")
        gap_layout.addWidget(gap_title)
        gap_layout.addWidget(gap_help)
        gap_layout.addStretch()
        gap_layout.addWidget(self.gap_input)
        input_row.addWidget(gap_card, 1)
        layout.addLayout(input_row)

        self.file_label = QLabel("ファイルが選択されていません")
        self.file_label.setObjectName("fileLabel")
        layout.addWidget(self.file_label)

        action_row = QHBoxLayout()
        self.status_label = QLabel("MP3を選択してください")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        self.transcribe_button = QPushButton("文字起こしを開始")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.cancel_button = QPushButton("キャンセル")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_transcription)
        action_row.addWidget(self.status_label, 1)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.transcribe_button)
        layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        transcript_label = QLabel("文字起こし結果")
        transcript_label.setObjectName("sectionTitle")
        self.transcript = QPlainTextEdit()
        self.transcript.setMinimumHeight(260)
        self.transcript.setPlaceholderText("文字起こし結果はここに表示され、自由に編集できます。")
        layout.addWidget(transcript_label)
        layout.addWidget(self.transcript, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._scroll_page()
        title = QLabel("設定画面")
        title.setObjectName("title")
        subtitle = QLabel("文字起こしに使用する環境とモデルを設定します。")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(22, 22, 22, 22)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(18)

        self.python_input = QLineEdit(self._configured_python())
        python_button = QPushButton("Pythonを選択")
        python_button.setObjectName("secondaryButton")
        python_button.clicked.connect(self.choose_python)
        self.model_input = QLineEdit(str(self.settings.value("model", MODEL_ID)))
        model_button = QPushButton("フォルダを選択")
        model_button.setObjectName("secondaryButton")
        model_button.clicked.connect(self.choose_model)
        self.device_input = QComboBox()
        self.device_input.addItem("CPU", "cpu")
        self.device_input.addItem("GPU (CUDA)", "cuda")
        selected_device = str(self.settings.value("device", "cpu"))
        self.device_input.setCurrentIndex(max(0, self.device_input.findData(selected_device)))
        token_button = QPushButton("Hugging Face tokenを再入力")
        token_button.setObjectName("secondaryButton")
        token_button.clicked.connect(self.reenter_token)
        gpu_setup_button = QPushButton("GPU環境をセットアップ")
        gpu_setup_button.setObjectName("secondaryButton")
        gpu_setup_button.clicked.connect(self.setup_gpu)

        fields = [
            ("Python環境", self.python_input, python_button),
            ("モデル", self.model_input, model_button),
            ("処理デバイス", self.device_input, None),
            ("GPU環境", gpu_setup_button, None),
            ("Hugging Face token", token_button, None),
        ]
        for row, (label_text, field, button) in enumerate(fields):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)
            if button:
                grid.addWidget(button, row, 2)
        grid.setColumnStretch(1, 1)
        layout.addWidget(card)

        note = QLabel("token再入力を押すと、専用のセットアップ画面が開きます。実行ログはアプリと同じ場所の「log」フォルダへ保存されます。")
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        save_button = QPushButton("設定を保存")
        save_button.clicked.connect(self.save_settings)
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_row.addWidget(save_button)
        layout.addLayout(save_row)
        layout.addStretch()
        return page

    def switch_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.process_nav.setChecked(index == 0)
        self.settings_nav.setChecked(index == 1)

    def _app_dir(self) -> Path:
        return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

    def _default_python(self) -> str:
        discovered = self._find_kotoba_python()
        if discovered:
            return discovered
        if not getattr(sys, "frozen", False):
            return sys.executable
        return shutil.which("python") or ""

    def _local_kotoba_python(self) -> Path:
        return self._app_dir() / ".venv-kotoba" / "Scripts" / "python.exe"

    def _find_kotoba_python(self) -> str:
        candidates = [
            self._local_kotoba_python(),
            self._app_dir().parent / ".venv-kotoba" / "Scripts" / "python.exe",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return ""

    def _configured_python(self) -> str:
        saved = str(self.settings.value("python", "")).strip()
        if saved and Path(saved).is_file():
            return saved
        discovered = self._find_kotoba_python()
        if discovered:
            self.settings.setValue("python", discovered)
            return discovered
        return self._default_python()

    def select_audio(self, path: str) -> None:
        self.audio_path = path
        self.file_label.setText(f"選択中: {Path(path).name}")
        self.status_label.setText("文字起こしの準備ができました")
        self.transcribe_button.setEnabled(True)

    def choose_python(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Python実行ファイルを選択", "", "Python (python.exe);;Executable (*.exe)")
        if path:
            self.python_input.setText(path)

    def choose_model(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "ローカルモデルフォルダを選択")
        if path:
            self.model_input.setText(path)

    def save_settings(self, show_message: bool = True) -> None:
        self.settings.setValue("python", self.python_input.text().strip())
        self.settings.setValue("model", self.model_input.text().strip() or MODEL_ID)
        self.settings.setValue("device", self.device_input.currentData())
        self.settings.setValue("gap", self.gap_input.value())
        if show_message:
            QMessageBox.information(self, "設定", "設定を保存しました。")

    def reenter_token(self) -> None:
        self.launch_setup("setup-huggingface-login.cmd")

    def setup_gpu(self) -> None:
        self.launch_setup("setup-gpu.cmd")

    def launch_setup(self, file_name: str) -> None:
        setup_path = self._app_dir() / file_name
        if not setup_path.is_file():
            QMessageBox.warning(self, "セットアップファイルがありません", f"次のファイルが見つかりません:\n{setup_path}")
            return
        subprocess.Popen(
            ["cmd.exe", "/c", str(setup_path)],
            cwd=str(self._app_dir()),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )

    def _start_log(self) -> None:
        log_dir = self._app_dir() / "log"
        log_dir.mkdir(exist_ok=True)
        self.current_log_path = log_dir / f"transcription-{datetime.now():%Y%m%d-%H%M%S}.log"
        # The BOM lets Windows tools reliably detect UTF-8 Japanese text.
        self.current_log_path.write_text("", encoding="utf-8-sig")

    def append_log(self, message: str) -> None:
        if self.current_log_path is None:
            self._start_log()
        assert self.current_log_path is not None
        with self.current_log_path.open("a", encoding="utf-8") as log:
            log.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}\n")

    def cuda_available(self, python: str) -> tuple[bool, str]:
        try:
            check = subprocess.run(
                [
                    python,
                    "-c",
                    (
                        "import torch; "
                        "print('available=' + str(torch.cuda.is_available())); "
                        "print('torch_cuda=' + str(torch.version.cuda)); "
                        "print('devices=' + str(torch.cuda.device_count()))"
                    ),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return False, str(error)
        details = "\n".join(part for part in (check.stdout.strip(), check.stderr.strip()) if part)
        return check.returncode == 0 and "available=True" in check.stdout, details

    def start_transcription(self) -> None:
        self.save_settings(False)
        python = self.python_input.text().strip()
        model = self.model_input.text().strip() or MODEL_ID
        if not python or not Path(python).is_file():
            discovered = self._find_kotoba_python()
            if discovered:
                python = discovered
                self.python_input.setText(discovered)
                self.settings.setValue("python", discovered)
            else:
                QMessageBox.warning(
                    self,
                    "Python環境が必要です",
                    (
                        "Kotoba-Whisper用のPython環境を自動検出できませんでした。\n\n"
                        "設定画面でpython.exeを選択するか、setup-kotoba.cmdを実行してください。"
                    ),
                )
                self.switch_page(1)
                return
        if self.device_input.currentData() == "cuda":
            available, details = self.cuda_available(python)
            if not available:
                self.device_input.setCurrentIndex(self.device_input.findData("cpu"))
                self.save_settings(False)
                self.switch_page(1)
                QMessageBox.warning(
                    self,
                    "GPUを利用できません",
                    (
                        "現在のPython環境ではCUDA対応GPUを利用できません。\n"
                        "処理デバイスをCPUへ戻しました。\n\n"
                        "GPU処理にはNVIDIA CUDA対応GPU、対応ドライバー、"
                        "CUDA対応版PyTorchが必要です。設定画面の"
                        "「GPU環境をセットアップ」を実行してください。\n\n"
                        f"確認結果:\n{details or '詳細を取得できませんでした。'}"
                    ),
                )
                return
        self.current_log_path = None
        self._start_log()
        self.append_log(f"Python: {python}")
        self.append_log(f"モデル: {model}")
        self.append_log(f"処理デバイス: {self.device_input.currentData()}")
        self.transcribe_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("開始しています...")
        self.thread = TranscriptionThread(
            python,
            self.audio_path,
            model,
            self.gap_input.value(),
            str(self.device_input.currentData()),
            str(self._app_dir() / "output"),
        )
        self.thread.status.connect(self.status_label.setText)
        self.thread.log.connect(self.append_log)
        self.thread.completed.connect(self.transcription_completed)
        self.thread.failed.connect(self.transcription_failed)
        self.thread.cancelled.connect(self.transcription_cancelled)
        self.thread.start()

    def cancel_transcription(self) -> None:
        if self.thread and self.thread.isRunning():
            self.status_label.setText("キャンセルしています...")
            self.append_log("ユーザーが処理をキャンセルしました。")
            self.thread.requestInterruption()
            self.thread.cancel()
            self.cancel_button.setEnabled(False)

    def finish_transcription_ui(self) -> None:
        self.progress.setRange(0, 1)
        self.cancel_button.setVisible(False)
        self.cancel_button.setEnabled(True)
        self.transcribe_button.setEnabled(True)

    def transcription_completed(self, result: object) -> None:
        data = dict(result)  # type: ignore[arg-type]
        self.transcript.setPlainText(str(data["text"]))
        file_count = len(data["files"])
        output_dir = str(data["output_dir"])
        self.status_label.setText(f"文字起こし完了: MP3を{file_count}件出力しました")
        self.append_log(f"文字起こしが完了しました。MP3出力数: {file_count}")
        self.append_log(f"音声出力先: {output_dir}")
        self.finish_transcription_ui()
        self.progress.setValue(1)
        QMessageBox.information(
            self,
            "処理完了",
            f"文字起こしと音声切り出しが完了しました。\n\n出力先:\n{output_dir}",
        )

    def transcription_failed(self, message: str) -> None:
        self.status_label.setText("文字起こしに失敗しました")
        self.append_log(f"エラー: {message}")
        self.finish_transcription_ui()
        self.progress.setValue(0)
        QMessageBox.critical(self, "文字起こしエラー", f"{message}\n\n詳細ログ:\n{self.current_log_path}")

    def transcription_cancelled(self) -> None:
        self.status_label.setText("文字起こしをキャンセルしました")
        self.finish_transcription_ui()
        self.progress.setValue(0)


STYLESHEET = """
#root, #mainScroll, #content { background: #0b1120; }
#header { background: #111827; border-bottom: 1px solid #263653; }
QLabel { color: #dbeafe; font-size: 13px; }
#brand { color: #f8fafc; font-size: 17px; font-weight: 700; }
#title { color: #f8fafc; font-size: 28px; font-weight: 700; }
#sectionTitle, #dropTitle { color: #f8fafc; font-size: 16px; font-weight: 600; }
#muted { color: #94a3b8; }
#fileLabel { color: #7dd3fc; padding: 2px; }
#fieldLabel { color: #cbd5e1; min-width: 120px; font-weight: 600; }
#card { background: #0f192c; border: 1px solid #263653; border-radius: 14px; }
#dropZone { background: #111b31; border: 2px dashed #3b82f6; border-radius: 18px; }
#dropZone:hover { background: #152441; border-color: #60a5fa; }
#dropIcon { background: #2563eb; color: white; border-radius: 24px; min-width: 74px; max-width: 74px; min-height: 48px; max-height: 48px; font-weight: 700; }
QLineEdit, QDoubleSpinBox, QComboBox, QPlainTextEdit { background: #111b31; color: #f8fafc; border: 1px solid #263653; border-radius: 9px; padding: 9px; selection-background-color: #2563eb; }
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border-color: #3b82f6; }
QPushButton { background: #2563eb; color: white; border: none; border-radius: 9px; padding: 10px 18px; font-weight: 600; }
QPushButton:hover { background: #3b82f6; }
QPushButton:disabled { background: #263653; color: #64748b; }
#secondaryButton, #navButton { background: #1e293b; border: 1px solid #334155; }
#secondaryButton:hover, #navButton:hover { background: #334155; }
#navButton:checked { background: #2563eb; border-color: #3b82f6; }
#dangerButton { background: #9f1239; }
#dangerButton:hover { background: #be123c; }
QProgressBar { background: #172033; border: none; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #38bdf8; border-radius: 3px; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b1120"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f8fafc"))
    app.setPalette(palette)
    app.setFont(QFont("Yu Gothic UI", 10))
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
