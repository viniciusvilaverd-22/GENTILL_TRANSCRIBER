@echo off
setlocal
cd /d "%~dp0"
set "LOG=.gentill\release-build-windows-lite.log"

> "%LOG%" echo BUILD_WINDOWS_LITE_START

if not exist ".venv\Scripts\python.exe" (
  >>"%LOG%" echo VENV=FAIL
  exit /b 1
)

".venv\Scripts\python.exe" generate_icon.py >>"%LOG%" 2>&1
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.in -r requirements-runtime-compat.txt -r requirements-build.txt >>"%LOG%" 2>&1
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m unittest -v test_transcriber.py test_transcriber_e2e.ValidationTests test_product_features.py >>"%LOG%" 2>&1
if errorlevel 1 exit /b 1

if exist "dist-lite" rmdir /s /q "dist-lite"
if exist "build-lite" rmdir /s /q "build-lite"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist-lite" --workpath "build-lite" "gentill_transcriber_lite.spec" >>"%LOG%" 2>&1
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" sign_windows.py "dist-lite\Gentill Transcriber Lite\Gentill Transcriber Lite.exe" >>"%LOG%" 2>&1
if errorlevel 1 exit /b 1

>>"%LOG%" echo BUILD_WINDOWS_LITE=PASS
echo BUILD_WINDOWS_LITE=PASS
echo Executavel: dist-lite\Gentill Transcriber Lite\Gentill Transcriber Lite.exe
pause
