#Requires -Version 5.1
<#
.SYNOPSIS
  Build a USB-portable LogiScan runtime on a trusted PC with internet.
.DESCRIPTION
  Downloads embeddable CPython, RapidOCR, onnxruntime-directml, OpenCV,
  and RapidOCR ONNX weights. Run install.bat on the corporate laptop (offline).
#>
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "logiscan\__main__.py"))) {
    throw "Cannot find logiscan package above scripts/. Run this from the LogiScan tree."
}

$PythonVersion = "3.12.10"
$EmbedName = "python-$PythonVersion-embed-amd64.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$EmbedName"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"

$RuntimeDir = Join-Path $Root "runtime\python"
$WheelsDir = Join-Path $Root "vendor\wheels"
$ModelDir = Join-Path $Root "models\rapidocr"
$StageDir = Join-Path $Root "vendor\stage"

New-Item -ItemType Directory -Force -Path $RuntimeDir, $WheelsDir, $ModelDir, $StageDir | Out-Null

function Get-RemoteFile {
    param([string]$Url, [string]$Destination)
    if (Test-Path $Destination) {
        Write-Host "Already present: $Destination"
        return
    }
    Write-Host "Downloading $Url"
    $tmp = "$Destination.download"
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        & curl.exe -L --fail --retry 3 -o $tmp $Url
        if ($LASTEXITCODE -ne 0) { throw "curl failed for $Url" }
    }
    else {
        Invoke-WebRequest -Uri $Url -OutFile $tmp
    }
    Move-Item -Force $tmp $Destination
}

Write-Host "==> Embeddable Python $PythonVersion"
$embedZip = Join-Path $StageDir $EmbedName
Get-RemoteFile -Url $EmbedUrl -Destination $embedZip
if (-not (Test-Path (Join-Path $RuntimeDir "python.exe"))) {
    Expand-Archive -Path $embedZip -DestinationPath $RuntimeDir -Force
}

$pth = Get-ChildItem -Path $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if (-not $pth) { throw "python*._pth missing in $RuntimeDir" }
@(
    "python312.zip"
    "."
    "Lib\site-packages"
    "..\.."
    "import site"
) | Set-Content -Path $pth.FullName -Encoding ascii

$python = Join-Path $RuntimeDir "python.exe"
$getPip = Join-Path $StageDir "get-pip.py"
Get-RemoteFile -Url $GetPipUrl -Destination $getPip
Write-Host "==> Bootstrapping pip"
& $python $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }

Write-Host "==> Downloading RapidOCR, OpenCV, numpy"
& $python -m pip download rapidocr opencv-python numpy -d $WheelsDir
if ($LASTEXITCODE -ne 0) { throw "dependency download failed" }

Write-Host "==> Downloading onnxruntime-directml (must replace CPU onnxruntime)"
& $python -m pip download onnxruntime-directml -d $WheelsDir
if ($LASTEXITCODE -ne 0) { throw "onnxruntime-directml download failed" }

Write-Host "==> Installing into embed Python so RapidOCR models can be prefetched"
& $python -m pip install --no-index --find-links $WheelsDir rapidocr opencv-python numpy
if ($LASTEXITCODE -ne 0) { throw "prepare-time RapidOCR install failed" }
& $python -m pip uninstall -y onnxruntime
& $python -m pip install --no-index --find-links $WheelsDir onnxruntime-directml
if ($LASTEXITCODE -ne 0) { throw "prepare-time onnxruntime-directml install failed" }

Write-Host "==> Prefetching RapidOCR ONNX models into $ModelDir"
$env:PYTHONPATH = $Root
& $python -c @"
from pathlib import Path
from rapidocr import RapidOCR
from logiscan.ocr import _loaded_models, engine_params
model_dir = Path(r'$ModelDir')
model_dir.mkdir(parents=True, exist_ok=True)
engine = RapidOCR(params=engine_params(model_dir))
_loaded_models(engine)
print('Models ready in', model_dir)
"@
if ($LASTEXITCODE -ne 0) { throw "RapidOCR model prefetch failed" }

Write-Host ""
Write-Host "Prepare complete. Copy this folder to a USB stick, then on the corporate laptop run:"
Write-Host "  scripts\install.bat"
Write-Host "  scripts\run.bat"
Write-Host "Drop images in photos\ first."
