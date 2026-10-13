@echo off
setlocal
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)
exit /b 0
