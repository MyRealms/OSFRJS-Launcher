@echo off
setlocal

set "ROOT=%~dp0"
set "DIST_DIR=%ROOT%dist"
set "SPEC_FILE=%ROOT%FreeRealmsJSLauncher.spec"

python -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 exit /b %errorlevel%

echo.
echo Build complete:
echo   %DIST_DIR%\FreeRealmsJSLauncher\FreeRealmsJSLauncher.exe
