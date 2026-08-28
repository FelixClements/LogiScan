# Operator GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a USB-portable Tkinter operator console that picks two folders, runs the existing filing batch, and shows thumbnail, progress, and per-photo status.

**Architecture:** Extract `run_batch` from `cli.py` so CLI and GUI share one loop. Prefs and thumbnail helpers stay importable without Tk. `gui.py` owns the ttk window and a worker thread; Tk never calls RapidOCR. Tcl/Tk is copied into the embeddable runtime by `prepare.ps1`, not installed via pip.

**Tech Stack:** Python 3.12, stdlib `tkinter`/`ttk`/`unittest`, existing RapidOCR + Pillow/pillow-heif, Windows USB kit (`pythonw.exe`).

## Global Constraints

- Filing rules, statuses, CSV columns, and DirectML hard-fail stay as in `docs/superpowers/specs/2026-08-28-trailer-photo-filing-design.md`.
- No extra pip GUI packages (no CustomTkinter, Qt, Dear PyGui).
- `python -m logiscan` stays CLI-only. Window is `pythonw -m logiscan.gui`.
- No `--gui` flag, no watch mode, no review-before-move, no dry-run/`--apply`.
- Cancel is checked between photos, never during `process_image`.
- Do not instantiate `Tk()` in tests.
- Tests in this repo are `unittest` (`python -m unittest tests.test_* -v`), not pytest.
- Never write `git config`. If commit fails on missing identity, leave files staged and continue.

## File map

| File | Responsibility |
|---|---|
| `logiscan/gui_prefs.py` | Read/write `logiscan_gui.json` (no Tk) |
| `logiscan/batch.py` | `BatchCallbacks`, `run_batch` |
| `logiscan/preview.py` | Input file → PNG thumbnail bytes (Pillow, no Tk) |
| `logiscan/gui.py` | ttk window, worker thread, dialogs |
| `logiscan/cli.py` | argparse + logging + `run_batch` |
| `scripts/run_gui.bat` | `pythonw -m logiscan.gui` + Tcl/Tk env |
| `scripts/prepare.ps1` | Vendor Tcl/Tk from the matching Python NuGet package |
| `tests/test_gui_prefs.py` | Prefs round-trip |
| `tests/test_batch.py` | Orchestration with a fake processor |
| `tests/test_preview.py` | Thumbnail PNG from a tiny JPEG |
| `tests/test_report.py` | Patch `logiscan.batch.OCRProcessor` after the CLI split |

`logiscan/gui_prefs.py` and `logiscan/preview.py` are split out of `gui.py` so tests never import tkinter. Filing modules (`processor.py`, `extract.py`, `index.py`, `iso.py`, `images.py`, `ocr.py`) are not modified except if a task below names them (none do).

---

### Task 1: GUI prefs helper

**Files:**
- Create: `logiscan/gui_prefs.py`
- Test: `tests/test_gui_prefs.py`

**Interfaces:**
- Consumes: `pathlib.Path`, stdlib `json`
- Produces:
  - `DEFAULT_PHOTOS = Path("photos")`
  - `PREFS_NAME = "logiscan_gui.json"`
  - `class GuiPrefs: photos_dir: Path; search_root: Path | None`
  - `def prefs_path(root: Path) -> Path`
  - `def load_prefs(root: Path) -> GuiPrefs`
  - `def save_prefs(root: Path, prefs: GuiPrefs) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gui_prefs.py`:

```python
"""GUI folder prefs without Tk."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.gui_prefs import GuiPrefs, load_prefs, prefs_path, save_prefs


class GuiPrefsTests(unittest.TestCase):
    def test_missing_file_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("photos"))
            self.assertIsNone(prefs.search_root)

    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            save_prefs(
                root,
                GuiPrefs(photos_dir=Path("E:/photos"), search_root=Path("D:/POs")),
            )
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("E:/photos"))
            self.assertEqual(prefs.search_root, Path("D:/POs"))
            payload = json.loads(prefs_path(root).read_text(encoding="utf-8"))
            self.assertEqual(payload["photos_dir"], str(Path("E:/photos")))
            self.assertEqual(payload["search_root"], str(Path("D:/POs")))

    def test_garbage_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prefs_path(root).write_text("{not json", encoding="utf-8")
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("photos"))
            self.assertIsNone(prefs.search_root)

    def test_unknown_keys_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prefs_path(root).write_text(
                '{"photos_dir": "x", "search_root": "y", "extra": 1}',
                encoding="utf-8",
            )
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("x"))
            self.assertEqual(prefs.search_root, Path("y"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_gui_prefs -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'logiscan.gui_prefs'`

- [ ] **Step 3: Write minimal implementation**

