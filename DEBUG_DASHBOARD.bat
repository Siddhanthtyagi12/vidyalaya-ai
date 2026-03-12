@echo off
echo [INFO] Closing old Dashboard processes...
taskkill /F /IM python.exe /T >nul 2>&1
echo [INFO] Old processes cleared.
echo [INFO] Starting Dashboard in DEBUG MODE (Visible Window)...
echo [NOTE] Please wait until you see "Running on http://127.0.0.1:5000"
echo.
python backend/app.py
pause
