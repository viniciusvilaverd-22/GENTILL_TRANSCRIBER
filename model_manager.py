from __future__ import annotations

import os
from pathlib import Path


MODEL_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
}


def user_model_root() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path.home() / ".local" / "share"
    path = root / "Gentill Transcriber" / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def valid_model_dir(path: Path) -> bool:
    return (path / "model.bin").is_file() and (path / "config.json").is_file()


def discover_models(*roots: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        if valid_model_dir(root):
            found[root.name] = root
            continue
        for child in root.iterdir():
            if child.is_dir() and valid_model_dir(child):
                found[child.name] = child
    return found


def download_model(name: str, destination: Path | None = None) -> Path:
    key = name.lower().strip()
    if key not in MODEL_REPOS:
        raise ValueError(f"Modelo não suportado: {name}")

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub não está disponível.") from exc

    target = destination or (user_model_root() / f"whisper-{key}-ct2")
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=MODEL_REPOS[key], local_dir=str(target))
    if not valid_model_dir(target):
        raise RuntimeError("Download terminou sem os arquivos mínimos do modelo.")
    return target
