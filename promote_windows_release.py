from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RC_ROOT = ROOT / "dist-rc"
DIST_ROOT = ROOT / "dist"
RC_BUNDLE = RC_ROOT / "Gentill Transcriber"
RC_MANIFEST = RC_ROOT / "RELEASE_MANIFEST_windows.json"
DIST_BUNDLE = DIST_ROOT / "Gentill Transcriber"
DIST_MANIFEST = DIST_ROOT / "RELEASE_MANIFEST_windows.json"


def main() -> int:
    if not RC_BUNDLE.is_dir() or not RC_MANIFEST.is_file():
        raise RuntimeError("RC validado ausente")

    manifest = json.loads(RC_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("startup_smoke") != "PASS":
        raise RuntimeError("RC sem startup smoke PASS")
    if manifest.get("packaged_transcription_e2e", {}).get("status") != "PASS":
        raise RuntimeError("RC sem packaged transcription E2E PASS")
    if manifest.get("icon", {}).get("resource_validation", {}).get("status") != "PASS":
        raise RuntimeError("RC sem validação de ícone PASS")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = ROOT / ".gentill" / "release-backups" / f"windows-{stamp}"
    backup_root.mkdir(parents=True, exist_ok=False)

    if DIST_BUNDLE.exists():
        shutil.copytree(DIST_BUNDLE, backup_root / "Gentill Transcriber")
    if DIST_MANIFEST.is_file():
        shutil.copy2(DIST_MANIFEST, backup_root / DIST_MANIFEST.name)

    temp_bundle = DIST_ROOT / ".Gentill Transcriber.promoting"
    if temp_bundle.exists():
        shutil.rmtree(temp_bundle)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copytree(RC_BUNDLE, temp_bundle)
        if DIST_BUNDLE.exists():
            shutil.rmtree(DIST_BUNDLE)
        temp_bundle.replace(DIST_BUNDLE)
        final_manifest = json.loads(RC_MANIFEST.read_text(encoding="utf-8"))
        final_manifest["bundle"] = str(DIST_BUNDLE)
        final_manifest["executable"]["path"] = str(DIST_BUNDLE / "Gentill Transcriber.exe")
        final_manifest["model"]["path"] = str(
            DIST_BUNDLE / "_internal" / "models" / "whisper-small-ct2" / "model.bin"
        )
        DIST_MANIFEST.write_text(
            json.dumps(final_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        if temp_bundle.exists():
            shutil.rmtree(temp_bundle, ignore_errors=True)
        backup_bundle = backup_root / "Gentill Transcriber"
        if backup_bundle.exists():
            if DIST_BUNDLE.exists():
                shutil.rmtree(DIST_BUNDLE, ignore_errors=True)
            shutil.copytree(backup_bundle, DIST_BUNDLE)
        backup_manifest = backup_root / DIST_MANIFEST.name
        if backup_manifest.is_file():
            shutil.copy2(backup_manifest, DIST_MANIFEST)
        raise

    print(f"RELEASE_PROMOTE=PASS backup={backup_root}")
    print(f"EXECUTABLE={DIST_BUNDLE / 'Gentill Transcriber.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
