@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "LIVE_BOT_DIR=%~dp0"
set "NAME_FILE=%TEMP%\igneel-build-name-%RANDOM%-%RANDOM%.txt"
set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

pushd "%PROJECT_ROOT%" || goto :failed

rem The config module reads credentials for all deployments at import time.
rem Build-only values let this script obtain the selected config name without
rem requiring or packaging a developer's real credentials.
set "LOGIN=0"
set "PASSWORD=build-only"
set "SERVER=build-only"
set "TERMINAL_PATH=build-only"
"%PYTHON_EXE%" -c "from live_bot.live_config import active_config; name = active_config.get('name'); invalid = set('<>:/\\|?*') | {chr(34)}; reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {'COM' + str(i) for i in range(1, 10)} | {'LPT' + str(i) for i in range(1, 10)}; valid = isinstance(name, str) and bool(name) and name == name.strip() and not name.endswith(('.', ' ')) and not any(ch in invalid or ord(ch) < 32 for ch in name) and name.split('.')[0].upper() not in reserved; print(name) if valid else exit(2)" > "%NAME_FILE%"
if errorlevel 1 goto :invalid_name

set /p "EXE_NAME="<"%NAME_FILE%"
del /q "%NAME_FILE%" >nul 2>&1
if not defined EXE_NAME goto :invalid_name

"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean --onefile --windowed --name "%EXE_NAME%" --icon "%LIVE_BOT_DIR%igneel.ico" --add-data "%LIVE_BOT_DIR%igneel.ico;." --hidden-import=talib.stream --paths "%PROJECT_ROOT%" --distpath "%LIVE_BOT_DIR%dist" --workpath "%LIVE_BOT_DIR%build\pyinstaller" --specpath "%LIVE_BOT_DIR%build" "%LIVE_BOT_DIR%gui.py"
if errorlevel 1 goto :build_failed

if not exist "%LIVE_BOT_DIR%dist\%EXE_NAME%.exe" goto :missing_executable

set "ISCC_EXE="
where ISCC.exe >nul 2>&1
if not errorlevel 1 set "ISCC_EXE=ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE goto :missing_iscc

set "APP_NAME=%EXE_NAME%"
"%ISCC_EXE%" "%LIVE_BOT_DIR%installer.iss"
if errorlevel 1 goto :installer_failed

echo.
echo Build complete:
echo   %LIVE_BOT_DIR%dist\%EXE_NAME%.exe
echo   %LIVE_BOT_DIR%dist\%EXE_NAME%Setup.exe
popd
exit /b 0

:invalid_name
del /q "%NAME_FILE%" >nul 2>&1
echo ERROR: active_config must define "name" as a valid Windows filename.
goto :failed

:build_failed
echo ERROR: PyInstaller failed. Install build dependencies with "%PYTHON_EXE% -m pip install -r requirements.txt".
goto :failed

:missing_executable
echo ERROR: PyInstaller did not create "%LIVE_BOT_DIR%dist\%EXE_NAME%.exe".
goto :failed

:missing_iscc
echo ERROR: Inno Setup 6 compiler ISCC.exe was not found. Install Inno Setup 6 or add ISCC.exe to PATH.
goto :failed

:installer_failed
echo ERROR: Inno Setup failed to compile installer. See the compiler output above.

:failed
popd 2>nul
exit /b 1
