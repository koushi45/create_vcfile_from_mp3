import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from clip_export import (
    create_output_dir,
    export_dialogue_clips,
    group_dialogues,
    safe_filename,
)


class DialogueGroupingTests(unittest.TestCase):
    def test_groups_segments_until_gap_threshold(self):
        result = {
            "chunks": [
                {"text": "よろしく", "timestamp": [0.0, 1.0]},
                {"text": "お願いね", "timestamp": [1.2, 2.0]},
                {"text": "私もまだまだね", "timestamp": [2.7, 4.0]},
            ]
        }
        self.assertEqual(
            group_dialogues(result, 0.5),
            [
                {"start": 0.0, "end": 2.0, "text": "よろしくお願いね"},
                {"start": 2.7, "end": 4.0, "text": "私もまだまだね"},
            ],
        )

    def test_creates_tokyo_timestamp_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = create_output_dir(
                temp_dir,
                datetime(2026, 6, 10, 21, 0, tzinfo=timezone(timedelta(hours=9))),
            )
            self.assertEqual(output.name, "260610_2100")
            self.assertEqual(create_output_dir(temp_dir, datetime(2026, 6, 10, 21, 0)).name, "260610_2100")

    def test_sanitizes_windows_filename(self):
        self.assertEqual(safe_filename('よろしく/お願いね:*?', 1), "よろしく_お願いね___")


class ExportTests(unittest.TestCase):
    @patch("subprocess.run")
    def test_exports_named_mp3_files(self, run):
        result = {
            "chunks": [
                {"text": "よろしくお願いね", "timestamp": [0.0, 1.0]},
                {"text": "よろしくお願いね", "timestamp": [2.0, 3.0]},
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_ffmpeg = MagicMock()
            fake_ffmpeg.get_ffmpeg_exe.return_value = "ffmpeg.exe"
            with patch.dict("sys.modules", {"imageio_ffmpeg": fake_ffmpeg}):
                output_dir, files = export_dialogue_clips(
                    "source.mp3", result, 0.5, temp_dir
                )
            self.assertEqual(
                [path.name for path in files],
                ["よろしくお願いね.mp3", "よろしくお願いね_2.mp3"],
            )
            self.assertEqual(run.call_count, 2)
            self.assertTrue(str(output_dir).startswith(temp_dir))
            self.assertIn("-ss", run.call_args_list[0].args[0])
            self.assertIn("-t", run.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()
