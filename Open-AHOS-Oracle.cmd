@echo off
cd /d "%~dp0"
python tools\open_oracle_studio.py
if errorlevel 1 pause
