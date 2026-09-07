# Copy trailer photos into every matching PO folder

When a unique truck code and unique seal are read, LogiScan files the JPEG into **every** PO folder whose filenames contain that truck code. “Several PO folders” is no longer a leftover.

This amends the unique-folder gate in `2026-08-28-trailer-photo-filing-design.md`. The GUI still drives the same batch as the CLI (`2026-08-28-operator-gui-design.md`). OCR, extract, CSV column names, and hardware rules do not change.

A `{TRAILER}_{SEAL}.jpg` pair is meant to be filed once. A second photo of the same pair should find those destination files already present and stay in Photos as **Already filed**.

## Non-goals

- Asking the operator which of the matching folders to use
- Review-before-copy, dry-run, or per-photo dialogs
- New CSV columns or new status codes
- Overwriting a destination file
- Rolling back a copy that already landed after a later copy fails
- Changing trailer/seal extract, the filename index walk, or OCR hardware

## Filing gates

After a unique trailer and unique seal, look up every indexed PO folder for that trailer (resolved parent paths, as today). Sort those paths by `str(path)` so `DestFolder` is stable.

| Matching folders | `{TRAILER}_{SEAL}.jpg` already in any of them | Status | Copies | Original in Photos |
|---|---|---|---|---|
| 0 | — | `NO_FOLDER` | None | Stays |
| 1 or more | No | `MOVED` | Copy into **every** matching folder | Leaves (same archive rules as today) |
| 1 or more | Yes | `DEST_EXISTS` | None. Never overwrite | Stays |

Trailer and seal leftovers still win first (`NO_TRAILER`, `AMBIGUOUS_TRAILER`, `NO_SEAL`, `AMBIGUOUS_SEAL`). Folder lookup does not run when those fire.

`AMBIGUOUS_FOLDER` is not produced on new runs. Keep the constant and the old GUI label (`Several PO folders`) so an old CSV row can still be shown. Do not use that leftover sentence for new results.

Same truck code in several files **in one PO folder** still counts as one folder.

## Destination path

Unchanged per folder:

```text
{po_folder}/{TRAILER}_{SEAL}.jpg
```

Example: `MRSU8692215_48291.jpg`.

## Copy then leave Photos

On `MOVED`:

1. Copy the working JPEG into every matching destination. Do not remove the original until every copy succeeds.
2. Then apply today’s Photos rules: JPEG/JPG original is gone; HEIC/HEIF/PNG original moves to `{photos_dir}/_processed`. Delete any temp JPEG.

One matching folder has the same end state as today’s single-folder move. Several folders means several copies, then Photos is cleared the same way.

On `DEST_EXISTS` and every other leftover: Photos is untouched. Delete any temp JPEG, as today.

If a copy fails after an earlier copy succeeded: status `ERROR`, `DestFolder` empty, `error` set to the exception text, original stays in Photos, keep whatever JPEGs already landed. Do not overwrite. Do not delete successful copies. A later retry of the same trailer+seal then hits `DEST_EXISTS` (the anomaly path below).

## ScanResult and CSV

CSV columns stay:

```text
Timestamp, Filename, Trailer, Seal, DestFolder, Status
```

One photo still produces one `ScanResult` and one CSV row.

`ScanResult.dest_folder` remains a single string. When there are matching folders, join their resolved paths with `"; "` (semicolon, space).

| Status | `DestFolder` |
|---|---|
| `MOVED` | Every matching PO folder, joined |
| `DEST_EXISTS` | Every matching PO folder, joined (one folder: that folder, as today) |
| `NO_FOLDER` and earlier leftovers | Empty |

`ocr_matches.log` still records only `MOVED`. The joined dest list goes on that success line.

## Already filed warning

Table status stays **Already filed** (`DEST_EXISTS`). No popup. No new machine status.

Inspect footer is still `{filename} is still in the photos folder. {reason}`.

| Matching folders | Leftover reason |
|---|---|
| 1 | `A photo for this truck and seal is already in the PO folder.` |
| 2 or more | `This truck code matches more than one PO folder, and a photo for this truck and seal is already in at least one of them.` |

Pass `dest_folder` into `leftover_reason` and `inspect_footer`. Use the extra warning when status is `DEST_EXISTS` and `dest_folder` contains `"; "` (the join separator). One path, missing dest, or `dest_folder=None` keeps today’s sentence. Clicking a `MOVED` row is unchanged: `{filename} was moved.`

CLI/logger: on multi-folder `DEST_EXISTS`, `LOGGER.warning` with that extra sentence plus filename, trailer, seal, and the joined dest list. GUI `pythonw` has no console; the inspect footer is the operator-visible warning.

A successful multi-folder copy is not a leftover. The row is not red.

## Code units

| Unit | Change |
|---|---|
| `FolderIndex.lookup_status` | Return `(list[Path], status)`. 0 folders → `([], "NO_FOLDER")`. 1 or more → `(sorted folders, None)`. Never return `AMBIGUOUS_FOLDER`. |
| `gate_status` | Return `(status, list[Path])`. Trailer/seal leftovers and `NO_FOLDER` use an empty list. Any existing dest → `DEST_EXISTS` plus the folder list. Otherwise `MOVED` plus the folder list. |
| Copy/commit | Copy working JPEG to each dest, then archive/remove the original. |
| `ScanResult.dest_folder` | Joined path list when folders were known. |
| `leftover_reason` / `inspect_footer` | Extra `DEST_EXISTS` sentence when dest lists more than one folder. GUI passes `result.dest_folder`. |
| `ReportManager` | Unchanged CSV columns; success log still `MOVED` only. |

## README

Replace the unique-folder leftover wording. A truck that matches several PO folders is copied to each of them. Ambiguous trailer, missing seal, no PO folder, or an already-filed dest still leaves the original in Photos.

## Testing

No GPU. No Tk. Temp directories, same style as `tests/test_index.py`, `tests/test_move.py`, `tests/test_gui_copy.py`.

- Two PO folders for one truck return both folders, not `AMBIGUOUS_FOLDER`. Duplicates in one folder still count as one. Unknown truck is `NO_FOLDER`.
- Unique truck+seal and two empty dests → `MOVED`, JPEG in both folders, original gone from Photos (HEIC/PNG → `_processed`).
- Either dest already exists → `DEST_EXISTS`, no copies, no overwrites, original stays. `DestFolder` lists both folders.
- One matching folder still files as today.
- GUI copy: multi-folder `DEST_EXISTS` uses the extra leftover sentence; one-folder `DEST_EXISTS` keeps today’s sentence. `MOVED` is not a leftover. Inspect footer for `MOVED` is unchanged.
- CSV: one row per photo; `DestFolder` is the joined list on `MOVED` and on multi-folder `DEST_EXISTS`.
