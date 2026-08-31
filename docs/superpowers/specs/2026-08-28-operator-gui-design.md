# Operator GUI

A Tkinter operator console for the USB kit. The operator picks the photo folder and the Destination (PO folder tree), clicks Run, and watches each photo: thumbnail, N-of-M progress, and a status row. After the run, leftover photos (anything not moved) are inspectable in the same window: the first leftover is selected, its photo is in the preview pane, and the footer explains why it stayed. Filing rules stay exactly as in `2026-08-28-trailer-photo-filing-design.md`. The GUI drives the same batch as the CLI.

`python -m logiscan` stays CLI-only. The window is a second entry point.

## Non-goals

- Watch mode, review-before-move, or a dry-run / `--apply` split
- A third OCR pass, pausing the batch on failure, or typing trailer/seal by hand
- Changing extract, index, move gates, CSV columns, or OCR hardware rules
- CPU OCR fallback
- Extra pip GUI packages (CustomTkinter, Qt, Dear PyGui)
- Opening the CSV from the window, a hardware-probe button, or editing dest paths
- Screenshot / Tk widget tests

## Window

Layout A (form on top):

```text
Photos        [ path field                    ] [Browse]
Destination   [ path field                    ] [Browse]
[Run] [Cancel]  3 / 12  [========--------]
+--------------------+  +---------------------------+
| photo ~30% width   |  | Filename | Trailer | Seal | Status |
| letterboxed        |  | ...      |         |      |        |
+--------------------+  +---------------------------+
footer: phase / inspect reason
```

- ttk widgets. Title `LogiScan`. Minimum size about 900×560.
- `Browse` uses `tkinter.filedialog.askdirectory`. UNC paths are allowed in the field (paste or browse).
- Treeview columns: `Filename`, `Trailer`, `Seal`, `Status`. Empty cells when a field is unknown. Trailer and Seal still show whatever Pass 2 extracted, even on a leftover. The Status column shows short English (`No truck code`, `Moved`, …), not the CSV machine codes. The Status column is about 200px wide.
- The GUI may call `list_images` before starting the worker and pre-fill every filename with a blank status so the full queue is visible; `run_batch` still lists files itself.
- Leftover rows (anything other than `MOVED`, including blank cancelled rows) use a Treeview tag with dark red foreground (`#8a1c1c`).
- Thumbnail: left pane is about 30% of the body width (grid weights 3 vs 7, column 0 `minsize` about 270). Empty state is still a dark rectangle of that minimum size; the Treeview must not collapse it. The photo is letterboxed in a dark frame, aspect ratio kept, never upscaled. Decode size is the pane’s shorter edge in pixels, not a fixed 280. After an image is set, the Label must not keep character `width`/`height` (Tk would treat those as pixels and clip the bitmap). Keep a Python reference to the `PhotoImage` so Tk does not drop it. During a run this is the photo currently in OCR. After a run it is the selected leftover, loaded from `{photos_dir}/{filename}` (still on disk). Clicking a `Moved` row does not change the preview. Resizing the window by more than about 8px re-decodes the current photo to the new pane; it does not re-run OCR.
- Footer during a run: phase text (`Indexing PO folders…`, `Starting OCR…`) or the last `ERROR` message. After a run with leftovers: `{n} not moved. Click a row to inspect.` then, once a leftover is selected (including auto-select), `{filename} is still in the photos folder. {reason}`. After a run with none leftover: `{n} moved.` Clicking a moved row: `{filename} was moved.`
- After a successful or cancelled run (not engine-init exit 2): mark unprocessed rows `Not processed`, auto-select the first leftover in tree order, scroll it into view, and show its photo. Row clicks while a run is in progress do not steal the preview.
- Idle: Run enabled, Cancel disabled, folder fields and Browse enabled.
- Running: Run disabled, Cancel enabled, folder fields and Browse disabled.
- After a batch (including cancel): idle again, then inspect leftovers as above.

Last-used folders: `logiscan_gui.json` at the kit root (`APP_ROOT`), written when Run starts after both paths validate.

```json
{"photos_dir": "E:\\LogiScan\\photos", "search_root": "D:\\POs"}
```

Missing file: Photos defaults to the kit `photos` folder; Destination starts empty (operator must pick one). Ignore unknown keys. Do not write the file until a validated Run. The JSON key remains `search_root` so older prefs files still load. CLI `--search-root` is unchanged.

