import unittest

from transcription import extract_segments, format_transcript


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
            "chunks/SPEAKER_00": [
                {"text": "後", "timestamp": [2.0, 3.0]},
            ],
            "chunks/SPEAKER_01": [
                {"text": "先", "timestamp": [0.0, 1.0]},
            ],
        }
        self.assertEqual(
            extract_segments(result),
            [
                {"start": 0.0, "end": 1.0, "text": "先"},
                {"start": 2.0, "end": 3.0, "text": "後"},
            ],
        )
        self.assertEqual(format_transcript(result, 0.5), "先/後")

    def test_falls_back_to_plain_text(self):
        self.assertEqual(format_transcript({"text": "全文です"}, 0.5), "全文です")


if __name__ == "__main__":
    unittest.main()
