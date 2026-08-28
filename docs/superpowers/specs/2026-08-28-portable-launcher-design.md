# Portable launcher

LogiScan stays a USB kit (embeddable Python, RapidOCR, DirectML). Operators start it with one double-click: `LogiScan.exe` at the kit root. That EXE is a tiny C# stub, not a frozen OCR app. It starts `runtime\python\pythonw.exe -m logiscan.gui`.

This also fixes why start fails today:

- `run.bat` with no args exits 1 (`--search-root` is required) and the window closes.
- `run_gui.bat` uses the USB `pythonw.exe`, which has no Tcl/Tk. The official Python NuGet package does not include tkinter, and PowerShell `Expand-Archive` rejects `.nupkg`.

## Non-goals

- PyInstaller, Nuitka, or any freeze of RapidOCR / onnxruntime-directml / HEIC into the EXE
- Installing Python, Tcl/Tk, or LogiScan into Program Files
- Administrator rights on the trusted PC or the warehouse laptop
- Watch mode, review-before-move, or filing-pipeline changes
- Operator-facing `.bat` files at the kit root

## Kit layout

```text
LogiScan.exe              operator double-click
logiscan\                 Python package
runtime\python\           embed 3.12 + Tcl/Tk + site-packages
models\rapidocr\
photos\
vendor\wheels\
vendor\tcltk\             staged Tcl/Tk files for offline copy
scripts\prepare.ps1
scripts\install.bat
scripts\LogiScanLauncher\ Program.cs
```

`python -m logiscan` remains for tests and maintainers. Operators do not use it.

Delete `scripts\run.bat` and `scripts\run_gui.bat`.

## LogiScan.exe

WinExe (no console). `prepare.ps1` compiles `scripts\LogiScanLauncher\Program.cs` with `.NET Framework` `csc.exe`. Try `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`, then `Framework\v4.0.30319\csc.exe`. Output is `LogiScan.exe` at the kit root. If `csc.exe` is missing, prepare fails with those paths named.

Kit root = directory containing the EXE (`AppContext.BaseDirectory` / `Assembly.Location`). Working directory is set to the kit root before starting Python.

Environment for the child process:

```text
PYTHONPATH=<kit>
TCL_LIBRARY=<kit>\runtime\python\tcl\tcl8.6
TK_LIBRARY=<kit>\runtime\python\tcl\tk8.6
```

Command:

```text
<kit>\runtime\python\pythonw.exe -m logiscan.gui
```

### Auto-fix, then start

Do not pop a “file is missing, go run a script” box when a local script can still repair the kit.

1. **Python missing** (`runtime\python\python.exe` not present): run `scripts\install.bat` in a visible `cmd.exe` window and wait. That script already errors if the embed was never prepared. After it exits, if `python.exe` is still missing, MessageBox: this USB copy was never prepared on a trusted PC (no internet here to download one).
2. **Tcl/Tk missing** (`python.exe -c "import tkinter"` fails): run `python.exe -m logiscan.tcltk` which copies `vendor\tcltk\` into `runtime\python\`, then retry the import. No prompt. If vendor files are also missing, MessageBox: kit incomplete (prepare never staged Tcl/Tk).
3. **Wheels missing** (e.g. `python.exe -c "import rapidocr"` fails): run `scripts\install.bat` in a visible window, wait, then continue.
4. **Start GUI.** If `pythonw` exits within two seconds with a non-zero code, MessageBox the captured stderr.

Never run `prepare.ps1` from the launcher (needs internet and several minutes). Never use `ShellExecute` on an MSI. Never request elevation.

## Tcl/Tk (no admin, kit-local only)

Tcl/Tk is never installed on the machine. Files live only under the kit.

`prepare.ps1` currently downloads NuGet `python` 3.12.10 for tkinter. **Remove that step.** That package has no `_tkinter.pyd`, and `Expand-Archive` cannot open `.nupkg`.

Instead, download the official installer payloads (same version as the embed, 3.12.10):

```text
https://www.python.org/ftp/python/3.12.10/amd64/tcltk.msi
https://www.python.org/ftp/python/3.12.10/amd64/lib.msi
```

Extract into `vendor\stage\` with no admin:

- Prefer `msiexec /a <msi> TARGETDIR=<kit>\vendor\stage\<name> /qn`. TARGETDIR is inside the kit, not Program Files. This is an administrative unpack to a folder, not a system install.
- If `/a` fails without elevation, extract with the `WindowsInstaller.Installer` COM object (read the MSI cabinet and copy files). Do not require 7-Zip.

Copy into both `vendor\tcltk\` (offline cache) and `runtime\python\`:

| Source (after extract) | Destination under `runtime\python` and `vendor\tcltk` |
|---|---|
| `_tkinter.pyd` | `_tkinter.pyd` (next to `python.exe`) |
| `tcl86*.dll`, `tk86*.dll` | same folder as `python.exe` |
| `tcl8.6` and `tk8.6` directories | `tcl\tcl8.6`, `tcl\tk8.6` |
| `Lib\tkinter\` (from `lib.msi`) | `Lib\site-packages\tkinter\` |

`python312._pth` already has `Lib\site-packages` and `import site`. No pip GUI package.

`scripts\install.bat` (offline, no admin): after wheels, run `"%PY%" -m logiscan.tcltk` so `vendor\tcltk` is copied when `_tkinter.pyd` is still missing. Then the existing hardware probe.

## Install vs prepare

| When | Who | Network | What |
|---|---|---|---|
| `prepare.ps1` | trusted PC | yes | embed Python, wheels, models, Tcl/Tk into vendor + runtime, compile `LogiScan.exe` |
| `install.bat` | warehouse PC | no | pip from `vendor\wheels`, copy `vendor\tcltk` if needed, `--check-hardware` |
| `LogiScan.exe` | operator | no | auto-fix from vendor/install.bat, then GUI |

## Errors

| Situation | Operator sees |
|---|---|
| Kit fully prepared | GUI window, no console |
| Tcl/Tk not in runtime but in vendor | silent copy, then GUI |
| Wheels not installed, python present | `install.bat` window, then GUI |
| No python.exe | `install.bat` window; if still missing, MessageBox kit never prepared |
| `pythonw` crash on startup | MessageBox with stderr |
| DirectML missing after GUI is up | existing GUI error dialog on Run (unchanged) |

## Testing

No GPU. No `Tk()`. No admin.

- `tests/test_tcltk_copy.py`: fake `vendor/tcltk` with dummy `_tkinter.pyd`, `tcl/tcl8.6`, `Lib/site-packages/tkinter/__init__.py`; call `logiscan.tcltk.copy_tcltk(vendor, runtime)`; assert those files land in the temp runtime dir.
- Existing unittest suite unchanged.
- After `prepare.ps1`, `LogiScan.exe` exists at the kit root. Not asserted in CI (no `csc` requirement on every test machine).

## Code shape

| Piece | Role |
|---|---|
| `scripts/LogiScanLauncher/Program.cs` | Stub: auto-fix, then `pythonw -m logiscan.gui` |
| `scripts/prepare.ps1` | Drop NuGet tkinter; add tcltk.msi/lib.msi extract + copy; compile launcher |
| `scripts/install.bat` | Copy `vendor\tcltk` if needed |
| `logiscan/tcltk.py` | Copy helper used by tests and optionally by install/prepare |
| delete `scripts/run.bat`, `scripts/run_gui.bat` | Operators use the EXE |
