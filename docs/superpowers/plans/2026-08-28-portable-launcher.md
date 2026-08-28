# Portable Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operators double-click `LogiScan.exe` at the USB kit root; a tiny C# stub auto-fixes Tcl/Tk/wheels from the kit then starts the existing GUI.

**Architecture:** Keep embeddable CPython + RapidOCR. `logiscan.tcltk.copy_tcltk` copies staged files from `vendor/tcltk` into `runtime/python`. `prepare.ps1` downloads official 3.12.10 `tcltk.msi` and `lib.msi` (not NuGet), unpacks into the kit without admin, stages `vendor/tcltk`, compiles `LogiScan.exe`. The EXE never freezes OCR.

**Tech Stack:** Python 3.12 embed, C# / .NET Framework `csc.exe`, PowerShell, `msiexec /a`, stdlib `unittest`.

## Global Constraints

- No PyInstaller/Nuitka freeze of RapidOCR, DirectML, or HEIC.
- No install into Program Files; no administrator rights.
- No operator-facing `.bat` at the kit root; delete `scripts/run.bat` and `scripts/run_gui.bat`.
- Filing/OCR pipeline unchanged.
- Tests: `python -m unittest tests.test_* -v` (not pytest). No `Tk()`. No GPU. No admin.
- Never write `git config`. If commit fails on identity, use `git -c user.name="LogiScan" -c user.email="logiscan@local"` for that commit only, or leave staged.

## File map

| File | Responsibility |
|---|---|
| `logiscan/tcltk.py` | `copy_tcltk(vendor, runtime) -> bool` |
| `tests/test_tcltk_copy.py` | Fake vendor → temp runtime |
| `scripts/prepare.ps1` | Replace NuGet tk step; MSI extract; stage vendor/tcltk; compile EXE |
| `scripts/install.bat` | After wheels, `python -m logiscan.tcltk` |
| `scripts/LogiScanLauncher/Program.cs` | WinExe stub |
| `.gitignore` | `LogiScan.exe`, `vendor/tcltk/` |
| delete `scripts/run.bat`, `scripts/run_gui.bat` | Operators use the EXE |

---

### Task 1: Tcl/Tk copy helper

**Files:**
- Create: `logiscan/tcltk.py`
- Test: `tests/test_tcltk_copy.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `pathlib.Path`, `shutil`
- Produces:
  - `def copy_tcltk(vendor: Path, runtime: Path) -> bool`
  - Returns `True` if `runtime / "_tkinter.pyd"` exists after the copy (or already existed).
  - Copies only these relative paths if they exist under `vendor`: `_tkinter.pyd`, `tcl86*.dll` and `tk86*.dll` in vendor root, `tcl/tcl8.6`, `tcl/tk8.6`, `Lib/site-packages/tkinter`.
  - `python -m logiscan.tcltk` uses kit root = parent of `logiscan` package (`APP_ROOT`), vendor = `APP_ROOT / "vendor" / "tcltk"`, runtime = `APP_ROOT / "runtime" / "python"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tcltk_copy.py`:

```python
"""Copy staged Tcl/Tk files into a fake USB runtime."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.tcltk import copy_tcltk


class CopyTcltkTests(unittest.TestCase):
    def test_copies_layout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            vendor = root / "vendor" / "tcltk"
            runtime = root / "runtime" / "python"
            (vendor / "tcl" / "tcl8.6").mkdir(parents=True)
            (vendor / "tcl" / "tk8.6").mkdir(parents=True)
            (vendor / "Lib" / "site-packages" / "tkinter").mkdir(parents=True)
            (vendor / "_tkinter.pyd").write_bytes(b"pyd")
            (vendor / "tcl86t.dll").write_bytes(b"dll")
            (vendor / "tk86t.dll").write_bytes(b"dll")
            (vendor / "tcl" / "tcl8.6" / "init.tcl").write_text("x", encoding="utf-8")
            (vendor / "Lib" / "site-packages" / "tkinter" / "__init__.py").write_text(
                "# tk", encoding="utf-8"
            )
            self.assertTrue(copy_tcltk(vendor, runtime))
            self.assertEqual((runtime / "_tkinter.pyd").read_bytes(), b"pyd")
            self.assertTrue((runtime / "tcl86t.dll").exists())
            self.assertTrue((runtime / "tk86t.dll").exists())
            self.assertTrue((runtime / "tcl" / "tcl8.6" / "init.tcl").exists())
            self.assertTrue(
                (runtime / "Lib" / "site-packages" / "tkinter" / "__init__.py").exists()
            )

    def test_missing_vendor_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            runtime = root / "runtime" / "python"
            runtime.mkdir(parents=True)
            self.assertFalse(copy_tcltk(root / "vendor" / "tcltk", runtime))
            self.assertFalse((runtime / "_tkinter.pyd").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_tcltk_copy -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'logiscan.tcltk'`

- [ ] **Step 3: Write minimal implementation**

Create `logiscan/tcltk.py`:

```python
"""Copy staged Tcl/Tk files from vendor/tcltk into the USB Python runtime."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from logiscan.config import APP_ROOT

