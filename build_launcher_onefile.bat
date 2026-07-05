@echo off
setlocal

set "ROOT=%~dp0"
set "DIST_DIR=%ROOT%dist"
set "SPEC_FILE=%ROOT%FreeRealmsJSLauncher.spec"

rem Clean dist\ so the previous build mode's leftovers don't confuse
rem the user or inflate the .7z. PyInstaller's --clean only clears the
rem build cache, not the output directory.
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

set "OSFR_BUILD_MODE=onefile"
python -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 exit /b %errorlevel%

echo.
echo Build complete (onefile):
echo   %DIST_DIR%\FreeRealmsJSLauncher.exe
