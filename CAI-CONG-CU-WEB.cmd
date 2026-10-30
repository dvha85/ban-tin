@echo off
setlocal
cd /d "%~dp0"
title Cai cong cu web cho Ban tin
echo Chi cai thu vien va Chromium cuc bo. Khong dang nhap, khong goi model AI.
echo Moi truong rieng: %USERPROFILE%\AppData\Local\BanTinTools\crawl-0.9.5
set "BANTIN_WEB_ENV=%USERPROFILE%\AppData\Local\BanTinTools\crawl-0.9.5"
if not exist "%BANTIN_WEB_ENV%\Scripts\python.exe" (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -m venv "%BANTIN_WEB_ENV%"
    ) else (
        py -3 -m venv "%BANTIN_WEB_ENV%"
    )
    if errorlevel 1 goto failed
)
"%BANTIN_WEB_ENV%\Scripts\python.exe" -m pip install -r requirements-web.txt
if errorlevel 1 goto failed
"%BANTIN_WEB_ENV%\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto failed
echo Da cai xong. Mo Ban tin, vao Nguon tin de bat nguon can doc.
pause
exit /b 0
:failed
echo Chua cai xong. Giu thong bao loi va gui lai cho tro ly. RSS/API van dung duoc.
pause
exit /b 1
