@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\runtime\python\python.exe"
set "PYTHONPATH=%ROOT%"

if exist "%PY%" goto :run
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Run scripts\install.bat from this USB kit first.
  exit /b 1
)
set "PY=python"

:run
"%PY%" -m logiscan --check-hardware
exit /b %ERRORLEVEL%