TKINTER_PYD = "_tkinter.pyd"


def copy_tcltk(vendor: Path, runtime: Path) -> bool:
    runtime.mkdir(parents=True, exist_ok=True)
    src_pyd = vendor / TKINTER_PYD
    if not src_pyd.is_file() and not (runtime / TKINTER_PYD).is_file():
        return False
    if src_pyd.is_file():
        shutil.copy2(src_pyd, runtime / TKINTER_PYD)
    if vendor.is_dir():
        for dll in vendor.glob("tcl86*.dll"):
            shutil.copy2(dll, runtime / dll.name)
        for dll in vendor.glob("tk86*.dll"):
            shutil.copy2(dll, runtime / dll.name)
        for rel in ("tcl/tcl8.6", "tcl/tk8.6", "Lib/site-packages/tkinter"):
            src = vendor.joinpath(*rel.split("/"))
            dest = runtime.joinpath(*rel.split("/"))
            if src.is_dir():
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
    return (runtime / TKINTER_PYD).is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy vendor/tcltk into runtime/python.")
    parser.parse_args(argv)
    vendor = APP_ROOT / "vendor" / "tcltk"
    runtime = APP_ROOT / "runtime" / "python"
    ok = copy_tcltk(vendor, runtime)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Append to `.gitignore` (keep existing lines):

```
LogiScan.exe
vendor/tcltk/
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_tcltk_copy -v`

Expected: two tests PASS

- [ ] **Step 5: Commit**

```bash
git add logiscan/tcltk.py tests/test_tcltk_copy.py .gitignore
git commit -m "Add Tcl/Tk copy helper for the USB runtime."
```

---

### Task 2: Stage Tcl/Tk from official MSIs in prepare.ps1

**Files:**
- Modify: `scripts/prepare.ps1` (replace the NuGet tkinter block at the `Write-Host "==> Vendoring Tcl/Tk` section through the closing `}` before `$python = Join-Path`)

**Interfaces:**
- Consumes: `Get-RemoteFile`, `$PythonVersion = "3.12.10"`, `$StageDir`, `$RuntimeDir`, `$Root`, `logiscan.tcltk.copy_tcltk` via `python -m logiscan.tcltk`
- Produces: `vendor/tcltk/` with the layout from Task 1; same files in `runtime/python`; no NuGet `python` download for tkinter

- [ ] **Step 1: Delete the NuGet tkinter block**

Remove the entire block that starts with `Write-Host "==> Vendoring Tcl/Tk from Python NuGet"` and downloads `python.$PythonVersion.nupkg` / `Expand-Archive`. Leave the embed `_pth` write in place.

- [ ] **Step 2: Insert MSI download, unpack, stage, copy**

