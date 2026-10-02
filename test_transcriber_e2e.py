from pathlib import Path
from tempfile import TemporaryDirectory
import math
import struct
import unittest
import wave

from transcriber import transcribe


APP_DIR = Path(__file__).resolve().parent
MODEL_DIR = APP_DIR / "models" / "whisper-small-ct2"


class ValidationTests(unittest.TestCase):
    def test_rejects_unsupported_input_before_model_load(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "entrada.txt"
            path.write_text("não é mídia", encoding="utf-8")
            with self.assertRaises(ValueError):
                transcribe(
                    input_path=path,
                    model_path=MODEL_DIR,
                    language="pt",
                    device="cpu",
                    compute_type="int8",
                )

    def test_gui_module_imports_with_packaging_paths(self):
        import transcriber_gui

        self.assertEqual(transcriber_gui.DEFAULT_MODEL.name, "whisper-small-ct2")
        self.assertIn("Gentill Transcriber", str(transcriber_gui.DEFAULT_OUTPUT))
        self.assertEqual(
            transcriber_gui.ABOUT_GITHUB_URL,
            "https://github.com/viniciusvilaverd-22/GENTILL_TRANSCRIBER",
        )
        self.assertEqual(transcriber_gui.ABOUT_ORGANIZATION, "Gentill Ops")
        self.assertEqual(
            transcriber_gui.ABOUT_PIX_KEY,
            "eb608e93-1781-49fc-9a70-94cc395dcd53",
        )

    def test_pyav_open_supports_faster_whisper_metadata_errors(self):
        import av

        with TemporaryDirectory() as directory:
            path = Path(directory) / "pyav-probe.wav"
            OfflineMediaE2ETests._write_test_wav(path, seconds=0.1)
            with av.open(str(path), mode="r", metadata_errors="ignore") as container:
                self.assertIsNotNone(container)


class OfflineMediaE2ETests(unittest.TestCase):
    @staticmethod
    def _write_test_wav(path: Path, seconds: float = 1.0, sample_rate: int = 16000) -> None:
        frame_count = int(seconds * sample_rate)
        amplitude = 800
        frequency = 440.0
        frames = bytearray()
        for index in range(frame_count):
            sample = int(amplitude * math.sin(2.0 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", sample))

        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(bytes(frames))

    def test_local_model_transcribes_valid_wav_without_network(self):
        self.assertTrue((MODEL_DIR / "model.bin").is_file(), "modelo local ausente")
        with TemporaryDirectory() as directory:
            audio_path = Path(directory) / "qa-tone.wav"
            self._write_test_wav(audio_path)
            segments, metadata = transcribe(
                input_path=audio_path,
                model_path=MODEL_DIR,
                language="pt",
                device="cpu",
                compute_type="int8",
            )

            self.assertIsInstance(segments, list)
            self.assertEqual(metadata["offline_policy"], "local_files_only")
            self.assertEqual(metadata["device"], "cpu")
            self.assertEqual(metadata["compute_type"], "int8")
            self.assertEqual(Path(metadata["input"]).name, "qa-tone.wav")


if __name__ == "__main__":
    unittest.main()
