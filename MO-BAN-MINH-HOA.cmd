@echo off
setlocal
cd /d "%~dp0"
title Ban tin - ban minh hoa rieng
where python >nul 2>nul
if not errorlevel 1 (
    python -m newsroom --demo --port 8878
) else (
    py -3 -m newsroom --demo --port 8878
)
if errorlevel 1 pause