Immediately after writing `python*._pth`, insert:

```powershell
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
if (-not (Test-Path (Join-Path $Root "vendor\tcltk\_tkinter.pyd"))) {
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
    $tcl86 = Get-ChildItem -Path $tclExtract -Recurse -Directory -Filter "tcl8.6" | Select-Object -First 1
    $tk86 = Get-ChildItem -Path $tclExtract -Recurse -Directory -Filter "tk8.6" | Select-Object -First 1
    if (-not $tcl86) { throw "tcl8.6 missing from tcltk.msi extract" }
    if (-not $tk86) { throw "tk8.6 missing from tcltk.msi extract" }
    $vendorTcl = Join-Path $vendorTk "tcl"
    New-Item -ItemType Directory -Force -Path $vendorTcl | Out-Null
    Copy-Item -Recurse -Force $tcl86.FullName (Join-Path $vendorTcl "tcl8.6")
    Copy-Item -Recurse -Force $tk86.FullName (Join-Path $vendorTcl "tk8.6")
    $tkinterPkg = Get-ChildItem -Path $libExtract -Recurse -Directory -Filter "tkinter" |
        Where-Object { Test-Path (Join-Path $_.FullName "__init__.py") } |
        Select-Object -First 1
    if (-not $tkinterPkg) { throw "Lib/tkinter missing from lib.msi extract at $libExtract" }
    $vendorPkg = Join-Path $vendorTk "Lib\site-packages\tkinter"
    New-Item -ItemType Directory -Force -Path (Split-Path $vendorPkg) | Out-Null
    if (Test-Path $vendorPkg) { Remove-Item -Recurse -Force $vendorPkg }
    Copy-Item -Recurse -Force $tkinterPkg.FullName $vendorPkg
}

$python = Join-Path $RuntimeDir "python.exe"
$env:PYTHONPATH = $Root
Write-Host "==> Copying vendor/tcltk into runtime/python"
& $python -m logiscan.tcltk
if ($LASTEXITCODE -ne 0) { throw "logiscan.tcltk copy failed; vendor/tcltk is incomplete" }
```

Keep `$python = Join-Path $RuntimeDir "python.exe"` only once (the original line after the old NuGet block). If the original `$python =` line remains below, delete the duplicate.

Then continue with existing get-pip / wheels (those need `$python`).

- [ ] **Step 3: Smoke the unpack locally if `runtime\python\python.exe` already exists**

Run only if you are on the trusted Windows PC with internet:

```powershell
powershell -NoProfile -File scripts\prepare.ps1
```

Expected: no throw about NuGet/`_tkinter.pyd missing from Python NuGet`; `vendor\tcltk\_tkinter.pyd` exists; `runtime\python\_tkinter.pyd` exists.

```text
runtime\python\python.exe -c "import tkinter; print(tkinter.TkVersion)"
```

Expected: prints `8.6` (or similar) with no traceback.

If `msiexec /a` exits non-zero, stop and report the exit code; do not silently skip Tcl/Tk.

If this machine cannot run prepare (no network), skip the live smoke and rely on code review of the new block.

- [ ] **Step 4: Commit**

```bash
git add scripts/prepare.ps1
git commit -m "Vendor Tcl/Tk from official MSIs instead of NuGet."
```

---

### Task 3: install.bat copies Tcl/Tk

**Files:**
- Modify: `scripts/install.bat`

**Interfaces:**
- Consumes: `python -m logiscan.tcltk` from Task 1, existing `%PY%` and `%PYTHONPATH%`
- Produces: after wheels, Tcl/Tk present in runtime when `vendor\tcltk` was staged

- [ ] **Step 1: Insert tcltk copy before the hardware probe**

In `scripts/install.bat`, after the onnxruntime-directml install succeeds and **before** `echo Hardware probe:`, insert:

