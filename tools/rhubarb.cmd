@echo off
rem AHOS Rhubarb shim — binary repo dışında tutulur.
if defined AHOS_RHUBARB_EXE (
  set "RHUBARB=%AHOS_RHUBARB_EXE%"
) else (
  set "RHUBARB=C:\actions-runner\_work\tools\rhubarb\Rhubarb-Lip-Sync-1.14.0-Windows\rhubarb.exe"
)
if not exist "%RHUBARB%" (
  echo AHOS_RHUBARB_MISSING: %RHUBARB% 1>&2
  exit /b 3
)
"%RHUBARB%" %*