## Launch

```text
scripts\run_gui.bat
```

Uses `runtime\python\pythonw.exe` when that file exists, otherwise `pythonw` on PATH. No extra console window. Sets `PYTHONPATH` to the kit root (same as `run.bat`) and Tcl/Tk library env vars (see USB kit).

```text
pythonw -m logiscan.gui
```

`scripts\run.bat` and `python -m logiscan` are unchanged. No `--gui` flag on the CLI.

`pythonw` has no stderr console. `ReportManager` still appends `ocr_report.csv` and `ocr_matches.log`. GUI logging can stay at INFO to nowhere visible; the tree and footer are the operator feedback.

## Architecture

```text
Tk main thread                          worker thread
     |                                        |
     |  Run clicked                           |
     |  save prefs, spawn thread ------------>|
     |                                        | run_batch(config, callbacks)
     |  after() updates  <--------------------| on_phase / on_photo_begin / on_photo_done
     |  thumbnail, row, N/M                   | should_stop between steps
     |                                        |
     |  Cancel -> Event.set() --------------->| current process_image finishes
```

Tk never calls RapidOCR. The worker never touches Tk widgets; it only queues work with `root.after(0, ...)`.

Because the filing work is done, CLI and GUI share one runner. `cli.py` parses args and logs. `gui.py` owns the window. Neither copies the process loop.

| Piece | Role |
|---|---|
| `logiscan/batch.py` | `run_batch`: validate dirs, list photos, index, init `OCRProcessor`, loop `process_image` + `ReportManager.record` |
| `logiscan/cli.py` | argparse, logging, `--check-hardware`, then `run_batch` |
| `logiscan/gui.py` | ttk window, prefs, worker thread, thumbnail, leftover inspect |
| `logiscan/gui_copy.py` | English status labels, leftover reasons, run summary (no Tk) |
| `logiscan/processor.py` and friends | Unchanged filing pipeline |
| `scripts/run_gui.bat` | `pythonw -m logiscan.gui` |
| `scripts/prepare.ps1` | Vendor Tcl/Tk into the embeddable runtime (not a pip package) |

### `run_batch`

Signature shape:

```python
def run_batch(
    config: Config,
    *,
    callbacks: BatchCallbacks | None = None,
    processor_factory: Callable[[Config, FolderIndex], Any] | None = None,
    index_builder: Callable[[Path], FolderIndex] | None = None,
) -> int:
```

Defaults construct the real `OCRProcessor` and `build_index`. Tests pass fakes. Exit codes match the CLI: `1` missing/not-a-dir, `2` DirectML or engine init, `0` otherwise (empty folder, full run, or cancel).

`BatchCallbacks` (all optional):

- `on_phase(message: str)` — index, engine init, counts
- `on_photo_begin(index: int, total: int, path: Path)` — 1-based index, before `process_image`
- `on_photo_done(index: int, total: int, result: ScanResult)` — after record
- `should_stop() -> bool` — checked after validation, after listing, after index, after engine init, and **between** photos (not during `process_image`)

CLI uses `on_photo_done` only to keep the current log lines. GUI uses all four.

Empty photo dir: CLI still exits 0. GUI shows an info dialog and does not start OCR.

## Thumbnail

The GUI's worker-side `on_photo_begin` (still not Tk) opens the **current input file** with Pillow and `pillow_heif.register_heif_opener()` (HEIC/HEIF is not OpenCV-readable). It resizes to fit the preview pane’s shorter edge (`self._preview_max`, an int updated on the Tk thread from the frame size; ignore unmapped sizes under 2px and fall back to 280). Aspect ratio is kept; no upscale. PNG-encode that bitmap. `root.after` delivers those bytes to the Tk thread, which builds the `PhotoImage`.

- Decode failure: gray placeholder; footer may show `Preview failed: {name}`; processing continues.
- Do not OCR for preview. Drop the PNG bytes after the widget is updated.
- After a run, leftover inspect also calls `thumbnail_png` on the Tk thread from `{photos_dir}/{filename}` at the same pane `max_size`. That file is still in the input dir. Decode failure: gray placeholder; keep the inspect footer (do not replace it with `Preview failed`).
- The preview Label is centered in a dark frame that fills the 30% column. Do not set character `width`/`height` on the Label after an image is applied.

## Cancel and close

