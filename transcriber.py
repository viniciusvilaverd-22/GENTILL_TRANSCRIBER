from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


SUPPORTED_INPUTS = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".mkv", ".mov", ".webm", ".avi",
}


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


def _timestamp_srt(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _timestamp_vtt(seconds: float) -> str:
    return _timestamp_srt(seconds).replace(",", ".")


def render_txt(segments: Sequence[Segment]) -> str:
    return "\n".join(s.text.strip() for s in segments if s.text.strip()).strip() + "\n"


def render_srt(segments: Sequence[Segment]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n"
            f"{_timestamp_srt(segment.start)} --> {_timestamp_srt(segment.end)}\n"
            f"{segment.text.strip()}\n"
        )
    return "\n".join(blocks)


def render_vtt(segments: Sequence[Segment]) -> str:
    blocks = ["WEBVTT\n"]
    for segment in segments:
        blocks.append(
            f"{_timestamp_vtt(segment.start)} --> {_timestamp_vtt(segment.end)}\n"
            f"{segment.text.strip()}\n"
        )
    return "\n".join(blocks)


def write_outputs(
    output_dir: Path,
    stem: str,
    segments: Sequence[Segment],
    metadata: dict,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{stem}.txt").write_text(render_txt(segments), encoding="utf-8")
    (output_dir / f"{stem}.srt").write_text(render_srt(segments), encoding="utf-8")
    (output_dir / f"{stem}.vtt").write_text(render_vtt(segments), encoding="utf-8")
    payload = {
        "metadata": metadata,
        "segments": [asdict(segment) for segment in segments],
    }
    (output_dir / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_model(model_path: Path, device: str, compute_type: str):
    if not model_path.exists():
        raise FileNotFoundError(
            f"Modelo local não encontrado: {model_path}. "
            "O modo LAB não permite download implícito."
        )

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Dependência faster-whisper não instalada no ambiente LAB."
        ) from exc

    return WhisperModel(
        str(model_path),
        device=device,
        compute_type=compute_type,
        local_files_only=True,
    )


def transcribe(
    input_path: Path,
    model_path: Path,
    language: str | None,
    device: str,
    compute_type: str,
) -> tuple[list[Segment], dict]:
    if not input_path.is_file():
        raise FileNotFoundError(f"Entrada não encontrada: {input_path}")
    if input_path.suffix.lower() not in SUPPORTED_INPUTS:
        raise ValueError(f"Formato não permitido nesta baseline: {input_path.suffix}")

    model = load_model(model_path, device=device, compute_type=compute_type)
    raw_segments, info = model.transcribe(
        str(input_path),
        language=language,
        vad_filter=True,
        beam_size=5,
    )

    segments = [
        Segment(start=float(s.start), end=float(s.end), text=str(s.text).strip())
        for s in raw_segments
        if str(s.text).strip()
    ]

    metadata = {
        "input": str(input_path.resolve()),
        "model": str(model_path.resolve()),
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
        "device": device,
        "compute_type": compute_type,
        "offline_policy": "local_files_only",
    }
    return segments, metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gentill Transcriber LAB — offline")
    parser.add_argument("input", type=Path)
    parser.add_argument("--model", type=Path, default=Path("models/whisper-small-ct2"))
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--language", default="pt", help="Use 'auto' para autodetecção.")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "auto"])
    parser.add_argument("--compute-type", default="int8")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    language = None if args.language.lower() == "auto" else args.language.lower()

    try:
        segments, metadata = transcribe(
            input_path=args.input,
            model_path=args.model,
            language=language,
            device=args.device,
            compute_type=args.compute_type,
        )
        write_outputs(args.output, args.input.stem, segments, metadata)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1

    print(f"TRANSCRIPTION=PASS segments={len(segments)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
