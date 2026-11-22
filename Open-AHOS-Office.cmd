@echo off
cd /d "%~dp0"
python "%~dp0tools\start_office.py"
timeout /t 4 /nobreak >nul
