@echo off
title NSE Analyzer - Share Public Link
color 0A

cd /d "%~dp0"

echo ================================================================
echo   NSE DERIVATIVES INTELLIGENCE - PUBLIC SHARING MODE
echo ================================================================
echo.
echo [1/3] Freeing port 5000 if occupied...
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 5000 -EA SilentlyContinue; if($c){foreach($x in $c){Stop-Process -Id $x.OwningProcess -Force -EA SilentlyContinue}}"
timeout /t 1 /nobreak >nul

echo [2/3] Starting NSE Analyzer server...
start /b cmd /c "python app.py > server_log.txt 2>&1"
timeout /t 3 /nobreak >nul

echo [3/3] Creating public shareable tunnel...
echo.
echo ================================================================
echo   YOUR PUBLIC LINK WILL APPEAR BELOW IN A FEW SECONDS...
echo   Copy the https://....trycloudflare.com link and share it!
echo.
echo   Press Ctrl+C to stop sharing anytime.
echo ================================================================
echo.

cloudflared.exe tunnel --url http://127.0.0.1:5000

pause
