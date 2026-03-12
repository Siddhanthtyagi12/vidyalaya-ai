@echo off
echo [INFO] Closing old Dashboard processes...
taskkill /F /IM python.exe /T >nul 2>&1
echo [INFO] Old processes cleared.
echo [INFO] Starting Fresh Dashboard...
start /min cmd /c "python backend/app.py"
echo [SUCCESS] Please wait 3 seconds and refresh your browser at http://127.0.0.1:5000
timeout /t 3 >nul
pause