Create `logiscan/gui_prefs.py`:

```python
"""Last-used folder paths for the operator GUI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PREFS_NAME = "logiscan_gui.json"
DEFAULT_PHOTOS = Path("photos")


@dataclass(frozen=True)
class GuiPrefs:
    photos_dir: Path = DEFAULT_PHOTOS
    search_root: Path | None = None


def prefs_path(root: Path) -> Path:
    return root / PREFS_NAME


def load_prefs(root: Path) -> GuiPrefs:
    path = prefs_path(root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return GuiPrefs()
    if not isinstance(raw, dict):
        return GuiPrefs()
    photos = raw.get("photos_dir")
    search = raw.get("search_root")
    photos_dir = Path(photos) if isinstance(photos, str) and photos else DEFAULT_PHOTOS
    search_root = Path(search) if isinstance(search, str) and search else None
    return GuiPrefs(photos_dir=photos_dir, search_root=search_root)


def save_prefs(root: Path, prefs: GuiPrefs) -> None:
    payload = {
        "photos_dir": str(prefs.photos_dir),
        "search_root": str(prefs.search_root) if prefs.search_root is not None else "",
    }
    prefs_path(root).write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_gui_prefs -v`

Expected: four tests PASS

- [ ] **Step 5: Commit**

```bash
git add logiscan/gui_prefs.py tests/test_gui_prefs.py
git commit -m "Add GUI folder prefs helper."
```

---

### Task 2: Shared `run_batch`

**Files:**
- Create: `logiscan/batch.py`
- Test: `tests/test_batch.py`

**Interfaces:**
- Consumes: `Config`, `ScanResult`, `STATUS_ERROR`, `DirectMLUnavailableError`, `list_images`, `build_index`, `FolderIndex`, `OCRProcessor`, `ReportManager`
- Produces:
  - `def require_dir(path: Path, label: str) -> str | None`
  - `@dataclass class BatchCallbacks` with `on_phase: Callable[[str], None] | None = None`, `on_photo_begin: Callable[[int, int, Path], None] | None = None`, `on_photo_done: Callable[[int, int, ScanResult], None] | None = None`, `should_stop: Callable[[], bool] | None = None`
  - `def run_batch(config: Config, *, callbacks: BatchCallbacks | None = None, processor_factory: Callable[[Config, FolderIndex], Any] | None = None, index_builder: Callable[[Path], FolderIndex] | None = None) -> int`
  - Exit codes: `1` missing/not-a-dir, `2` DirectML or other engine init, `0` empty / complete / cancelled

