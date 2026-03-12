Set WshShell = CreateObject("WScript.Shell")
' Run Flask implicitly hidden (0 means hidden window)
WshShell.Run "cmd /c python backend/app.py", 0, false

' Wait a fraction of a second for server to open port
WScript.Sleep 1000

' Open browser to the URL
WshShell.Run "http://127.0.0.1:5000"
