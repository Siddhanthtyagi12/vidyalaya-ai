@echo off
cd mobile_app
echo [INFO] Vidyalaya AI Mobile App start ho rahi hai...
echo [INFO] QR Code scan karne ke liye apne phone mein "Expo Go" app kholiye.
echo [INFO] Agar koi sawal puche (jaise port change), toh 'y' dabayein.
echo.
npx expo start --tunnel
pause
