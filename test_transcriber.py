from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from transcriber import Segment, render_srt, render_txt, render_vtt, write_outputs


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.segments = [
            Segment(0.0, 1.25, "Olá mundo."),
            Segment(61.5, 63.0, "Segundo trecho."),
        ]

    def test_txt(self):
        self.assertEqual(render_txt(self.segments), "Olá mundo.\nSegundo trecho.\n")

    def test_srt_timestamps(self):
        output = render_srt(self.segments)
        self.assertIn("00:00:00,000 --> 00:00:01,250", output)
        self.assertIn("00:01:01,500 --> 00:01:03,000", output)

    def test_vtt_header_and_timestamps(self):
        output = render_vtt(self.segments)
        self.assertTrue(output.startswith("WEBVTT"))
        self.assertIn("00:00:00.000 --> 00:00:01.250", output)

    def test_write_outputs(self):
        with TemporaryDirectory() as directory:
            target = Path(directory)
            write_outputs(target, "amostra", self.segments, {"offline_policy": "local_files_only"})
            for suffix in ("txt", "srt", "vtt", "json"):
                self.assertTrue((target / f"amostra.{suffix}").is_file())
            payload = json.loads((target / "amostra.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["segments"]), 2)


if __name__ == "__main__":
    unittest.main()
