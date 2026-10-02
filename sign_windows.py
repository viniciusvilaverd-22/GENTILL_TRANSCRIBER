from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def sign_file(path: Path, thumbprint: str, timestamp_url: str | None) -> None:
    signtool = shutil.which("signtool.exe") or shutil.which("signtool")
    if not signtool:
        raise RuntimeError("signtool.exe não encontrado no PATH.")

    command = [
        signtool,
        "sign",
        "/sha1",
        thumbprint,
        "/fd",
        "SHA256",
    ]
    if timestamp_url:
        command += ["/tr", timestamp_url, "/td", "SHA256"]
    command.append(str(path))
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()

    thumbprint = os.environ.get("GENTILL_SIGN_CERT_SHA1", "").strip()
    timestamp_url = os.environ.get("GENTILL_SIGN_TIMESTAMP_URL", "").strip() or None

    if not thumbprint:
        print("WINDOWS_SIGNING=SKIPPED reason=GENTILL_SIGN_CERT_SHA1_not_configured")
        return 0

    for path in args.files:
        if not path.is_file():
            raise FileNotFoundError(path)
        sign_file(path, thumbprint, timestamp_url)
        print(f"SIGNED={path}")

    print("WINDOWS_SIGNING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