Photo index in `on_photo_begin` / `on_photo_done` is **1-based**. `should_stop` is checked after validation, after listing, after index, after engine init, and between photos (not during `process_image`). Empty photo dir returns `0` without building the index or constructing a processor.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch.py`:

```python
"""run_batch orchestration without OCR."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.batch import BatchCallbacks, run_batch
from logiscan.config import STATUS_MOVED, STATUS_NO_TRAILER, Config, ScanResult
from logiscan.hardware import DirectMLUnavailableError
from logiscan.index import FolderIndex


class FakeProcessor:
    def __init__(self, mapping: dict[str, ScanResult]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def process_image(self, path: Path) -> ScanResult:
        self.calls.append(path.name)
        return self.mapping[path.name]


class RunBatchTests(unittest.TestCase):
    def _layout(self) -> tuple[Path, Path, Path, Config]:
        root = Path(self._temp.name)
        photos = root / "photos"
        search = root / "pos"
        photos.mkdir()
        search.mkdir()
        config = Config(
            photos_dir=photos,
            search_root=search,
            log_path=root / "ocr_matches.log",
            report_path=root / "ocr_report.csv",
            model_dir=root / "models" / "rapidocr",
        )
        return photos, search, root, config

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_missing_photos_dir_exits_1(self) -> None:
        _, search, root, _ = self._layout()
        config = Config(
            photos_dir=root / "missing",
            search_root=search,
            log_path=root / "ocr_matches.log",
            report_path=root / "ocr_report.csv",
        )
        self.assertEqual(run_batch(config), 1)

    def test_empty_input_exits_0_without_factory(self) -> None:
        _photos, _search, _root, config = self._layout()
        calls: list[str] = []

        def factory(config, index):
            calls.append("factory")
            raise AssertionError("processor should not be built")

        self.assertEqual(run_batch(config, processor_factory=factory), 0)
        self.assertEqual(calls, [])

    def test_processes_each_photo_and_records(self) -> None:
        photos, _search, root, config = self._layout()
        (photos / "a.jpg").write_bytes(b"x")
        (photos / "b.jpg").write_bytes(b"x")
        fake = FakeProcessor(
            {
                "a.jpg": ScanResult("t", "a.jpg", status=STATUS_MOVED, trailer="T", seal="1"),
                "b.jpg": ScanResult("t", "b.jpg", status=STATUS_NO_TRAILER),
            }
        )
        begun: list[tuple[int, str]] = []
        done: list[str] = []

        def factory(config, index):
            self.assertIsInstance(index, FolderIndex)
            return fake

        code = run_batch(
            config,
            callbacks=BatchCallbacks(
                on_photo_begin=lambda i, n, path: begun.append((i, path.name)),
                on_photo_done=lambda i, n, result: done.append(result.filename),
            ),
            processor_factory=factory,
            index_builder=lambda root: FolderIndex({}),
        )
        self.assertEqual(code, 0)
        self.assertEqual(fake.calls, ["a.jpg", "b.jpg"])
        self.assertEqual(begun, [(1, "a.jpg"), (2, "b.jpg")])
        self.assertEqual(done, ["a.jpg", "b.jpg"])
        csv_text = config.report_path.read_text(encoding="utf-8")
        self.assertIn("a.jpg", csv_text)
        self.assertIn("b.jpg", csv_text)
        self.assertIn(STATUS_MOVED, csv_text)

    def test_should_stop_after_first_skips_rest(self) -> None:
        photos, _search, _root, config = self._layout()
        (photos / "a.jpg").write_bytes(b"x")
        (photos / "b.jpg").write_bytes(b"x")
        fake = FakeProcessor(
            {
                "a.jpg": ScanResult("t", "a.jpg", status=STATUS_NO_TRAILER),
                "b.jpg": ScanResult("t", "b.jpg", status=STATUS_NO_TRAILER),
            }
        )
        stop_after = {"n": 0}

        def should_stop() -> bool:
            return stop_after["n"] >= 1

        def on_done(i, n, result):
            stop_after["n"] += 1

        code = run_batch(
            config,
            callbacks=BatchCallbacks(should_stop=should_stop, on_photo_done=on_done),
            processor_factory=lambda c, i: fake,
            index_builder=lambda root: FolderIndex({}),
        )
        self.assertEqual(code, 0)
        self.assertEqual(fake.calls, ["a.jpg"])

    def test_directml_error_exits_2(self) -> None:
        photos, _search, _root, config = self._layout()
        (photos / "a.jpg").write_bytes(b"x")

        def factory(config, index):
            raise DirectMLUnavailableError("DmlExecutionProvider is not available")

        self.assertEqual(
            run_batch(
                config,
                processor_factory=factory,
                index_builder=lambda root: FolderIndex({}),
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_batch -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'logiscan.batch'`

- [ ] **Step 3: Write minimal implementation**

Create `logiscan/batch.py`:

```python
"""Shared convert/OCR/file batch used by CLI and GUI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from logiscan.config import STATUS_ERROR, Config, ScanResult
from logiscan.hardware import DirectMLUnavailableError
from logiscan.images import list_images
from logiscan.index import FolderIndex, build_index
from logiscan.processor import OCRProcessor
from logiscan.report import ReportManager

LOGGER = logging.getLogger("logiscan")


@dataclass
class BatchCallbacks:
    on_phase: Callable[[str], None] | None = None
    on_photo_begin: Callable[[int, int, Path], None] | None = None
    on_photo_done: Callable[[int, int, ScanResult], None] | None = None
    should_stop: Callable[[], bool] | None = None


def require_dir(path: Path, label: str) -> str | None:
    if not path.exists():
        return f"{label} does not exist: {path}"
    if not path.is_dir():
        return f"{label} is not a directory: {path}"
    return None


def _stopped(callbacks: BatchCallbacks | None) -> bool:
    return bool(callbacks and callbacks.should_stop and callbacks.should_stop())


def _phase(callbacks: BatchCallbacks | None, message: str) -> None:
    if callbacks and callbacks.on_phase:
        callbacks.on_phase(message)


