# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPEC).resolve().parent

datas = [
    (str(ROOT / "dist" / "Gentill Transcriber"), "payload/Gentill Transcriber"),
    (str(ROOT / "dist-installer-tools" / "Gentill Transcriber Uninstall.exe"), "tools"),
    (str(ROOT / "assets" / "gentill_transcriber.ico"), "assets"),
]

a = Analysis(
    ["installer_windows.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["win32com.client", "pythoncom", "pywintypes"],
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
    name="Gentill Transcriber Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "gentill_transcriber.ico"),
)
