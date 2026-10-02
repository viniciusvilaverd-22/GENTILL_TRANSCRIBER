from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path, required=True)
    args = parser.parse_args()

    installer = args.installer
    if not installer.is_file():
        raise FileNotFoundError(installer)

    completed = subprocess.run([str(installer), "--self-test"], timeout=120, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Installer self-test falhou: exit_code={completed.returncode}")

    try:
        import pefile
    except ImportError as exc:
        raise RuntimeError("pefile ausente") from exc

    pe = pefile.PE(str(installer), fast_load=False)
    try:
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
        )
        root = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
        icon = group = 0
        if root:
            for entry in root.entries:
                if entry.id == 3:
                    icon = len(getattr(entry.directory, "entries", []))
                elif entry.id == 14:
                    group = len(getattr(entry.directory, "entries", []))
        if icon < 1 or group < 1:
            raise RuntimeError("Installer sem recursos de ícone válidos")
    finally:
        pe.close()

    print("INSTALLER_VERIFY=PASS")
    print(f"INSTALLER_SHA256={sha256(installer)}")
    print(f"INSTALLER_BYTES={installer.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
