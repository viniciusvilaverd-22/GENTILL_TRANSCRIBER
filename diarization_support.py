from __future__ import annotations

from pathlib import Path


class DiarizationUnavailable(RuntimeError):
    pass


def is_available() -> bool:
    try:
        import pyannote.audio  # noqa: F401
    except Exception:
        return False
    return True


def diarize_local(audio_path: Path, pipeline_path: Path) -> list[tuple[float, float, str]]:
    """Run a locally provisioned pyannote.audio pipeline. No model download is initiated here."""
    if not pipeline_path.exists():
        raise DiarizationUnavailable(f"Pipeline local de diarização não encontrado: {pipeline_path}")

    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise DiarizationUnavailable(
            "Diarização requer pyannote.audio instalado separadamente."
        ) from exc

    try:
        pipeline = Pipeline.from_pretrained(str(pipeline_path))
    except Exception as exc:
        raise DiarizationUnavailable(
            "Não foi possível carregar o pipeline local de diarização."
        ) from exc

    result = pipeline(str(audio_path))
    turns: list[tuple[float, float, str]] = []
    for turn, _, speaker in result.itertracks(yield_label=True):
        turns.append((float(turn.start), float(turn.end), str(speaker)))
    return turns
