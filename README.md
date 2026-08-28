# LogiScan

Windows USB kit that files trailer photos into PO folders.

It converts HEIC/HEIF/PNG to JPEG, reads an ISO-6346 trailer code and a 5-digit seal with RapidOCR on DirectML. iGPU only. No CPU OCR. Then it moves the JPEG into the matching PO folder when every gate passes.

Operators start it by double-clicking `LogiScan.exe` at the kit root. That EXE is a small C# stub. The OCR stack stays in the bundled embeddable Python 3.12 under `runtime\python`. Nothing is installed into Program Files. No admin rights.

## What you need

- 64-bit Windows with a DirectML-capable iGPU
- Internet once, on a trusted PC, to run `scripts\prepare.ps1`
- A folder tree of PO directories whose filenames contain ISO-6346 codes. That tree is the search root. LogiScan does not open PDFs or Excel.

Corporate laptops can be offline after you copy the prepared folder onto a stick.

## First-time prepare

Needs internet. No admin. From the repo root:

```powershell
powershell -NoProfile -File scripts\prepare.ps1
```

That downloads embeddable CPython 3.12.10, stages Tcl/Tk from python.org MSIs into `vendor\tcltk`, compiles `LogiScan.exe`, vendors wheels, and prefetches RapidOCR ONNX models into `models\rapidocr`.

If pip prints `WARNING: Skipping onnxruntime as it is not installed.`, ignore it. The scripts always try to uninstall CPU `onnxruntime` so DirectML can stay in charge. When that CPU package was never installed, pip skips it. `onnxruntime-directml` is the one that must be present.

Copy the whole folder to the USB stick. Include `LogiScan.exe`, `logiscan\`, `runtime\`, `vendor\`, `models\`, `photos\`, and `scripts\`.

## Warehouse laptop

Offline is fine after prepare. Run:

```bat
scripts\install.bat
```

Installs wheels from `vendor\wheels`, copies Tcl/Tk into the USB Python, then runs a hardware probe. You want:

```text
DmlExecutionProvider present: True
OK: iGPU OCR backend will be onnxruntime-dml
```

Exit code 2 means DirectML is missing. Do not try to "fix" that with CPU `onnxruntime`. LogiScan will refuse CPU OCR.

## Start the app

Double-click `LogiScan.exe` in the kit root.

The first click can sit for several seconds while it imports RapidOCR, numpy, OpenCV, and DirectML. That is expected.

If Python, Tcl/Tk, or wheels are missing, the stub tries `scripts\install.bat` or `python -m logiscan.tcltk` by itself. It never runs `prepare.ps1`. That script needs internet.

If the window never appears, read `logs\gui-stderr.log` next to the EXE.

`LogiScan.exe` is gitignored. `prepare.ps1` builds it with `.NET Framework` `csc.exe`. If the file is missing, run prepare again. Compile happens before pip, so a later pip error should still leave you an EXE.

## Operator window

1. Photos folder (defaults to the kit `photos` directory)
2. PO search root (you must pick this)
3. Run

You get a thumbnail, N-of-M progress, and a row per photo (filename, trailer, seal, status). Cancel finishes the current photo, then stops.

Last-used folders are stored in `logiscan_gui.json` at the kit root. Drop images in `photos\` (top level only). Do not put them inside `_processed`.

## What a successful file looks like

JPEG destination:

```text
<PO folder>\TRAILER_SEAL.jpg
```

HEIC/HEIF/PNG originals are moved to `photos\_processed` after a successful JPEG move. Existing destination files are not overwritten. Ambiguous trailer, missing seal, or no unique PO folder leaves the original in place.

Each run appends `ocr_report.csv`. Moves also append `ocr_matches.log`.

## Maintainer CLI

Operators should not need this. Tests and debugging still use the bundled Python.

```bat
runtime\python\python.exe -m logiscan --check-hardware
runtime\python\python.exe -m logiscan --input-dir photos --search-root "D:\POs"
```

`--search-root` is required for a processing run. `--check-hardware` is not.

System Python on PATH is not the USB kit. GUI and OCR must run through `runtime\python`.

## Tests

No pytest. No GPU required for this set:

```bat
python -m unittest tests.test_tcltk_copy tests.test_gui_prefs tests.test_batch tests.test_preview tests.test_report.CliTests tests.test_extract tests.test_hardware tests.test_images tests.test_index tests.test_iso tests.test_move -v
```

`tests.test_gpu` needs DirectML and the kit packages. Skip it on machines without `onnxruntime-directml`.

## Layout

```text
LogiScan.exe                 double-click this after prepare
logiscan\                    Python package
runtime\python\              embed 3.12 + Tcl/Tk + site-packages
models\rapidocr\             ONNX weights
photos\                      drop images here
vendor\wheels\               offline pip
vendor\tcltk\                staged Tcl/Tk for install.bat
scripts\prepare.ps1          trusted PC, internet
scripts\install.bat          warehouse laptop
scripts\LogiScanLauncher\    C# stub source
```

## Hard rules

- DirectML only. No CPU OCR fallback.
- No PyInstaller or Nuitka freeze of RapidOCR, DirectML, or HEIC.
- Tcl/Tk lives in the kit. It is not installed on the PC.
- Do not restore operator `.bat` launchers at the kit root. `install.bat` is a maintainer script, not the start button.
