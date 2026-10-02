# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPEC).resolve().parent

a = Analysis(
    ["uninstaller_windows.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "assets" / "gentill_transcriber.ico"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Gentill Transcriber Uninstall",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "gentill_transcriber.ico"),
)
