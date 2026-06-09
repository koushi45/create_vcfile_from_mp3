from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from transcription import MODEL_ID, run_transcription


class TranscriptionThread(QThread):
    status = Signal(str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self, python_executable: str, audio_path: str, model: str, gap_seconds: float
    ) -> None:
        super().__init__()
        self.python_executable = python_executable
        self.audio_path = audio_path
        self.model = model
        self.gap_seconds = gap_seconds

    def run(self) -> None:
        try:
            text = run_transcription(
                self.python_executable,
                self.audio_path,
                self.model,
                self.gap_seconds,
                self.status.emit,
            )
            self.completed.emit(text)
        except Exception as error:
            self.failed.emit(str(error))


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(180)
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
        self.setWindowTitle("自動音声切り抜きアプリ")
        self.resize(920, 760)
        self.setMinimumSize(720, 620)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 28, 36, 30)
        layout.setSpacing(18)

        title = QLabel("自動音声切り抜きアプリ")
        title.setObjectName("title")
        subtitle = QLabel("ローカルのKotoba-Whisper v2.2で、日本語音声をすばやく文字に。")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.select_audio)
        layout.addWidget(self.drop_zone)

        self.file_label = QLabel("ファイルが選択されていません")
        self.file_label.setObjectName("fileLabel")
        layout.addWidget(self.file_label)

        options = QHBoxLayout()
        gap_label = QLabel("セリフ間隔")
        self.gap_input = QDoubleSpinBox()
        self.gap_input.setRange(0.0, 60.0)
        self.gap_input.setDecimals(1)
        self.gap_input.setSingleStep(0.1)
        self.gap_input.setValue(float(self.settings.value("gap", 0.5)))
        self.gap_input.setSuffix(" 秒以上で / を挿入")
        self.python_input = QLineEdit(
            str(self.settings.value("python", self._default_python()))
        )
        self.python_input.setPlaceholderText("Kotoba-Whisper環境の python.exe")
        python_button = QPushButton("Pythonを選択")
        python_button.setObjectName("secondaryButton")
        python_button.clicked.connect(self.choose_python)
        options.addWidget(gap_label)
        options.addWidget(self.gap_input, 1)
        options.addSpacing(12)
        options.addWidget(self.python_input, 2)
        options.addWidget(python_button)
        layout.addLayout(options)

        model_row = QHBoxLayout()
        model_label = QLabel("モデル")
        self.model_input = QLineEdit(str(self.settings.value("model", MODEL_ID)))
        self.model_input.setPlaceholderText("モデルID または ローカルモデルフォルダ")
        model_button = QPushButton("フォルダを選択")
        model_button.setObjectName("secondaryButton")
        model_button.clicked.connect(self.choose_model)
        model_row.addWidget(model_label)
        model_row.addWidget(self.model_input, 1)
        model_row.addWidget(model_button)
        layout.addLayout(model_row)

        action_row = QHBoxLayout()
        self.status_label = QLabel("MP3を選択してください")
        self.status_label.setObjectName("muted")
        self.transcribe_button = QPushButton("文字起こしを開始")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.clicked.connect(self.start_transcription)
        action_row.addWidget(self.status_label, 1)
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
        self.transcript.setPlaceholderText("文字起こし結果はここに表示され、自由に編集できます。")
        layout.addWidget(transcript_label)
        layout.addWidget(self.transcript, 1)

    def _default_python(self) -> str:
        if not getattr(sys, "frozen", False):
            return sys.executable
        return shutil.which("python") or ""

    def select_audio(self, path: str) -> None:
        self.audio_path = path
        self.file_label.setText(f"選択中: {Path(path).name}")
        self.status_label.setText("文字起こしの準備ができました")
        self.transcribe_button.setEnabled(True)

    def choose_python(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Python実行ファイルを選択", "", "Python (python.exe);;Executable (*.exe)"
        )
        if path:
            self.python_input.setText(path)

    def choose_model(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "ローカルモデルフォルダを選択")
        if path:
            self.model_input.setText(path)

    def start_transcription(self) -> None:
        python = self.python_input.text().strip()
        model = self.model_input.text().strip()
        if not python or not Path(python).is_file():
            QMessageBox.warning(
                self, "Python環境が必要です", "Kotoba-Whisperを導入したpython.exeを選択してください。"
            )
            return
        self.settings.setValue("python", python)
        self.settings.setValue("model", model)
        self.settings.setValue("gap", self.gap_input.value())
        self.transcribe_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status_label.setText("開始しています…")
        self.thread = TranscriptionThread(
            python, self.audio_path, model or MODEL_ID, self.gap_input.value()
        )
        self.thread.status.connect(self.status_label.setText)
        self.thread.completed.connect(self.transcription_completed)
        self.thread.failed.connect(self.transcription_failed)
        self.thread.start()

    def transcription_completed(self, text: str) -> None:
        self.transcript.setPlainText(text)
        self.status_label.setText("文字起こしが完了しました")
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.transcribe_button.setEnabled(True)

    def transcription_failed(self, message: str) -> None:
        self.status_label.setText("文字起こしに失敗しました")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.transcribe_button.setEnabled(True)
        QMessageBox.critical(
            self,
            "文字起こしエラー",
            f"{message}\n\nモデルがローカルに保存済みか、Python環境に必要パッケージがあるか確認してください。",
        )


STYLESHEET = """
#root { background: #0b1120; }
QLabel { color: #dbeafe; font-size: 13px; }
#title { color: #f8fafc; font-size: 28px; font-weight: 700; }
#sectionTitle, #dropTitle { color: #f8fafc; font-size: 16px; font-weight: 600; }
#muted { color: #94a3b8; }
#fileLabel { color: #7dd3fc; padding: 2px; }
#dropZone {
  background: #111b31; border: 2px dashed #3b82f6; border-radius: 18px;
}
#dropZone:hover { background: #152441; border-color: #60a5fa; }
#dropIcon {
  background: #2563eb; color: white; border-radius: 24px;
  min-width: 74px; max-width: 74px; min-height: 48px; max-height: 48px;
  font-weight: 700;
}
QLineEdit, QDoubleSpinBox, QPlainTextEdit {
  background: #111b31; color: #f8fafc; border: 1px solid #263653;
  border-radius: 9px; padding: 9px; selection-background-color: #2563eb;
}
QLineEdit:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus { border-color: #3b82f6; }
QPushButton {
  background: #2563eb; color: white; border: none; border-radius: 9px;
  padding: 10px 18px; font-weight: 600;
}
QPushButton:hover { background: #3b82f6; }
QPushButton:disabled { background: #263653; color: #64748b; }
#secondaryButton { background: #1e293b; border: 1px solid #334155; }
#secondaryButton:hover { background: #334155; }
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
