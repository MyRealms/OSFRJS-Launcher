@echo off
setlocal

set "ROOT=%~dp0"
set "DIST_DIR=%ROOT%dist"
set "SPEC_FILE=%ROOT%FreeRealmsJSLauncher.spec"

rem Clean dist\ so the previous build mode's leftovers don't confuse
rem the user or inflate the .7z. PyInstaller's --clean only clears the
rem build cache, not the output directory.
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"

set "OSFR_BUILD_MODE=onedir"
python -m PyInstaller --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 exit /b %errorlevel%

rem Strip the redundant embedded PKG overlay from the onedir EXE so the
rem launcher starts instantly instead of Windows / AV having to scan
rem hundreds of MB of gzip data appended to the PE.
python "%ROOT%strip_pkg.py" "%DIST_DIR%\FreeRealmsJSLauncher\FreeRealmsJSLauncher.exe"
if errorlevel 1 exit /b %errorlevel%

rem PyInstaller always builds the onefile-style EXE first (with the PKG
rem appended), then COLLECT copies it into the onedir subfolder. The
rem orphan in dist\ is never used in onedir mode. Remove it so the user
rem is not confused by a 300+ MB .exe sitting right next to the real
rem onedir launcher.
if exist "%DIST_DIR%\FreeRealmsJSLauncher.exe" del "%DIST_DIR%\FreeRealmsJSLauncher.exe"

echo.
echo Build complete (onedir):
echo   %DIST_DIR%\FreeRealmsJSLauncher\FreeRealmsJSLauncher.exe
