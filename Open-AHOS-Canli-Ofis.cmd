@echo off
cd /d "%~dp0"
rem AHOS canli ofis: sunucuyu acar (yoksa) ve canli ofisi tarayicida acar
powershell -NoProfile -Command "$c=New-Object System.Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1',8787); exit 0 } catch { exit 1 } finally { $c.Dispose() }"
if errorlevel 1 (
  start "AHOS OFIS" /min python "%~dp0tools\office_server.py"
  timeout /t 3 /nobreak >nul
)
start "" "http://127.0.0.1:8787/canli"
