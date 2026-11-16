@echo off
rem AHOS Blender shim — portable Blender repo dışında tutulur.
if defined AHOS_BLENDER_EXE (
  set "BLENDER=%AHOS_BLENDER_EXE%"
) else (
  set "BLENDER=C:\actions-runner\_work\blender-4.5.16-windows-x64\blender.exe"
)
if not exist "%BLENDER%" (
  echo AHOS_BLENDER_MISSING: %BLENDER% 1>&2
  exit /b 3
)
"%BLENDER%" %*