```bat
echo Copying Tcl/Tk into the USB Python if needed...
"%PY%" -m logiscan.tcltk
if errorlevel 1 (
  echo Tcl/Tk copy failed. Re-run scripts\prepare.ps1 on a trusted PC so vendor\tcltk is staged.
  exit /b 1
)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/install.bat
git commit -m "Copy staged Tcl/Tk during offline install."
```

---

### Task 4: C# LogiScan.exe stub

**Files:**
- Create: `scripts/LogiScanLauncher/Program.cs`
- Modify: `scripts/prepare.ps1` (compile step near the end, before the “Prepare complete” banner)

**Interfaces:**
- Consumes: kit root = EXE directory; `scripts\install.bat`; `runtime\python\python.exe` / `pythonw.exe`; `python -m logiscan.tcltk`
- Produces: `LogiScan.exe` at kit root (WinExe)

- [ ] **Step 1: Write `scripts/LogiScanLauncher/Program.cs`**

```csharp
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    static int Main()
    {
        string kit = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(
            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        Directory.SetCurrentDirectory(kit);
        string python = Path.Combine(kit, "runtime", "python", "python.exe");
        string pythonw = Path.Combine(kit, "runtime", "python", "pythonw.exe");
        string installBat = Path.Combine(kit, "scripts", "install.bat");

        if (!File.Exists(python))
        {
            RunInstall(installBat, kit);
            if (!File.Exists(python))
            {
                MessageBox.Show(
                    "This USB copy was never prepared on a trusted PC with internet.\n\n" +
                    "On a PC with internet run scripts\\prepare.ps1, then copy this folder to the stick.",
                    "LogiScan",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }
        }

        if (!PythonImportOk(python, kit, "tkinter"))
        {
            RunPythonModule(python, kit, "logiscan.tcltk");
            if (!PythonImportOk(python, kit, "tkinter"))
            {
                MessageBox.Show(
                    "Tcl/Tk is not in this kit (vendor\\tcltk missing).\n\n" +
                    "Re-run scripts\\prepare.ps1 on a trusted PC.",
                    "LogiScan",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return 1;
            }
        }

        if (!PythonImportOk(python, kit, "rapidocr"))
        {
            RunInstall(installBat, kit);
        }

        return StartGui(pythonw, kit);
    }

    static void RunInstall(string installBat, string kit)
    {
        if (!File.Exists(installBat))
        {
            return;
        }
        var psi = new ProcessStartInfo
        {
            FileName = installBat,
            WorkingDirectory = kit,
            UseShellExecute = true,
        };
        using (var proc = Process.Start(psi))
        {
            if (proc != null)
            {
                proc.WaitForExit();
            }
        }
    }

    static bool PythonImportOk(string python, string kit, string module)
    {
        var psi = new ProcessStartInfo
        {
            FileName = python,
            Arguments = "-c \"import " + module + "\"",
            WorkingDirectory = kit,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        psi.EnvironmentVariables["PYTHONPATH"] = kit;
        using (var proc = Process.Start(psi))
        {
            if (proc == null)
            {
                return false;
            }
            proc.WaitForExit();
            return proc.ExitCode == 0;
        }
    }

    static void RunPythonModule(string python, string kit, string module)
    {
        var psi = new ProcessStartInfo
        {
            FileName = python,
            Arguments = "-m " + module,
            WorkingDirectory = kit,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        psi.EnvironmentVariables["PYTHONPATH"] = kit;
        using (var proc = Process.Start(psi))
        {
            if (proc != null)
            {
                proc.WaitForExit();
            }
        }
    }

    static int StartGui(string pythonw, string kit)
    {
        if (!File.Exists(pythonw))
        {
            MessageBox.Show(
                "pythonw.exe is missing next to python.exe.",
                "LogiScan",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 1;
        }
        string tcl = Path.Combine(kit, "runtime", "python", "tcl", "tcl8.6");
        string tk = Path.Combine(kit, "runtime", "python", "tcl", "tk8.6");
        var psi = new ProcessStartInfo
        {
            FileName = pythonw,
            Arguments = "-m logiscan.gui",
            WorkingDirectory = kit,
            UseShellExecute = false,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        psi.EnvironmentVariables["PYTHONPATH"] = kit;
        psi.EnvironmentVariables["TCL_LIBRARY"] = tcl;
        psi.EnvironmentVariables["TK_LIBRARY"] = tk;
        using (var proc = Process.Start(psi))
        {
            if (proc == null)
            {
                return 1;
            }
            if (proc.WaitForExit(2000))
            {
                string err = proc.StandardError.ReadToEnd();
                if (proc.ExitCode != 0)
                {
                    MessageBox.Show(
                        string.IsNullOrWhiteSpace(err) ? ("GUI exited " + proc.ExitCode) : err,
                        "LogiScan",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return proc.ExitCode;
                }
            }
        }
        return 0;
    }
}
```