def run_batch(
    config: Config,
    *,
    callbacks: BatchCallbacks | None = None,
    processor_factory: Callable[[Config, FolderIndex], Any] | None = None,
    index_builder: Callable[[Path], FolderIndex] | None = None,
) -> int:
    for path, label in (
        (config.photos_dir, "Input directory"),
        (config.search_root, "Search root"),
    ):
        error = require_dir(path, label)
        if error:
            LOGGER.error("%s", error)
            return 1
    if _stopped(callbacks):
        return 0

    images = list_images(config.photos_dir, config.image_suffixes)
    if not images:
        LOGGER.warning("No image files in %s", config.photos_dir)
        return 0
    if _stopped(callbacks):
        return 0

    _phase(callbacks, "Indexing PO folders…")
    builder = index_builder or build_index
    index = builder(config.search_root)
    if _stopped(callbacks):
        return 0

    _phase(callbacks, "Starting OCR…")
    factory = processor_factory or (lambda cfg, idx: OCRProcessor(cfg, idx))
    try:
        processor = factory(config, index)
    except DirectMLUnavailableError:
        LOGGER.exception("DirectML iGPU is required; refusing CPU OCR.")
        return 2
    except Exception:
        LOGGER.exception("Failed to initialize the OCR engine.")
        return 2
    if _stopped(callbacks):
        return 0

    reporter = ReportManager(config)
    total = len(images)
    LOGGER.info("Processing %s image(s) from %s", total, config.photos_dir)
    for offset, path in enumerate(images, start=1):
        if _stopped(callbacks):
            return 0
        if callbacks and callbacks.on_photo_begin:
            callbacks.on_photo_begin(offset, total, path)
        result = processor.process_image(path)
        reporter.record(result)
        if callbacks and callbacks.on_photo_done:
            callbacks.on_photo_done(offset, total, result)
        if result.status == STATUS_ERROR or result.error:
            LOGGER.error("%s %s: %s", result.status, result.filename, result.error or "")
        else:
            LOGGER.info(
                "%s %s | trailer=%s seal=%s dest=%s",
                result.status,
                result.filename,
                result.trailer,
                result.seal,
                result.dest_folder,
            )
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_batch -v`

Expected: five tests PASS

- [ ] **Step 5: Commit**

```bash
git add logiscan/batch.py tests/test_batch.py
git commit -m "Extract shared run_batch for CLI and GUI."
```

---

### Task 3: Point CLI at `run_batch`

**Files:**
- Modify: `logiscan/cli.py`
- Modify: `tests/test_report.py` (the `logiscan.cli.OCRProcessor` patch)

**Interfaces:**
- Consumes: `run_batch` from Task 2
- Produces: `main()` still returns 1 / 2 / 0 as today; `--check-hardware` unchanged; `--search-root` still required before `run_batch`

- [ ] **Step 1: Change the existing DML CLI test patch target**

In `tests/test_report.py`, replace the patch in `test_dml_init_failure_exits_2` so it patches the module that will construct `OCRProcessor`:

```python
            with patch(
                "logiscan.batch.OCRProcessor",
                side_effect=DirectMLUnavailableError("DmlExecutionProvider is not available"),
            ):
```

Leave the other CLI tests as they are.

- [ ] **Step 2: Rewrite `logiscan/cli.py` to call `run_batch`**

Replace the file with:

```python
"""CLI for the USB-portable LogiScan trailer photo filer."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from logiscan.batch import run_batch
from logiscan.config import Config
from logiscan.hardware import probe_hardware

LOGGER = logging.getLogger("logiscan")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert HEIC, OCR trailer and seal, and file photos into PO folders."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("photos"))
    parser.add_argument("--search-root", type=Path, default=None)
    parser.add_argument("--log-file", type=Path, default=Path("ocr_matches.log"))
    parser.add_argument("--report-file", type=Path, default=Path("ocr_report.csv"))
    parser.add_argument(
        "--check-hardware",
        action="store_true",
        help="Print DirectML / OpenCL status and exit non-zero if DML is missing.",
    )
    return parser.parse_args(argv)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging()
    if args.check_hardware:
        return probe_hardware()

    if args.search_root is None:
        LOGGER.error("--search-root is required")
        return 1

    config = Config(
        photos_dir=args.input_dir,
        search_root=args.search_root,
        log_path=args.log_file,
        report_path=args.report_file,
    ).resolved()
    return run_batch(config)
```

- [ ] **Step 3: Run CLI tests**

Run: `python -m unittest tests.test_report.CliTests -v`

Expected: all five CLI tests PASS (`missing_search_root`, `missing_input_dir`, `empty_input_dir`, `check_hardware`, `dml_init_failure`)

- [ ] **Step 4: Commit**

```bash
git add logiscan/cli.py tests/test_report.py
git commit -m "Drive the CLI through run_batch."
```

---

### Task 4: Thumbnail bytes (no Tk)

**Files:**
- Create: `logiscan/preview.py`
- Test: `tests/test_preview.py`

**Interfaces:**
- Consumes: Pillow, `pillow_heif.register_heif_opener` for `.heic`/`.heif`
- Produces: `def thumbnail_png(path: Path, max_size: int = 280) -> bytes` — PNG bytes of a letterboxed-to-fit image, no upscale; raises `ValueError` if the file cannot be decoded

- [ ] **Step 1: Write the failing tests**

Create `tests/test_preview.py`:

```python
"""Thumbnail PNG helper without Tk."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from logiscan.preview import thumbnail_png


