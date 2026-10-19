Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard"
WshShell.Run "cmd /c .\.venv\Scripts\python.exe sync_github.py --force-sap", 0, True