- [ ] **Step 2: Compile at the end of `scripts/prepare.ps1`**

Before the `Write-Host "Prepare complete..."` banner, insert:

```powershell
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
```

Replace the completion banner so it no longer mentions `run.bat` / `run_gui.bat`:

```powershell
Write-Host ""
Write-Host "Prepare complete. Copy this folder to a USB stick, then on the corporate laptop run:"
Write-Host "  scripts\install.bat"
Write-Host "After that, operators double-click LogiScan.exe"
Write-Host "Drop images in photos\ first."
```

- [ ] **Step 3: Compile once locally to verify csc**

```powershell
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo /target:winexe /r:System.Windows.Forms.dll /r:System.dll /out:LogiScan.exe scripts\LogiScanLauncher\Program.cs
```

Expected: exit 0, `LogiScan.exe` exists at the repo root.

Optional: double-click it on this PC after Task 2 smoke (tkinter import works). GUI should open. Close it.

- [ ] **Step 4: Commit**

```bash
git add scripts/LogiScanLauncher/Program.cs scripts/prepare.ps1
git commit -m "Add LogiScan.exe stub compiled during prepare."
```

Do not git-add `LogiScan.exe`.

---

### Task 5: Remove operator bat files

**Files:**
- Delete: `scripts/run.bat`
- Delete: `scripts/run_gui.bat`

**Interfaces:**
- Consumes: Task 4 banner already points at `LogiScan.exe`
- Produces: no `run.bat` / `run_gui.bat` in the tree

- [ ] **Step 1: Delete the files**

```bash
git rm scripts/run.bat scripts/run_gui.bat
```

- [ ] **Step 2: Run non-GPU tests**

Run: `python -m unittest tests.test_tcltk_copy tests.test_gui_prefs tests.test_batch tests.test_preview tests.test_report.CliTests tests.test_extract tests.test_hardware tests.test_images tests.test_index tests.test_iso tests.test_move -v`

Expected: all PASS (same as today’s suite plus tcltk tests). Do not run `tests.test_gpu` unless DirectML is installed.

- [ ] **Step 3: Commit**

```bash
git commit -m "Remove operator .bat launchers in favor of LogiScan.exe."
```

---

## Self-review (spec coverage)

| Spec item | Task |
|---|---|
| Tiny C# stub, not a freeze | 4 |
| Auto-run install.bat if python/wheels missing | 4 |
| Auto `python -m logiscan.tcltk` if tkinter missing | 1, 4 |
| MessageBox only when kit never prepared / vendor empty / pythonw crash | 4 |
| Tcl/Tk from tcltk.msi + lib.msi, no NuGet, no admin Program Files | 2 |
| `vendor/tcltk` + copy into runtime | 1, 2, 3 |
| install.bat copies Tcl/Tk | 3 |
| Delete run.bat / run_gui.bat | 5 |
| `copy_tcltk` tests, no Tk() | 1 |
| csc paths Framework64 then Framework | 4 |
| No prepare.ps1 from the EXE | 4 |
