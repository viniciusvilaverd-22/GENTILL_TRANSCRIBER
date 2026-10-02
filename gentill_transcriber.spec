# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPEC).resolve().parent

datas = [
    (str(ROOT / "models" / "whisper-small-ct2"), "models/whisper-small-ct2"),
    (str(ROOT / "assets" / "gentill_transcriber.ico"), "assets"),
]
binaries = []
hiddenimports = []

for package in ("faster_whisper", "ctranslate2", "huggingface_hub", "av"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    ["transcriber_gui.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="Gentill Transcriber",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "assets" / "gentill_transcriber.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Gentill Transcriber",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Gentill Transcriber.app",
        bundle_identifier="com.gentillops.transcriber",
        info_plist={
            "CFBundleDisplayName": "Gentill Transcriber",
            "CFBundleName": "Gentill Transcriber",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15",
        },
    )
