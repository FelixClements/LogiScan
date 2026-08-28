@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PYW=%ROOT%\runtime\python\pythonw.exe"
set "PYTHONPATH=%ROOT%"
set "TCL_LIBRARY=%ROOT%\runtime\python\tcl\tcl8.6"
set "TK_LIBRARY=%ROOT%\runtime\python\tcl\tk8.6"

if exist "%PYW%" goto :run
where pythonw >nul 2>&1
if errorlevel 1 (
  echo pythonw not found. Run scripts\prepare.ps1 then scripts\install.bat from this USB kit first.
  exit /b 1
)
set "PYW=pythonw"

:run
"%PYW%" -m logiscan.gui %*
exit /b %ERRORLEVEL%
