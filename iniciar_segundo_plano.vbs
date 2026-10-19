Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard"
WshShell.Run "cmd /c ""C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard\.venv\Scripts\python.exe"" -m streamlit run app.py", 0, False
WshShell.Run "cmd /c ""C:\Users\joao.veronez\.gemini\antigravity\scratch\sharepoint-dashboard\.venv\Scripts\python.exe"" sync_github.py --loop", 0, False