class ThumbnailPngTests(unittest.TestCase):
    def test_jpeg_fits_max_size(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "wide.jpg"
            Image.new("RGB", (800, 200), color=(10, 20, 30)).save(path, "JPEG")
            data = thumbnail_png(path, max_size=280)
            out = Image.open(io.BytesIO(data))
            self.assertEqual(out.format, "PNG")
            self.assertLessEqual(out.size[0], 280)
            self.assertLessEqual(out.size[1], 280)
            self.assertEqual(out.size[0], 280)
            self.assertEqual(out.size[1], 70)

    def test_small_image_not_upscaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "tiny.jpg"
            Image.new("RGB", (40, 30), color=(1, 2, 3)).save(path, "JPEG")
            out = Image.open(io.BytesIO(thumbnail_png(path, max_size=280)))
            self.assertEqual(out.size, (40, 30))

    def test_unreadable_raises(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bad.jpg"
            path.write_bytes(b"not-an-image")
            with self.assertRaises(ValueError):
                thumbnail_png(path)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_preview -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'logiscan.preview'`

- [ ] **Step 3: Write minimal implementation**

Create `logiscan/preview.py`:

```python
"""Decode an input photo to PNG thumbnail bytes (no Tk)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

HEIF_SUFFIXES = {".heic", ".heif"}


def thumbnail_png(path: Path, max_size: int = 280) -> bytes:
    from PIL import Image

    if path.suffix.lower() in HEIF_SUFFIXES:
        import pillow_heif

        pillow_heif.register_heif_opener()
    try:
        image = Image.open(path)
        rgb = image.convert("RGB")
    except Exception as exc:
        raise ValueError(f"Unreadable or corrupted image: {path.name}") from exc
    rgb.thumbnail((max_size, max_size))
    buffer = BytesIO()
    rgb.save(buffer, format="PNG")
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_preview -v`

Expected: three tests PASS

- [ ] **Step 5: Commit**

```bash
git add logiscan/preview.py tests/test_preview.py
git commit -m "Add Pillow thumbnail helper for the GUI preview."
```

---

### Task 5: Vendor Tcl/Tk and `run_gui.bat`

**Files:**
- Modify: `scripts/prepare.ps1`
- Create: `scripts/run_gui.bat`
- Modify: `scripts/prepare.ps1` completion banner (mention `run_gui.bat`)

**Interfaces:**
- Consumes: existing embeddable CPython 3.12.10 layout in `runtime/python`
- Produces: `_tkinter.pyd`, `tcl86*.dll`, `tk86*.dll`, `runtime/python/tcl/`, `Lib/site-packages/tkinter` in the USB runtime; `scripts/run_gui.bat` launching `pythonw -m logiscan.gui` with `TCL_LIBRARY` / `TK_LIBRARY`

There is no unittest for this task. Verify by inspecting files after a local `prepare.ps1` if a runtime already exists; otherwise review the script and confirm `run_gui.bat` matches `run.bat` structure.

- [ ] **Step 1: Add a Tcl/Tk copy step to `scripts/prepare.ps1`**

After the embed zip is extracted (the block that writes `python*._pth`) and **before** get-pip, insert:

```powershell
Write-Host "==> Vendoring Tcl/Tk from Python NuGet $PythonVersion"
$nugetName = "python.$PythonVersion.nupkg"
$nugetZip = Join-Path $StageDir $nugetName
Get-RemoteFile -Url "https://www.nuget.org/api/v2/package/python/$PythonVersion" -Destination $nugetZip
$nugetExtract = Join-Path $StageDir "python-nuget-$PythonVersion"
if (-not (Test-Path (Join-Path $RuntimeDir "_tkinter.pyd"))) {
    if (Test-Path $nugetExtract) { Remove-Item -Recurse -Force $nugetExtract }
    New-Item -ItemType Directory -Force -Path $nugetExtract | Out-Null
    Expand-Archive -Path $nugetZip -DestinationPath $nugetExtract -Force
    $tkinterPyd = Get-ChildItem -Path $nugetExtract -Recurse -Filter "_tkinter.pyd" | Select-Object -First 1
    if (-not $tkinterPyd) { throw "_tkinter.pyd missing from Python NuGet package" }
    Copy-Item -Force $tkinterPyd.FullName (Join-Path $RuntimeDir "_tkinter.pyd")
    $dllDir = $tkinterPyd.DirectoryName
    Get-ChildItem -Path $dllDir -Filter "tcl86*.dll" | ForEach-Object { Copy-Item -Force $_.FullName $RuntimeDir }
    Get-ChildItem -Path $dllDir -Filter "tk86*.dll" | ForEach-Object { Copy-Item -Force $_.FullName $RuntimeDir }
    $tcl86 = Get-ChildItem -Path $nugetExtract -Recurse -Directory -Filter "tcl8.6" | Select-Object -First 1
    if (-not $tcl86) { throw "tcl8.6 missing from Python NuGet package" }
    $tclDest = Join-Path $RuntimeDir "tcl"
    if (Test-Path $tclDest) { Remove-Item -Recurse -Force $tclDest }
    Copy-Item -Recurse -Force $tcl86.Parent.FullName $tclDest
    $tkinterPkg = Get-ChildItem -Path $nugetExtract -Recurse -Directory -Filter "tkinter" |
        Where-Object { Test-Path (Join-Path $_.FullName "__init__.py") } |
        Select-Object -First 1
    if (-not $tkinterPkg) { throw "tkinter package missing from Python NuGet package" }
    $siteTk = Join-Path $RuntimeDir "Lib\site-packages\tkinter"
    New-Item -ItemType Directory -Force -Path (Split-Path $siteTk) | Out-Null
    if (Test-Path $siteTk) { Remove-Item -Recurse -Force $siteTk }
    Copy-Item -Recurse -Force $tkinterPkg.FullName $siteTk
}
```

Keep `$PythonVersion = "3.12.10"` as it already is. Do not add pip GUI packages.

Replace the final `Write-Host "  scripts\run.bat"` banner so it also prints `scripts\run_gui.bat`.

- [ ] **Step 2: Create `scripts/run_gui.bat`**

```bat
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
```

- [ ] **Step 3: If `runtime/python/python.exe` already exists locally, re-run prepare or run the new copy block and confirm these paths exist**

- `runtime/python/_tkinter.pyd`
- `runtime/python/tcl/tcl8.6`
- `runtime/python/tcl/tk8.6`
- `runtime/python/Lib/site-packages/tkinter/__init__.py`

Then: `runtime\python\python.exe -c "import tkinter; print(tkinter.TkVersion)"`

Expected: prints a Tk version (8.6) with no traceback.

If this machine has no runtime yet, skip the live import and rely on code review of the copy step.

- [ ] **Step 4: Commit**

```bash
git add scripts/prepare.ps1 scripts/run_gui.bat
git commit -m "Vendor Tcl/Tk into the USB runtime and add run_gui.bat."
```

---

### Task 6: Operator window

**Files:**
- Create: `logiscan/gui.py`

**Interfaces:**
- Consumes: `GuiPrefs` / `load_prefs` / `save_prefs` (Task 1), `run_batch` / `BatchCallbacks` / `require_dir` (Task 2), `thumbnail_png` (Task 4), `APP_ROOT`, `Config`, `list_images`
- Produces: `def main() -> int` and `python -m logiscan.gui` entry (`if __name__ == "__main__"`)

Layout A from the spec: Photos and PO root rows with Browse; Run / Cancel / `N / M` / progress bar; thumbnail left (~280px); Treeview columns `Filename`, `Trailer`, `Seal`, `Status`; footer. ttk. Title `LogiScan`. Minimum size 900×560.

Idle: Run on, Cancel off, fields enabled. Running: opposite, fields disabled. Prefs saved at kit root after both paths validate, before starting the worker. Empty photo dir: info dialog, no worker. Bad dirs: error dialog. Engine init exit 2: error dialog. Per-photo failures: tree only. `ERROR` also sets footer to `result.error`. Thumbnail failure: gray placeholder + footer `Preview failed: {name}`. Cancel: threading.Event, joined after current photo. Close while running: `WM_DELETE_WINDOW` sets cancel, footer `Stopping…`, `destroy()` only after the worker joins.

Import tkinter only inside `main()`. Nest the `App` class in `main()` after that import so `pythonw -m logiscan.gui` can show the ctypes MessageBox when Tcl/Tk was not vendored. Do not import tkinter at module top.

- [ ] **Step 1: Write `logiscan/gui.py`**

Create this file. Import tkinter in a try/except at module top so `class App` is only defined when Tcl/Tk is present. `pythonw` still reaches `main()` and can MessageBox on ImportError.

```python
"""Tkinter operator console for the USB-portable LogiScan filer."""

from __future__ import annotations

import base64
import threading
from pathlib import Path

from logiscan.batch import BatchCallbacks, require_dir, run_batch
from logiscan.config import APP_ROOT, STATUS_ERROR, Config
from logiscan.gui_prefs import GuiPrefs, load_prefs, save_prefs
from logiscan.images import list_images
from logiscan.preview import thumbnail_png

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]


def _message_box(title: str, text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        print(f"{title}: {text}")


if tk is not None:

    class App(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("LogiScan")
            self.minsize(900, 560)
            self._stop = threading.Event()
            self._worker: threading.Thread | None = None
            self._closing = False
            self._photo_image: tk.PhotoImage | None = None
            prefs = load_prefs(APP_ROOT)
            self._build(prefs)
            self.protocol("WM_DELETE_WINDOW", self._on_close)
            self._set_running(False)

    def _build(self, prefs: GuiPrefs) -> None:
        pad = {"padx": 8, "pady": 4}
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Photos", width=10).grid(row=0, column=0, sticky="w", **pad)
        self.photos_var = tk.StringVar(value=str(prefs.photos_dir))
        ttk.Entry(top, textvariable=self.photos_var).grid(row=0, column=1, sticky="ew", **pad)
        self.photos_browse = ttk.Button(top, text="Browse", command=self._browse_photos)
        self.photos_browse.grid(row=0, column=2, **pad)
        ttk.Label(top, text="PO root", width=10).grid(row=1, column=0, sticky="w", **pad)
        self.search_var = tk.StringVar(
            value="" if prefs.search_root is None else str(prefs.search_root)
        )
        ttk.Entry(top, textvariable=self.search_var).grid(row=1, column=1, sticky="ew", **pad)
        self.search_browse = ttk.Button(top, text="Browse", command=self._browse_search)
        self.search_browse.grid(row=1, column=2, **pad)
        top.columnconfigure(1, weight=1)

        controls = ttk.Frame(self)
        controls.pack(fill="x")
        self.run_btn = ttk.Button(controls, text="Run", command=self._on_run)
        self.run_btn.pack(side="left", **pad)
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self._on_cancel)
        self.cancel_btn.pack(side="left", **pad)
        self.count_var = tk.StringVar(value="0 / 0")
        ttk.Label(controls, textvariable=self.count_var).pack(side="left", **pad)
        self.progress = ttk.Progressbar(controls, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, **pad)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.preview = tk.Label(body, width=40, height=18, bg="#222222", fg="#aaaaaa", text="")
        self.preview.pack(side="left", fill="y", padx=8, pady=4)
        columns = ("filename", "trailer", "seal", "status")
        self.tree = ttk.Treeview(body, columns=columns, show="headings")
        for key, heading in (
            ("filename", "Filename"),
            ("trailer", "Trailer"),
            ("seal", "Seal"),
            ("status", "Status"),
        ):
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=140 if key != "filename" else 220)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, pady=4)
        scroll.pack(side="left", fill="y")

        self.footer_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.footer_var).pack(fill="x", **pad)

    def _browse_photos(self) -> None:
        chosen = filedialog.askdirectory(title="Photos")
        if chosen:
            self.photos_var.set(chosen)

    def _browse_search(self) -> None:
        chosen = filedialog.askdirectory(title="PO root")
        if chosen:
            self.search_var.set(chosen)

    def _set_running(self, running: bool) -> None:
        state_run = "disabled" if running else "normal"
        state_cancel = "normal" if running else "disabled"
        state_fields = "disabled" if running else "normal"
        self.run_btn.configure(state=state_run)
        self.cancel_btn.configure(state=state_cancel)
        self.photos_browse.configure(state=state_fields)
        self.search_browse.configure(state=state_fields)

    def _on_run(self) -> None:
        photos = Path(self.photos_var.get().strip())
        search = Path(self.search_var.get().strip())
        if not self.search_var.get().strip():
            messagebox.showerror("LogiScan", "PO root is required")
            return
        for path, label in ((photos, "Input directory"), (search, "Search root")):
            error = require_dir(path, label)
            if error:
                messagebox.showerror("LogiScan", error)
                return
        config = Config(photos_dir=photos, search_root=search).resolved()
        images = list_images(config.photos_dir, config.image_suffixes)
        if not images:
            messagebox.showinfo("LogiScan", f"No image files in {config.photos_dir}")
            return
        save_prefs(APP_ROOT, GuiPrefs(photos_dir=photos, search_root=search))
        for item in self.tree.get_children():
            self.tree.delete(item)
        for path in images:
            self.tree.insert("", "end", iid=path.name, values=(path.name, "", "", ""))
        self.progress["maximum"] = len(images)
        self.progress["value"] = 0
        self.count_var.set(f"0 / {len(images)}")
        self.footer_var.set("")
        self._stop.clear()
        self._set_running(True)
        self._worker = threading.Thread(target=self._worker_main, args=(config,), daemon=True)
        self._worker.start()

    def _worker_main(self, config: Config) -> None:
        def on_phase(message: str) -> None:
            self.after(0, lambda m=message: self.footer_var.set(m))

        def on_begin(index: int, total: int, path: Path) -> None:
            png: bytes | None
            try:
                png = thumbnail_png(path)
            except ValueError:
                png = None
            self.after(
                0,
                lambda i=index, n=total, p=path, b=png: self._photo_begin_ui(i, n, p, b),
            )

        def on_done(index: int, total: int, result) -> None:
            self.after(
                0,
                lambda i=index, n=total, r=result: self._photo_done_ui(i, n, r),
            )

        code = run_batch(
            config,
            callbacks=BatchCallbacks(
                on_phase=on_phase,
                on_photo_begin=on_begin,
                on_photo_done=on_done,
                should_stop=self._stop.is_set,
            ),
        )
        self.after(0, lambda: self._batch_finished(code))

    def _photo_begin_ui(self, index: int, total: int, path: Path, png: bytes | None) -> None:
        self.count_var.set(f"{index} / {total}")
        self.progress["value"] = index - 1
        if path.name in self.tree.get_children():
            self.tree.set(path.name, "status", "…")
            self.tree.see(path.name)
        if png is None:
            self._photo_image = None
            self.preview.configure(image="", text=path.name, bg="#222222")
            self.footer_var.set(f"Preview failed: {path.name}")
            return
        self._photo_image = tk.PhotoImage(data=base64.standard_b64encode(png))
        self.preview.configure(image=self._photo_image, text="")

    def _photo_done_ui(self, index: int, total: int, result) -> None:
        self.progress["value"] = index
        self.count_var.set(f"{index} / {total}")
        iid = result.filename
        if iid in self.tree.get_children():
            self.tree.item(
                iid,
                values=(
                    result.filename,
                    result.trailer or "",
                    result.seal or "",
                    result.status,
                ),
            )
        if result.status == STATUS_ERROR and result.error:
            self.footer_var.set(result.error)

    def _batch_finished(self, code: int) -> None:
        self._set_running(False)
        if code == 2:
            messagebox.showerror(
                "LogiScan",
                "DirectML iGPU is required; refusing CPU OCR.",
            )
        if self._closing:
            self.destroy()

    def _on_cancel(self) -> None:
        self._stop.set()
        self.footer_var.set("Stopping…")

    def _on_close(self) -> None:
        worker = self._worker
        if worker is not None and worker.is_alive():
            self._closing = True
            self._stop.set()
            self.footer_var.set("Stopping…")
            return
        self.destroy()


def main() -> int:
    if tk is None:
        _message_box(
            "LogiScan",
            "tkinter is missing. Re-run scripts\\prepare.ps1 on a trusted PC.",
        )
        return 1
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Every method from `_build` through `_on_close` must be indented as methods of `class App` (one extra indent under `if tk is not None`). `_set_running` must also disable/enable the two `ttk.Entry` widgets; keep references (`self.photos_entry`, `self.search_entry`) when creating them.

- [ ] **Step 2: Run non-Tk tests to confirm nothing imported tkinter accidentally**

Run: `python -m unittest tests.test_gui_prefs tests.test_batch tests.test_preview tests.test_report.CliTests -v`

Expected: all PASS

- [ ] **Step 3: Manual GUI smoke (this machine)**

1. `python -m logiscan.gui` (or `scripts\run_gui.bat` if Tcl/Tk is vendored).
2. Confirm layout A: two folder rows, Run/Cancel/progress, thumbnail left, table right.
3. Empty PO root → error dialog.
4. Valid empty photos folder → info dialog, no hang.
5. Start a real run only if DirectML and a search root are available; Cancel after one photo; remaining files stay in input.
6. Close the window during a run: it should stay up with `Stopping…` until the current photo finishes, then exit.

If tkinter is missing until prepare.ps1 is re-run, confirm the MessageBox path instead.

- [ ] **Step 4: Commit**

```bash
git add logiscan/gui.py
git commit -m "Add the Tkinter operator console."
```

---

## Self-review (spec coverage)

| Spec item | Task |
|---|---|
| Layout A, ttk, title, min size, columns, footer | 6 |
| Remember folders in `logiscan_gui.json` | 1, 6 |
| `pythonw -m logiscan.gui`, `run_gui.bat`, no `--gui` | 5, 6 |
| Shared `run_batch`, CLI unchanged flags | 2, 3 |
| Worker thread, `after()`, cancel between photos | 6 |
| Thumbnail via Pillow/HEIF, PNG to Tk, placeholder on fail | 4, 6 |
| Dialogs vs per-photo tree | 6 |
| Close waits for worker | 6 |
| Tcl/Tk vendored from NuGet, no pip GUI dep | 5 |
| Prefs + batch tests, no `Tk()` in CI | 1, 2, 4 |
| `test_dml_init_failure` still exit 2 | 3 |

No watch mode, no dry-run, no CSV button, no hardware-probe button.
