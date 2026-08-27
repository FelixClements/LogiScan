@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
set "ROOT=%CD%"
set "PY=%ROOT%\runtime\python\python.exe"
set "PYTHONPATH=%ROOT%"
set "WHEELS=%ROOT%\vendor\wheels"

if not exist "%PY%" (
  echo Embeddable Python not found at "%PY%"
  echo Run scripts\prepare.ps1 on a trusted PC with internet first, then copy this folder to the USB stick.
  exit /b 1
)

echo Installing RapidOCR and OpenCV from "%WHEELS%"...
"%PY%" -m pip install --no-index --find-links "%WHEELS%" rapidocr opencv-python numpy
if errorlevel 1 (
  echo Install failed.
  exit /b 1
)

echo Forcing onnxruntime-directml (CPU onnxruntime cannot stay installed)...
"%PY%" -m pip uninstall -y onnxruntime
"%PY%" -m pip install --no-index --find-links "%WHEELS%" onnxruntime-directml
if errorlevel 1 (
  echo onnxruntime-directml install failed.
  exit /b 1
)

echo.
echo Hardware probe:
"%PY%" -m logiscan --check-hardware
exit /b %ERRORLEVEL%
