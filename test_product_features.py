from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from diagnostics import realtime_factor
from history_store import HistoryStore
from transcriber import Segment, TranscriptionCancelled, apply_speaker_turns, write_outputs


class ProductFeatureTests(unittest.TestCase):
    def test_speaker_assignment_uses_greatest_overlap(self):
        segments = [
            Segment(0.0, 2.0, "primeiro"),
            Segment(2.0, 4.0, "segundo"),
        ]
        turns = [
            (0.0, 1.8, "Falante 1"),
            (1.8, 4.0, "Falante 2"),
        ]
        result = apply_speaker_turns(segments, turns)
        self.assertEqual(result[0].speaker, "Falante 1")
        self.assertEqual(result[1].speaker, "Falante 2")

    def test_docx_export(self):
        with TemporaryDirectory() as directory:
            target = Path(directory)
            written = write_outputs(
                target,
                "teste",
                [Segment(0.0, 1.0, "Olá", "Falante 1")],
                {"input": "teste.wav", "language": "pt", "model": "small"},
                formats={"docx"},
            )
            self.assertEqual([path.suffix for path in written], [".docx"])
            self.assertTrue((target / "teste.docx").is_file())

    def test_history_store_is_local_and_minimal(self):
        with TemporaryDirectory() as directory:
            store = HistoryStore(Path(directory) / "history.sqlite3")
            store.add(
                input_path=Path("entrada.wav"),
                output_dir=Path("saida"),
                model=Path("modelo"),
                language="pt",
                duration=10.0,
                elapsed=5.0,
                status="PASS",
            )
            rows = store.recent()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].status, "PASS")
            self.assertAlmostEqual(realtime_factor(rows[0].duration, rows[0].elapsed), 2.0)

    def test_cancel_event_contract(self):
        from transcriber import transcribe
        with TemporaryDirectory() as directory:
            media = Path(directory) / "x.wav"
            media.write_bytes(b"RIFF")
            event = threading.Event()
            event.set()
            with self.assertRaises(TranscriptionCancelled):
                transcribe(
                    media,
                    Path(directory),
                    "pt",
                    "cpu",
                    "int8",
                    cancel_event=event,
                )


if __name__ == "__main__":
    unittest.main()
