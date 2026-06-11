import subprocess
import unittest
from unittest.mock import MagicMock, patch

from transcription import extract_segments, format_transcript, run_transcription, worker_path


class TranscriptFormattingTests(unittest.TestCase):
    def test_inserts_separator_when_gap_meets_threshold(self):
        result = {
            "chunks": [
                {"text": "こんにちは", "timestamp": [0.0, 1.0]},
                {"text": "世界", "timestamp": [1.5, 2.0]},
                {"text": "です", "timestamp": [2.2, 2.8]},
            ]
        }
        self.assertEqual(format_transcript(result, 0.5), "こんにちは/世界です")

    def test_merges_and_sorts_speaker_chunks(self):
        result = {
            "chunks/SPEAKER_00": [{"text": "後", "timestamp": [2.0, 3.0]}],
            "chunks/SPEAKER_01": [{"text": "先", "timestamp": [0.0, 1.0]}],
        }
        self.assertEqual(
            extract_segments(result),
            [
                {"start": 0.0, "end": 1.0, "text": "先"},
                {"start": 2.0, "end": 3.0, "text": "後"},
            ],
        )
        self.assertEqual(format_transcript(result, 0.5), "先/後")

    def test_prefers_speaker_chunks_over_duplicate_regular_chunks(self):
        result = {
            "chunks": [{"text": "同じ文章", "timestamp": [0.0, 1.0]}],
            "chunks/SPEAKER_00": [
                {"text": "同じ文章", "timestamp": [0.0, 1.0]},
                {"text": "次の文章", "timestamp": [1.2, 2.0]},
            ],
        }
        self.assertEqual(format_transcript(result, 0.5), "同じ文章次の文章")

    def test_removes_exact_duplicate_speaker_chunks(self):
        result = {
            "chunks/SPEAKER_00": [{"text": "重複", "timestamp": [0.0, 1.0]}],
            "chunks/SPEAKER_01": [{"text": "重複", "timestamp": [0.0, 1.0]}],
        }
        self.assertEqual(format_transcript(result, 0.5), "重複")

    def test_falls_back_to_plain_text(self):
        self.assertEqual(format_transcript({"text": "全文です"}, 0.5), "全文です")


class WorkerErrorTests(unittest.TestCase):
    @patch("transcription.sys")
    def test_frozen_worker_is_next_to_executable(self, mocked_sys: MagicMock):
        mocked_sys.frozen = True
        mocked_sys.executable = r"C:\App\AutoVoiceClipper.exe"
        self.assertEqual(str(worker_path()), r"C:\App\transcribe_worker.py")

    @patch("transcription.subprocess.Popen")
    def test_uses_utf8_device_and_structured_worker_error(self, popen: MagicMock):
        process = popen.return_value
        process.stdout = iter(['{"type":"error","message":"必要なパッケージがありません"}\n'])
        process.wait.return_value = 1

        with self.assertRaisesRegex(RuntimeError, "必要なパッケージがありません"):
            run_transcription("python.exe", "audio.mp3", "model", 0.5)

        command = popen.call_args.args[0]
        self.assertIn("--device", command)
        self.assertIn("--output-root", command)
        environment = popen.call_args.kwargs["env"]
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(environment["PYTHONUTF8"], "1")
        self.assertEqual(environment["PYTHONWARNINGS"], "ignore")
        self.assertNotIn("HF_HUB_OFFLINE", environment)

    @patch("transcription.subprocess.Popen")
    def test_streams_logs_and_reports_auth_status(self, popen: MagicMock):
        process = popen.return_value
        process.stdout = iter(
            [
                "requesting https://huggingface.co/pyannote/speaker-diarization-3.1\n",
                '{"type":"error","message":"認証が必要です"}\n',
            ]
        )
        process.wait.return_value = 1
        logs = []
        statuses = []

        with self.assertRaisesRegex(RuntimeError, "認証が必要です"):
            run_transcription(
                "python.exe", "audio.mp3", "model", 0.5, statuses.append, logs.append
            )

        self.assertIn("huggingface.co/pyannote", logs[0])
        self.assertTrue(statuses)
        self.assertEqual(popen.call_args.kwargs["stderr"], subprocess.STDOUT)

    @patch("transcription.subprocess.Popen")
    def test_returns_transcript_and_exported_files(self, popen: MagicMock):
        process = popen.return_value
        process.stdout = iter(
            [
                '{"type":"result","data":{"transcription":{"chunks":[{"text":"セリフ","timestamp":[0,1]}]},"output_dir":"output/260610_2100","files":["output/260610_2100/セリフ.mp3"]}}\n'
            ]
        )
        process.wait.return_value = 0

        result = run_transcription("python.exe", "audio.mp3", "model", 0.5)

        self.assertEqual(result["text"], "セリフ")
        self.assertEqual(result["output_dir"], "output/260610_2100")
        self.assertEqual(result["files"], ["output/260610_2100/セリフ.mp3"])


if __name__ == "__main__":
    unittest.main()