Cancel sets a threading event. The photo already inside `process_image` always finishes (including temp-JPEG cleanup on failure). Remaining files are skipped; they stay in the input dir. After the worker returns, those skipped rows are leftovers: Status `Not processed`, inspectable like any other leftover.

Closing the window while a run is in progress: intercept `WM_DELETE_WINDOW`, set the cancel event, show `Stopping…` in the footer, and only then `destroy()` the root after the worker thread joins. Do not kill the process mid-`process_image`.

## Errors

| Situation | GUI |
|---|---|
| Photos or Destination missing / not a directory | Error dialog, no thread, no OCR |
| Empty photo dir | Info dialog, exit path 0 |
| `DirectMLUnavailableError` or other engine init failure | Error dialog, abort run, same as CLI exit 2 |
| Per-photo `CONVERT_ERROR` / `NO_TRAILER` / … / `MOVED` | English Status cell; leftover rows tinted; not a dialog |
| Per-photo `ERROR` | Row plus footer with `result.error` during the run; inspect footer after the run |
| Thumbnail decode fail | Placeholder; run continues |
| Prefs file unreadable | Ignore, use defaults |
| After run, any not-moved photo | First leftover auto-selected; click other leftover rows to inspect |

One dialog at a time. Do not pop a dialog per failed photo.

## Status column (English)

CSV and logs keep machine statuses. The tree shows:

| Status | Label |
|---|---|
| `NO_TRAILER` | No truck code |
| `AMBIGUOUS_TRAILER` | Several truck codes |
| `NO_SEAL` | No seal |
| `AMBIGUOUS_SEAL` | Several seals |
| `NO_FOLDER` | No PO folder |
| `AMBIGUOUS_FOLDER` | Several PO folders |
| `DEST_EXISTS` | Already filed |
| `CONVERT_ERROR` | Could not open |
| `ERROR` | Error |
| (blank / cancelled) | Not processed |
| `MOVED` | Moved |

## USB kit (Tcl/Tk)

Embeddable CPython 3.12 does not ship `tkinter`. `prepare.ps1` already downloads `python-3.12.10-embed-amd64.zip`. Add a step that downloads the matching official NuGet package `python` 3.12.10 (`https://www.nuget.org/api/v2/package/python/3.12.10`, a zip) and copies these into `runtime/python/`:

- `_tkinter.pyd` next to `python.exe`
- every `tcl86*.dll` and `tk86*.dll` from the package (usually `tools/` or `tools/DLLs/`) next to `python.exe`
- the package `tcl` directory (`tcl8.6`, `tk8.6`) to `runtime/python/tcl`
- the `tkinter` package to `runtime/python/Lib/site-packages/tkinter`

`python312._pth` already has `Lib\site-packages` and `import site`. Do not add a pip GUI dependency. Pillow stays a transitive install via `pillow-heif` (`PIL.ImageTk` needs both Pillow and tkinter).

`run_gui.bat` sets:

```text
TCL_LIBRARY=%ROOT%\runtime\python\tcl\tcl8.6
TK_LIBRARY=%ROOT%\runtime\python\tcl\tk8.6
```

`install.bat` does not need new wheels. `prepare.ps1` completion text mentions `scripts\run_gui.bat` next to `run.bat`.

If `_tkinter` fails to import at GUI startup: error dialog (or a MessageBox via ctypes if Tk itself cannot start) telling the operator to re-run `prepare.ps1` on a trusted PC.

## Testing

No GPU in GUI tests. Existing GPU / index / CLI tests stay.

- `tests/test_batch.py`: inject a fake processor (returns `ScanResult`s, no OCR). Assert `process_image` is called once per listed photo and each result is recorded. Empty input → 0. Missing dir → 1. `should_stop` after the first photo → later photos skipped. `processor_factory` raising `DirectMLUnavailableError` → 2.
- `tests/test_gui_prefs.py`: read/write `logiscan_gui.json` in `tmp_path`; missing file defaults; garbage JSON ignored.
- `tests/test_gui_copy.py`: English labels, leftover reasons, leftover vs `MOVED`, run summary, inspect footer. No Tk.
- `tests/test_preview.py`: thumbnail PNG at 280 and 480, `pane_max_size` / `pane_resized`. No Tk.
- Do not instantiate `Tk()` in CI.

CLI tests that spawn `python -m logiscan` keep working; `main()` still returns the same codes.
