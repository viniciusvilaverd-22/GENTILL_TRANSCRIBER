@echo off
setlocal
cd /d "%~dp0"
set "LOG=.gentill\release-build-windows-rc.log"

> "%LOG%" echo BUILD_WINDOWS_RC_START
>>"%LOG%" echo DATE=%DATE% TIME=%TIME%

if not exist ".venv\Scripts\python.exe" (
  >>"%LOG%" echo VENV=FAIL
  echo Ambiente Python nao encontrado em .venv.
  pause
  exit /b 1
)
>>"%LOG%" echo VENV=PASS

echo === ICONE ===
".venv\Scripts\python.exe" generate_icon.py >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo ICON_GENERATE=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo ICON_GENERATE=PASS

echo === DEPENDENCIAS ===
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.in -r requirements-runtime-compat.txt -r requirements-build.txt >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo DEPENDENCIES=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo DEPENDENCIES=PASS

echo === QA PRE-BUILD ===
".venv\Scripts\python.exe" -m unittest -v test_transcriber.py test_transcriber_e2e.py >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo QA_PRE_BUILD=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo QA_PRE_BUILD=PASS

echo === BUILD ===
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist-rc" --workpath "build-rc" "gentill_transcriber.spec" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo PYINSTALLER=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo PYINSTALLER=PASS

echo === VERIFY RELEASE ===
".venv\Scripts\python.exe" verify_release.py --platform windows --dist-root dist-rc >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo RELEASE_VERIFY=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo RELEASE_VERIFY=PASS

echo === PROMOTE VALIDATED RC ===
".venv\Scripts\python.exe" promote_windows_release.py >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo RELEASE_PROMOTE=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo RELEASE_PROMOTE=PASS
>>"%LOG%" echo BUILD_WINDOWS_RC=PASS

echo.
echo BUILD_WINDOWS_RC=PASS
echo Executavel validado: dist\Gentill Transcriber\Gentill Transcriber.exe
echo Manifesto: dist\RELEASE_MANIFEST_windows.json
pause
