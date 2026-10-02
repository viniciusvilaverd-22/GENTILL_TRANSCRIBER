from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import winreg
from pathlib import Path


APP_NAME = "Gentill Transcriber"


def _remove_shortcuts() -> None:
    paths = [
        Path(os.environ.get("APPDATA", Path.home())) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME,
        Path.home() / "Desktop" / f"{APP_NAME}.lnk",
    ]
    for path in paths:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def _unregister() -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\GentillTranscriber"
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass


def cleanup(target: Path) -> int:
    time.sleep(1.0)
    _remove_shortcuts()
    _unregister()
    shutil.rmtree(target, ignore_errors=False)
    print("UNINSTALL=PASS")
    return 0


def launch_cleanup(target: Path) -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="gentill-uninstall-"))
    helper = temp_dir / "Gentill Transcriber Uninstall.exe"
    shutil.copy2(Path(sys.executable), helper)
    subprocess.Popen(
        [str(helper), "--cleanup", str(target)],
        cwd=str(temp_dir),
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", type=Path)
    args = parser.parse_args()
    if args.cleanup:
        return cleanup(args.cleanup)
    return launch_cleanup(Path(sys.executable).resolve().parent)


if __name__ == "__main__":
    raise SystemExit(main())
