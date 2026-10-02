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

echo === LOCK ===
".venv\Scripts\python.exe" -m pip freeze --all > requirements.lock.txt
if errorlevel 1 (
  >>"%LOG%" echo LOCK=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo LOCK=PASS

echo === QA PRE-BUILD ===
".venv\Scripts\python.exe" -m unittest -v test_transcriber.py test_transcriber_e2e.py test_product_features.py >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo QA_PRE_BUILD=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo QA_PRE_BUILD=PASS

echo === BUILD APP ===
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist-rc" --workpath "build-rc" "gentill_transcriber.spec" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo PYINSTALLER=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo PYINSTALLER=PASS

echo === SIGN APP IF CONFIGURED ===
".venv\Scripts\python.exe" sign_windows.py "dist-rc\Gentill Transcriber\Gentill Transcriber.exe" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo APP_SIGN=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo APP_SIGN=PASS_OR_SKIPPED

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

echo === BUILD UNINSTALLER ===
if exist "dist-installer-tools" rmdir /s /q "dist-installer-tools"
if exist "build-installer-tools" rmdir /s /q "build-installer-tools"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist-installer-tools" --workpath "build-installer-tools" "gentill_uninstaller.spec" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo UNINSTALLER_BUILD=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo UNINSTALLER_BUILD=PASS

echo === SIGN UNINSTALLER IF CONFIGURED ===
".venv\Scripts\python.exe" sign_windows.py "dist-installer-tools\Gentill Transcriber Uninstall.exe" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo UNINSTALLER_SIGN=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo UNINSTALLER_SIGN=PASS_OR_SKIPPED

echo === BUILD INSTALLER ===
if exist "dist-installer" rmdir /s /q "dist-installer"
if exist "build-installer" rmdir /s /q "build-installer"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath "dist-installer" --workpath "build-installer" "gentill_installer.spec" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo INSTALLER_BUILD=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo INSTALLER_BUILD=PASS

echo === SIGN INSTALLER IF CONFIGURED ===
".venv\Scripts\python.exe" sign_windows.py "dist-installer\Gentill Transcriber Setup.exe" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo INSTALLER_SIGN=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo INSTALLER_SIGN=PASS_OR_SKIPPED

echo === VERIFY INSTALLER ===
".venv\Scripts\python.exe" verify_installer.py --installer "dist-installer\Gentill Transcriber Setup.exe" >>"%LOG%" 2>&1
if errorlevel 1 (
  >>"%LOG%" echo INSTALLER_VERIFY=FAIL
  pause
  exit /b 1
)
>>"%LOG%" echo INSTALLER_VERIFY=PASS

>>"%LOG%" echo BUILD_WINDOWS_RC=PASS

echo.
echo BUILD_WINDOWS_RC=PASS
echo Executavel validado: dist\Gentill Transcriber\Gentill Transcriber.exe
echo Instalador validado: dist-installer\Gentill Transcriber Setup.exe
echo Manifesto: dist\RELEASE_MANIFEST_windows.json
pause
