@echo off
REM Force monitor ON via SC_MONITORPOWER
powershell -Command "Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class MW { [DllImport(\"user32.dll\")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l); [DllImport(\"user32.dll\")] public static extern IntPtr GetDesktopWindow(); }'; [MW]::SendMessage([MW]::GetDesktopWindow(), 0x0112, (IntPtr)0xF170, (IntPtr)(-1)) | Out-Null" > nul 2>&1
cd /d "C:\Users\q1138\game-news-daily"
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory="Default"
timeout /t 10 /nobreak > nul
"C:\Users\q1138\AppData\Local\Programs\Python\Python311\python.exe" run-win-opencli.py