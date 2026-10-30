@echo off
setlocal
cd /d "%~dp0"
title Ban tin - giu cua so nay mo
where python >nul 2>nul
if not errorlevel 1 (
    python -m newsroom
) else (
    py -3 -m newsroom
)
if errorlevel 1 (
    echo.
    echo Khong mo duoc ung dung. Xem README.md hoac gui thong bao loi cho tro ly.
    pause
)
