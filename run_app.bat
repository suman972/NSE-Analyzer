@echo off
title NSE Institutional Derivatives & Option Selling System
color 0B
echo =======================================================================
echo     NSE DERIVATIVES INTELLIGENCE & OPTION SELLING STRATEGY DESK
echo =======================================================================
echo.
cd /d "%~dp0"

echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not found in your system PATH!
    echo Please install Python 3.10+ from python.org and check "Add Python to PATH".
    echo.
    pause
    exit /b
)

echo [2/3] Freeing port 5000 if occupied...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [3/3] Starting server and launching browser...
start /b cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5000/"

echo.
echo =======================================================================
echo Server is running live on: http://127.0.0.1:5000
echo.
echo Active Sections:
echo   [1] Home Dashboard           : http://127.0.0.1:5000/
echo   [2] Participant-Wise OI      : http://127.0.0.1:5000/participant-oi
echo   [3] Proper Option Chain      : http://127.0.0.1:5000/option-chain
echo   [4] 5-Data Quant Pipeline    : http://127.0.0.1:5000/pipeline
echo   [5] Big Player Strikes       : http://127.0.0.1:5000/strike-intelligence
echo   [6] Details Report (PDF)     : http://127.0.0.1:5000/details-report
echo   [7] Option Selling           : http://127.0.0.1:5000/option-selling
echo.
echo Press Ctrl + C or close this window to stop the server anytime.
echo =======================================================================
echo.

python app.py
pause
