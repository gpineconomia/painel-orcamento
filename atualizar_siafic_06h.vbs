Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard"
WshShell.Run "cmd /c ""C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard\.venv\Scripts\python.exe"" ""C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard\sync_github.py"" --force-sap", 0, True
