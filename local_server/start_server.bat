@echo off
title Starting OSFR Servers

REM 
cd /d "%~dp0"

echo Starting Login Server...
start "" /D "%~dp0Emulator" "Sanctuary.Login.exe"
timeout /t 2 >nul

echo Starting Gateway Server...
start "" /D "%~dp0Emulator" "Sanctuary.Gateway.exe"
timeout /t 1 >nul

echo Starting AuthBridge...
start "" /D "%~dp0AuthBridge" "..\node\node.exe" "server.mjs"

echo.
echo All servers started.
pause
