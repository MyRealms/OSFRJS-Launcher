@echo off
setlocal

set "ROOT=%~dp0"
set "DIST_EXE=%ROOT%dist\FreeRealmsJSLauncher\FreeRealmsJSLauncher.exe"

if exist "%DIST_EXE%" (
    start "" "%DIST_EXE%" --debug
    exit /b 0
)

python "%ROOT%launcher_ui.py" --debug
