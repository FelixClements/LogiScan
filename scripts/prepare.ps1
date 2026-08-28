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

Write-Host "==> Compiling LogiScan.exe"
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path $csc)) {
    throw "csc.exe not found under Microsoft.NET\Framework64 or Framework v4.0.30319"
}
$launcherSrc = Join-Path $Root "scripts\LogiScanLauncher\Program.cs"
$exe = Join-Path $Root "LogiScan.exe"
& $csc /nologo /target:winexe /r:System.Windows.Forms.dll /r:System.dll /out:$exe $launcherSrc
if ($LASTEXITCODE -ne 0) { throw "LogiScan.exe compile failed" }
if (-not (Test-Path $exe)) { throw "LogiScan.exe was not written to $exe" }

function Expand-Msi {
    param([string]$MsiPath, [string]$Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $p = Start-Process -FilePath "msiexec.exe" -ArgumentList @(
        "/a", $MsiPath, "TARGETDIR=$Destination", "/qn", "/norestart"
    ) -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        throw "msiexec /a failed with exit $($p.ExitCode) for $MsiPath (TARGETDIR=$Destination). No admin should be required for a kit-local TARGETDIR."
    }
}

Write-Host "==> Vendoring Tcl/Tk from python.org MSI $PythonVersion"
$tclMsi = Join-Path $StageDir "tcltk.msi"
$libMsi = Join-Path $StageDir "lib.msi"
Get-RemoteFile -Url "https://www.python.org/ftp/python/$PythonVersion/amd64/tcltk.msi" -Destination $tclMsi
Get-RemoteFile -Url "https://www.python.org/ftp/python/$PythonVersion/amd64/lib.msi" -Destination $libMsi
$tclExtract = Join-Path $StageDir "msi-tcltk"
$libExtract = Join-Path $StageDir "msi-lib"
if (-not (Test-Path (Join-Path $Root "vendor\tcltk\.staged"))) {
    if (Test-Path $tclExtract) { Remove-Item -Recurse -Force $tclExtract }
    if (Test-Path $libExtract) { Remove-Item -Recurse -Force $libExtract }
    Expand-Msi -MsiPath $tclMsi -Destination $tclExtract
    Expand-Msi -MsiPath $libMsi -Destination $libExtract
    $vendorTk = Join-Path $Root "vendor\tcltk"
    New-Item -ItemType Directory -Force -Path $vendorTk | Out-Null
    $tkinterPyd = Get-ChildItem -Path $tclExtract -Recurse -Filter "_tkinter.pyd" | Select-Object -First 1
    if (-not $tkinterPyd) { throw "_tkinter.pyd missing from tcltk.msi extract at $tclExtract" }
    Copy-Item -Force $tkinterPyd.FullName (Join-Path $vendorTk "_tkinter.pyd")
    $dllDir = $tkinterPyd.DirectoryName
    Get-ChildItem -Path $dllDir -Filter "tcl86*.dll" | ForEach-Object { Copy-Item -Force $_.FullName $vendorTk }
    Get-ChildItem -Path $dllDir -Filter "tk86*.dll" | ForEach-Object { Copy-Item -Force $_.FullName $vendorTk }
    $zlibDll = Get-ChildItem -Path $dllDir -Filter "zlib1.dll" | Select-Object -First 1
    if (-not $zlibDll) { throw "zlib1.dll missing from tcltk.msi extract next to _tkinter.pyd at $dllDir" }
    Copy-Item -Force $zlibDll.FullName $vendorTk
    $tcl86 = Get-ChildItem -Path $tclExtract -Recurse -Directory -Filter "tcl8.6" | Select-Object -First 1
    $tk86 = Get-ChildItem -Path $tclExtract -Recurse -Directory -Filter "tk8.6" | Select-Object -First 1
    if (-not $tcl86) { throw "tcl8.6 missing from tcltk.msi extract" }
    if (-not $tk86) { throw "tk8.6 missing from tcltk.msi extract" }
    $vendorTcl = Join-Path $vendorTk "tcl"
    New-Item -ItemType Directory -Force -Path $vendorTcl | Out-Null
    $destTcl86 = Join-Path $vendorTcl "tcl8.6"
    $destTk86 = Join-Path $vendorTcl "tk8.6"
    if (Test-Path $destTcl86) { Remove-Item -Recurse -Force $destTcl86 }
    if (Test-Path $destTk86) { Remove-Item -Recurse -Force $destTk86 }
    Copy-Item -Recurse -Force $tcl86.FullName $destTcl86
    Copy-Item -Recurse -Force $tk86.FullName $destTk86
    $tkinterPkg = Get-ChildItem -Path $tclExtract -Recurse -Directory -Filter "tkinter" |
        Where-Object { Test-Path (Join-Path $_.FullName "__init__.py") } |
        Select-Object -First 1
    if (-not $tkinterPkg) { throw "Lib/tkinter missing from tcltk.msi extract at $tclExtract" }
    $vendorPkg = Join-Path $vendorTk "Lib\site-packages\tkinter"
    New-Item -ItemType Directory -Force -Path (Split-Path $vendorPkg) | Out-Null
    if (Test-Path $vendorPkg) { Remove-Item -Recurse -Force $vendorPkg }
    Copy-Item -Recurse -Force $tkinterPkg.FullName $vendorPkg
    "" | Set-Content -Path (Join-Path $vendorTk ".staged") -Encoding ascii
}

$python = Join-Path $RuntimeDir "python.exe"
$env:PYTHONPATH = $Root
Write-Host "==> Copying vendor/tcltk into runtime/python"
& $python -m logiscan.tcltk
if ($LASTEXITCODE -ne 0) { throw "logiscan.tcltk copy failed; vendor/tcltk is incomplete" }
& $python -c "import tkinter; print(tkinter.Tcl().eval('info patchlevel'))"
if ($LASTEXITCODE -ne 0) { throw "Tcl/Tk did not initialize after copy (check zlib1.dll and tcl8.6 trees)" }
$getPip = Join-Path $StageDir "get-pip.py"
Get-RemoteFile -Url $GetPipUrl -Destination $getPip
Write-Host "==> Bootstrapping pip"
& $python $getPip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "get-pip failed" }

Write-Host "==> Downloading RapidOCR, OpenCV, numpy, pillow-heif"
& $python -m pip download rapidocr opencv-python numpy pillow-heif -d $WheelsDir
if ($LASTEXITCODE -ne 0) { throw "dependency download failed" }

Write-Host "==> Downloading onnxruntime-directml (must replace CPU onnxruntime)"
& $python -m pip download onnxruntime-directml -d $WheelsDir
if ($LASTEXITCODE -ne 0) { throw "onnxruntime-directml download failed" }

Write-Host "==> Installing into embed Python so RapidOCR models can be prefetched"
& $python -m pip install --no-index --find-links $WheelsDir rapidocr opencv-python numpy pillow-heif
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
Write-Host "After that, operators double-click LogiScan.exe"
Write-Host "Drop images in photos\ first."
