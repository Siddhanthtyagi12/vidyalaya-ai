Set WshShell = CreateObject("WScript.Shell")

' Change directory to the project folder
WshShell.CurrentDirectory = "d:\sidprojects"

' Run Flask visibly for debugging (1 means normal window)
WshShell.Run "cmd /c python backend/app.py", 1, false

' Wait 5 seconds for server to start
WScript.Sleep 5000

' Open browser to the URL
WshShell.Run "http://127.0.0.1:5000"
