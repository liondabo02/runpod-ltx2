@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "$c=New-Object System.Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',8767); exit 0 } catch { exit 1 } finally { $c.Dispose() }"
if errorlevel 1 (
  start "AHOS STUDIO-16" /min python "%~dp0tools\ahos_studio_ui.py" --port 8767
  timeout /t 2 /nobreak >nul
)
start "" "http://127.0.0.1:8767/"
