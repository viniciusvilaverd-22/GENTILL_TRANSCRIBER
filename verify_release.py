from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import struct
import subprocess
import tempfile
import time
import wave
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTED_MODEL_SHA256 = "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"
ICON_SOURCE = ROOT / "assets" / "gentill_transcriber.ico"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_model(bundle_root: Path) -> Path:
    matches = list(bundle_root.rglob("model.bin"))
    for candidate in matches:
        if sha256(candidate) == EXPECTED_MODEL_SHA256:
            return candidate
    raise RuntimeError("model.bin validado não encontrado no bundle")


def smoke_launch(executable: Path, seconds: float = 3.0) -> None:
    process = subprocess.Popen([str(executable)])
    try:
        time.sleep(seconds)
        code = process.poll()
        if code is not None:
            raise RuntimeError(f"aplicativo encerrou durante smoke, exit_code={code}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


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


def packaged_transcription_e2e(executable: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="gentill-transcriber-release-") as directory:
        work = Path(directory)
        audio = work / "qa-tone.wav"
        output = work / "output"
        _write_test_wav(audio)

        completed = subprocess.run(
            [
                str(executable),
                "--self-test-media",
                str(audio),
                "--self-test-output",
                str(output),
            ],
            timeout=240,
            check=False,
        )
        if completed.returncode != 0:
            error_file = output / "SELF_TEST_ERROR.txt"
            detail = (
                error_file.read_text(encoding="utf-8", errors="replace").strip()
                if error_file.is_file()
                else "sem detalhe"
            )
            raise RuntimeError(
                f"transcrição E2E do executável falhou, exit_code={completed.returncode}: {detail}"
            )

        required = {
            "json": output / "qa-tone.json",
            "txt": output / "qa-tone.txt",
            "srt": output / "qa-tone.srt",
            "vtt": output / "qa-tone.vtt",
            "docx": output / "qa-tone.docx",
        }
        for name, candidate in required.items():
            if not candidate.is_file():
                raise RuntimeError(f"saída ausente no E2E empacotado: {name}")

        payload = json.loads(required["json"].read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {})
        if metadata.get("offline_policy") != "local_files_only":
            raise RuntimeError("E2E empacotado não confirmou política offline")
        if metadata.get("device") != "cpu":
            raise RuntimeError("E2E empacotado não executou em CPU")
        if metadata.get("compute_type") != "int8":
            raise RuntimeError("E2E empacotado não executou em int8")

        return {
            "status": "PASS",
            "outputs": list(required),
            "offline_policy": metadata.get("offline_policy"),
            "device": metadata.get("device"),
            "compute_type": metadata.get("compute_type"),
        }


def verify_windows_icon(executable: Path) -> dict:
    try:
        import pefile
    except ImportError as exc:
        raise RuntimeError("pefile ausente; não é possível validar o ícone PE") from exc

    pe = pefile.PE(str(executable), fast_load=False)
    try:
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
        )
        root = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
        if root is None:
            raise RuntimeError("executável não possui diretório de recursos")

        icon_entries = 0
        group_entries = 0
        for entry in root.entries:
            if entry.id == 3:
                icon_entries = len(getattr(entry.directory, "entries", []))
            elif entry.id == 14:
                group_entries = len(getattr(entry.directory, "entries", []))

        if icon_entries < 1 or group_entries < 1:
            raise RuntimeError(
                f"recursos de ícone ausentes: RT_ICON={icon_entries}, RT_GROUP_ICON={group_entries}"
            )

        return {
            "status": "PASS",
            "rt_icon_entries": icon_entries,
            "rt_group_icon_entries": group_entries,
        }
    finally:
        pe.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--dist-root", default="dist")
    args = parser.parse_args()

    dist_root = ROOT / args.dist_root

    if args.platform == "windows":
        bundle_root = dist_root / "Gentill Transcriber"
        executable = bundle_root / "Gentill Transcriber.exe"
    else:
        bundle_root = dist_root / "Gentill Transcriber.app"
        executable = bundle_root / "Contents" / "MacOS" / "Gentill Transcriber"

    if not bundle_root.exists():
        raise RuntimeError(f"bundle ausente: {bundle_root}")
    if not executable.is_file():
        raise RuntimeError(f"executável ausente: {executable}")

    model = find_model(bundle_root)
    model_dir = model.parent
    for name in ("config.json", "tokenizer.json", "vocabulary.txt"):
        if not (model_dir / name).is_file():
            raise RuntimeError(f"arquivo de modelo ausente: {name}")

    icon_validation = None
    if args.platform == "windows":
        if not ICON_SOURCE.is_file():
            raise RuntimeError(f"ícone-fonte ausente: {ICON_SOURCE}")
        icon_validation = verify_windows_icon(executable)

    if not args.no_launch:
        smoke_launch(executable)

    packaged_e2e = packaged_transcription_e2e(executable)

    source_files = [
        "transcriber.py",
        "transcriber_gui.py",
        "history_store.py",
        "diagnostics.py",
        "model_manager.py",
        "diarization_support.py",
        "test_transcriber.py",
        "test_transcriber_e2e.py",
        "test_product_features.py",
    ]

    manifest = {
        "schema_version": 3,
        "product": "Gentill Transcriber",
        "target": args.platform,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "bundle": str(bundle_root),
        "executable": {
            "path": str(executable),
            "sha256": sha256(executable),
            "bytes": executable.stat().st_size,
        },
        "model": {
            "path": str(model),
            "sha256": sha256(model),
            "bytes": model.stat().st_size,
        },
        "icon": {
            "source": str(ICON_SOURCE) if args.platform == "windows" else None,
            "source_sha256": sha256(ICON_SOURCE) if args.platform == "windows" else None,
            "resource_validation": icon_validation,
        },
        "source": {
            name: sha256(ROOT / name)
            for name in source_files
            if (ROOT / name).is_file()
        },
        "features": {
            "drag_and_drop": True,
            "batch_queue": True,
            "pause_cancel": True,
            "real_progress": True,
            "model_manager": True,
            "docx": True,
            "local_history": True,
            "diagnostics": True,
            "diarization": "optional-local",
        },
        "offline_policy": "local_files_only",
        "startup_smoke": "SKIPPED" if args.no_launch else "PASS",
        "packaged_transcription_e2e": packaged_e2e,
    }

    manifest_path = dist_root / f"RELEASE_MANIFEST_{args.platform}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"RELEASE_VERIFY=PASS target={args.platform}")
    print("PACKAGED_TRANSCRIPTION_E2E=PASS")
    if args.platform == "windows":
        print("WINDOWS_ICON_RESOURCE=PASS")
    print(f"MANIFEST={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
