@echo off
chcp 65001 >nul
echo ========================================
echo   Competitive Analysis Agent - Starting
echo ========================================
echo.

set "ROOT=%~dp0"

echo [1/2] Starting backend (port 5010)...
start "Backend" /D "%ROOT%backend" cmd /k "py -3.12 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 5010"

timeout /t 2 /nobreak >nul

echo [2/2] Starting frontend (port 5000)...
start "Frontend" /D "%ROOT%frontend" cmd /k "npm run dev"

timeout /t 3 /nobreak >nul
echo.
echo Opening browser...
start http://localhost:5000

echo.
echo Frontend and backend started. This window can be closed safely.
echo To stop, close the terminal windows.
pause
