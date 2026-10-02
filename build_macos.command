#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BUILD_VENV=".venv-build"
MODEL_DIR="models/whisper-small-ct2"
APP_BUNDLE="dist/Gentill Transcriber.app"
APP_EXEC="$APP_BUNDLE/Contents/MacOS/Gentill Transcriber"

echo "MACOS_BUILD_HOST=$(uname -s) ARCH=$(uname -m)"

"$PYTHON_BIN" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/python" -c 'import tkinter; print("TKINTER=PASS")'
"$BUILD_VENV/bin/python" -m pip install --disable-pip-version-check -r requirements.in -r requirements-runtime-compat.txt -r requirements-build.txt
"$BUILD_VENV/bin/python" generate_icon.py

if [ ! -f "$MODEL_DIR/model.bin" ]; then
  echo "Provisionando modelo local Systran/faster-whisper-small..."
  mkdir -p "$MODEL_DIR"
  "$BUILD_VENV/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Systran/faster-whisper-small",
    local_dir="models/whisper-small-ct2",
)
PY
fi

test -f "$MODEL_DIR/model.bin"
echo "MODEL=PASS"

echo
echo "=== QA PRE-BUILD ==="
"$BUILD_VENV/bin/python" -m unittest -v test_transcriber.py test_transcriber_e2e.py

echo
echo "=== BUILD ==="
"$BUILD_VENV/bin/python" -m PyInstaller --noconfirm --clean gentill_transcriber.spec

test -d "$APP_BUNDLE"
test -x "$APP_EXEC"
echo "APP_BUNDLE=PASS"
file "$APP_EXEC"

echo
echo "=== VERIFY RELEASE ==="
"$BUILD_VENV/bin/python" verify_release.py --platform macos

echo
echo "BUILD_MACOS=PASS"
echo "Aplicativo: $APP_BUNDLE"
echo "Manifesto: dist/RELEASE_MANIFEST_macos.json"
