# Multi-folder copy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** File a unique truck+seal JPEG into every matching PO folder instead of leaving `AMBIGUOUS_FOLDER`.

**Architecture:** `FolderIndex.lookup_status` returns every matching folder. `gate_status` copies when none of those dests exist, and returns `DEST_EXISTS` if any dest exists. `commit_copies` writes the JPEG to each dest then clears Photos. `DestFolder` is a `"; "`-joined path list. Multi-folder `DEST_EXISTS` uses an extra leftover/log sentence.

**Tech Stack:** Python 3.12, stdlib `unittest`, existing LogiScan modules. No new packages. No Tk in tests.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-07-multi-folder-copy-design.md`
- CSV columns stay `Timestamp, Filename, Trailer, Seal, DestFolder, Status`
- No new status codes. `AMBIGUOUS_FOLDER` is not produced on new runs; keep the constant and GUI label
- Never overwrite `{TRAILER}_{SEAL}.jpg`
- Join dest paths with `DEST_FOLDER_SEP = "; "` from `logiscan/config.py`
- Tests are `python3 -m unittest tests.test_* -v`, not pytest
- Do not instantiate `Tk()` in tests
- Never write `git config`. If commit fails on missing identity, leave files staged and continue

## File map

| File | Responsibility |
|---|---|
| `logiscan/config.py` | `DEST_FOLDER_SEP` |
| `logiscan/index.py` | Return all matching folders from `lookup_status` |
| `logiscan/gui_copy.py` | Extra `DEST_EXISTS` leftover sentence when dest contains the join separator |
| `logiscan/processor.py` | `join_dest_folders`, `gate_status` list, `commit_copies`, warning log |
| `logiscan/gui.py` | Pass `result.dest_folder` into `inspect_footer` |
| `README.md` | Unique-folder leftover wording |
| `tests/test_index.py` | Both folders returned |
| `tests/test_gui_copy.py` | Extra leftover sentence |
| `tests/test_move.py` | Gates and copies to many dests |

---

### Task 1: Index returns every matching folder

**Files:**
- Modify: `logiscan/index.py`
- Test: `tests/test_index.py`

**Interfaces:**
- Consumes: existing `FolderIndex._map: dict[str, set[Path]]`
- Produces: `FolderIndex.lookup_status(self, trailer: str) -> tuple[list[Path], str | None]`
  - 0 folders → `([], "NO_FOLDER")`
  - 1 or more → `(sorted(folders, key=str), None)`
  - never `"AMBIGUOUS_FOLDER"`

- [ ] **Step 1: Write the failing tests**

In `tests/test_index.py`, change unique/duplicate/unknown lookups to expect a list, and replace `test_two_po_folders_are_ambiguous` with both folders returned:

```python
    def test_unique_folder_for_one_trailer(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-100"
            po.mkdir()
            (po / "MRSU8692215-cmr.pdf").write_bytes(b"x")
            index = build_index(root)
            folders, status = index.lookup_status("MRSU8692215")
            self.assertIsNone(status)
            self.assertEqual(folders, [po.resolve()])

    def test_hyphen_and_space_in_filename_normalize(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-100"
            po.mkdir()
            (po / "MRSU 8692215.xlsx").write_bytes(b"x")
            (po / "MRSU-8692215.pdf").write_bytes(b"x")
            index = build_index(root)
            folders, status = index.lookup_status("MRSU8692215")
            self.assertIsNone(status)
            self.assertEqual(folders, [po.resolve()])

    def test_same_folder_duplicates_count_as_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-100"
            po.mkdir()
            (po / "MRSU8692215-a.pdf").write_bytes(b"x")
            (po / "MRSU8692215-b.pdf").write_bytes(b"x")
            index = build_index(root)
            folders, status = index.lookup_status("MRSU8692215")
            self.assertIsNone(status)
            self.assertEqual(folders, [po.resolve()])

    def test_two_po_folders_return_both(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            one = root / "PO-1"
            two = root / "PO-2"
            one.mkdir()
            two.mkdir()
            (one / "MRSU8692215.pdf").write_bytes(b"x")
            (two / "MRSU8692215.pdf").write_bytes(b"x")
            index = build_index(root)
            folders, status = index.lookup_status("MRSU8692215")
            self.assertIsNone(status)
            self.assertEqual(folders, sorted([one.resolve(), two.resolve()], key=str))

    def test_unknown_trailer_is_no_folder(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "empty").mkdir()
            index = build_index(root)
            folders, status = index.lookup_status("MRSU8692215")
            self.assertEqual(folders, [])
            self.assertEqual(status, "NO_FOLDER")

    def test_invalid_check_digit_filename_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-100"
            po.mkdir()
            (po / "MRSU8692214.pdf").write_bytes(b"x")
            index = build_index(root)
            folders, status = index.lookup_status("MRSU8692215")
            self.assertEqual(folders, [])
            self.assertEqual(status, "NO_FOLDER")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_index -v`

Expected: FAIL on `test_two_po_folders_return_both` (`AMBIGUOUS_FOLDER` / `None` folder) and unique tests that still unpack a single `Path`.

- [ ] **Step 3: Implement lookup_status**

Replace `lookup_status` in `logiscan/index.py`:

```python
    def lookup_status(self, trailer: str) -> tuple[list[Path], str | None]:
        folders = sorted(self._map.get(trailer, set()), key=str)
        if not folders:
            return [], "NO_FOLDER"
        return folders, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_index -v`

Expected: PASS. `tests.test_move` will fail until Task 3; do not fix that here beyond what Task 1 needs.

- [ ] **Step 5: Commit**

```bash
git add tests/test_index.py logiscan/index.py
git commit -m "Return every matching PO folder from the filename index."
```

---

### Task 2: Extra Already filed leftover sentence

**Files:**
- Modify: `logiscan/config.py`
- Modify: `logiscan/gui_copy.py`
- Modify: `logiscan/gui.py` (`_inspect_iid`)
- Test: `tests/test_gui_copy.py`

**Interfaces:**
- Consumes: `STATUS_DEST_EXISTS`
- Produces:
  - `DEST_FOLDER_SEP = "; "` in `logiscan/config.py`
  - `leftover_reason(status: str, error: str | None = None, dest_folder: str | None = None) -> str`
  - `inspect_footer(filename: str, status: str, error: str | None = None, dest_folder: str | None = None) -> str`
  - Extra DEST_EXISTS sentence when `dest_folder` contains `DEST_FOLDER_SEP`

- [ ] **Step 1: Write the failing tests**

Add to `LeftoverReasonTests` and `InspectFooterTests` in `tests/test_gui_copy.py`:

```python
    def test_dest_exists_several_folders_warns(self) -> None:
        self.assertEqual(
            leftover_reason(
                STATUS_DEST_EXISTS,
                dest_folder="D:\\POs\\PO-1; D:\\POs\\PO-2",
            ),
            "This truck code matches more than one PO folder, and a photo for this truck and seal is already in at least one of them.",
        )

    def test_dest_exists_one_folder_keeps_old_sentence(self) -> None:
        self.assertEqual(
            leftover_reason(STATUS_DEST_EXISTS, dest_folder="D:\\POs\\PO-1"),
            "A photo for this truck and seal is already in the PO folder.",
        )

    def test_dest_exists_several_folders_footer(self) -> None:
        text = inspect_footer(
            "shot.jpg",
            STATUS_DEST_EXISTS,
            dest_folder="D:\\POs\\PO-1; D:\\POs\\PO-2",
        )
        self.assertEqual(
            text,
            "shot.jpg is still in the photos folder. This truck code matches more than one PO folder, and a photo for this truck and seal is already in at least one of them.",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_gui_copy -v`

Expected: FAIL — `leftover_reason` / `inspect_footer` reject `dest_folder=`.

- [ ] **Step 3: Implement**

Add after `CSV_FIELDS` in `logiscan/config.py`:

```python
DEST_FOLDER_SEP = "; "
```

Update `leftover_reason` and `inspect_footer` in `logiscan/gui_copy.py` to import `DEST_FOLDER_SEP` and:

```python
def leftover_reason(
    status: str,
    error: str | None = None,
    dest_folder: str | None = None,
) -> str:
    if status == STATUS_ERROR:
        if error:
            return error
        return "Processing failed."
    if not status:
        return "This photo was not processed."
    if (
        status == STATUS_DEST_EXISTS
        and dest_folder
        and DEST_FOLDER_SEP in dest_folder
    ):
        return (
            "This truck code matches more than one PO folder, and a photo "
            "for this truck and seal is already in at least one of them."
        )
    return _LEFTOVER_REASONS.get(status, status)


def inspect_footer(
    filename: str,
    status: str,
    error: str | None = None,
    dest_folder: str | None = None,
) -> str:
    if not is_leftover(status):
        return f"{filename} was moved."
    return (
        f"{filename} is still in the photos folder. "
        f"{leftover_reason(status, error, dest_folder=dest_folder)}"
    )
```

In `logiscan/gui.py` `_inspect_iid`, pass dest_folder:

```python
            dest_folder = result.dest_folder if result is not None else None
            self.footer_var.set(
                inspect_footer(iid, status, error, dest_folder=dest_folder)
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_gui_copy -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add logiscan/config.py logiscan/gui_copy.py logiscan/gui.py tests/test_gui_copy.py
git commit -m "Warn when Already filed matches several PO folders."
```

---

### Task 3: gate_status returns every folder

**Files:**
- Modify: `logiscan/processor.py`
- Test: `tests/test_move.py`

**Interfaces:**
- Consumes: `FolderIndex.lookup_status` → `(list[Path], str | None)`
- Produces:
  - `join_dest_folders(folders: list[Path]) -> str | None`
  - `gate_status(fields: ExtractedFields, index: FolderIndex) -> tuple[str, list[Path]]`
  - Trailer/seal leftovers and `NO_FOLDER` → empty list
  - Any existing `{TRAILER}_{SEAL}.jpg` among matching folders → `DEST_EXISTS` plus the folder list
  - Else `MOVED` plus the folder list

- [ ] **Step 1: Write the failing tests**

Update `GateStatusTests` in `tests/test_move.py` to expect lists, and add two-folder cases. Import `join_dest_folders` and `DEST_FOLDER_SEP` once they exist; until then tests call `gate_status` only:

```python
    def test_unique_folder_ready_to_move(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-1"
            po.mkdir()
            (po / "MRSU8692215.pdf").write_bytes(b"x")
            index = build_index(root)
            status, folders = gate_status(_complete(), index)
            self.assertEqual(status, STATUS_MOVED)
            self.assertEqual(folders, [po.resolve()])

    def test_dest_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-1"
            po.mkdir()
            (po / "MRSU8692215.pdf").write_bytes(b"x")
            (po / "MRSU8692215_48291.jpg").write_bytes(b"existing")
            index = build_index(root)
            status, folders = gate_status(_complete(), index)
            self.assertEqual(status, STATUS_DEST_EXISTS)
            self.assertEqual(folders, [po.resolve()])

    def test_no_folder(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            index = build_index(Path(raw))
            status, folders = gate_status(_complete(), index)
            self.assertEqual(status, STATUS_NO_FOLDER)
            self.assertEqual(folders, [])

    def test_trailer_failure_wins(self) -> None:
        fields = ExtractedFields(None, "48291", "NO_TRAILER", None)
        with tempfile.TemporaryDirectory() as raw:
            status, folders = gate_status(fields, build_index(Path(raw)))
        self.assertEqual(status, "NO_TRAILER")
        self.assertEqual(folders, [])

    def test_two_folders_ready_to_copy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            one = root / "PO-1"
            two = root / "PO-2"
            one.mkdir()
            two.mkdir()
            (one / "MRSU8692215.pdf").write_bytes(b"x")
            (two / "MRSU8692215.pdf").write_bytes(b"x")
            status, folders = gate_status(_complete(), build_index(root))
            self.assertEqual(status, STATUS_MOVED)
            self.assertEqual(folders, sorted([one.resolve(), two.resolve()], key=str))

    def test_two_folders_dest_exists_in_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            one = root / "PO-1"
            two = root / "PO-2"
            one.mkdir()
            two.mkdir()
            (one / "MRSU8692215.pdf").write_bytes(b"x")
            (two / "MRSU8692215.pdf").write_bytes(b"x")
            (one / "MRSU8692215_48291.jpg").write_bytes(b"keep-me")
            status, folders = gate_status(_complete(), build_index(root))
            self.assertEqual(status, STATUS_DEST_EXISTS)
            self.assertEqual(folders, sorted([one.resolve(), two.resolve()], key=str))
            self.assertEqual((one / "MRSU8692215_48291.jpg").read_bytes(), b"keep-me")
            self.assertFalse((two / "MRSU8692215_48291.jpg").exists())
```

Also add:

```python
class JoinDestFoldersTests(unittest.TestCase):
    def test_empty_is_none(self) -> None:
        self.assertIsNone(join_dest_folders([]))

    def test_joins_with_semicolon_space(self) -> None:
        from logiscan.config import DEST_FOLDER_SEP

        a = Path("/po/a")
        b = Path("/po/b")
        self.assertEqual(join_dest_folders([a, b]), f"{a}{DEST_FOLDER_SEP}{b}")
```

Import `join_dest_folders` from `logiscan.processor`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_move -v`

Expected: FAIL on list unpack / missing `join_dest_folders` / two-folder `AMBIGUOUS` leftover if gate still uses old lookup.

- [ ] **Step 3: Implement**

In `logiscan/processor.py`:

```python
from logiscan.config import (
    DEST_FOLDER_SEP,
    STATUS_CONVERT_ERROR,
    STATUS_DEST_EXISTS,
    STATUS_ERROR,
    STATUS_MOVED,
    Config,
    ScanResult,
)


def join_dest_folders(folders: list[Path]) -> str | None:
    if not folders:
        return None
    return DEST_FOLDER_SEP.join(str(path) for path in folders)


def gate_status(fields: ExtractedFields, index: FolderIndex) -> tuple[str, list[Path]]:
    if fields.trailer_status:
        return fields.trailer_status, []
    if fields.seal_status:
        return fields.seal_status, []
    assert fields.trailer is not None and fields.seal is not None
    folders, folder_status = index.lookup_status(fields.trailer)
    if folder_status:
        return folder_status, []
    if any(
        destination_for(folder, fields.trailer, fields.seal).exists()
        for folder in folders
    ):
        return STATUS_DEST_EXISTS, folders
    return STATUS_MOVED, folders
```

Temporarily keep `_scan` working: `status, folders = gate_status(...)` then `folder = folders[0] if folders else None` until Task 4/5. Prefer finishing Task 4 in the same change set if `_scan` would be broken.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_move tests.test_index -v`

Expected: Gate tests PASS. Commit-move tests still use `commit_move` until Task 4.

- [ ] **Step 5: Commit**

```bash
git add logiscan/processor.py tests/test_move.py
git commit -m "File to every matching PO folder unless a dest already exists."
```

If `_scan` is still single-folder, include Task 4–5 in the same commit rather than leaving process_image broken.

---

### Task 4: Copy JPEG into every dest then clear Photos

**Files:**
- Modify: `logiscan/processor.py`
- Test: `tests/test_move.py`

**Interfaces:**
- Consumes: working JPEG path, original path, dest paths, processed dir
- Produces: `commit_copies(*, original: Path, working: Path, dests: list[Path], processed_dir: Path) -> None`
  - `shutil.copy2` working JPEG to each dest first
  - JPEG original: unlink after copies
  - HEIC/HEIF/PNG: delete temp working JPEG, move original to `processed_dir`
  - Remove `commit_move` (callers switch to `commit_copies`)

- [ ] **Step 1: Write the failing tests**

Replace `commit_move` tests and add a two-dest JPEG test:

```python
from logiscan.processor import commit_copies, destination_for, gate_status, join_dest_folders


class CommitCopiesTests(unittest.TestCase):
    def test_jpeg_source_copied_then_removed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            original = root / "in" / "shot.jpg"
            original.parent.mkdir()
            original.write_bytes(b"jpeg-bytes")
            dest = root / "PO-1" / "MRSU8692215_48291.jpg"
            dest.parent.mkdir()
            processed = root / "in" / "_processed"
            commit_copies(
                original=original,
                working=original,
                dests=[dest],
                processed_dir=processed,
            )
            self.assertEqual(dest.read_bytes(), b"jpeg-bytes")
            self.assertFalse(original.exists())
            self.assertFalse(processed.exists())

    def test_heic_original_goes_to_processed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            original = root / "in" / "shot.heic"
            original.parent.mkdir()
            original.write_bytes(b"heic-bytes")
            working = root / "tmp.jpg"
            working.write_bytes(b"jpeg-bytes")
            dest = root / "PO-1" / "MRSU8692215_48291.jpg"
            dest.parent.mkdir()
            processed = root / "in" / "_processed"
            commit_copies(
                original=original,
                working=working,
                dests=[dest],
                processed_dir=processed,
            )
            self.assertEqual(dest.read_bytes(), b"jpeg-bytes")
            self.assertFalse(original.exists())
            self.assertEqual((processed / "shot.heic").read_bytes(), b"heic-bytes")
            self.assertFalse(working.exists())

    def test_jpeg_copied_to_every_dest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            original = root / "in" / "shot.jpg"
            original.parent.mkdir()
            original.write_bytes(b"jpeg-bytes")
            one = root / "PO-1" / "MRSU8692215_48291.jpg"
            two = root / "PO-2" / "MRSU8692215_48291.jpg"
            one.parent.mkdir()
            two.parent.mkdir()
            commit_copies(
                original=original,
                working=original,
                dests=[one, two],
                processed_dir=root / "in" / "_processed",
            )
            self.assertEqual(one.read_bytes(), b"jpeg-bytes")
            self.assertEqual(two.read_bytes(), b"jpeg-bytes")
            self.assertFalse(original.exists())
```

Keep `test_existing_dest_untouched_when_gate_says_exists` using `gate_status` only.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.CommitCopiesTests -v`  
Use: `python3 -m unittest tests.test_move.CommitCopiesTests -v`

Expected: FAIL — `commit_copies` not defined.

- [ ] **Step 3: Implement commit_copies and wire _scan**

```python
def commit_copies(
    *,
    original: Path,
    working: Path,
    dests: list[Path],
    processed_dir: Path,
) -> None:
    for dest in dests:
        shutil.copy2(str(working), str(dest))
    converting = original.suffix.lower() in CONVERT_SUFFIXES
    if converting:
        if working != original:
            working.unlink(missing_ok=True)
        try:
            processed_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(original), str(processed_dir / original.name))
        except OSError as exc:
            LOGGER.error(
                "Copied JPEG to %s but failed to archive %s: %s",
                dests,
                original,
                exc,
            )
        return
    if original.exists():
        original.unlink()
```

Replace `_scan` filing tail:

```python
        status, folders = gate_status(fields, self._index)
        dest_folder = join_dest_folders(folders)
        if status != STATUS_MOVED:
            if (
                status == STATUS_DEST_EXISTS
                and dest_folder
                and DEST_FOLDER_SEP in dest_folder
            ):
                LOGGER.warning(
                    "%s %s | trailer=%s seal=%s dest=%s",
                    leftover_reason(status, dest_folder=dest_folder),
                    original.name,
                    fields.trailer,
                    fields.seal,
                    dest_folder,
                )
            return ScanResult(
                timestamp=timestamp,
                filename=original.name,
                trailer=fields.trailer,
                seal=fields.seal,
                dest_folder=dest_folder,
                status=status,
            )
        assert fields.trailer is not None and fields.seal is not None
        dests = [
            destination_for(folder, fields.trailer, fields.seal) for folder in folders
        ]
        commit_copies(
            original=original,
            working=working,
            dests=dests,
            processed_dir=self.config.processed_dir,
        )
        return ScanResult(
            timestamp=timestamp,
            filename=original.name,
            trailer=fields.trailer,
            seal=fields.seal,
            dest_folder=dest_folder,
            status=STATUS_MOVED,
        )
```

Import `leftover_reason` from `logiscan.gui_copy`. Delete `commit_move`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_move tests.test_index tests.test_gui_copy tests.test_batch tests.test_report -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add logiscan/processor.py tests/test_move.py
git commit -m "Copy filed JPEGs into every matching PO folder."
```

---

### Task 5: README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: filing behavior from the spec
- Produces: README no longer says “no unique PO folder” blocks the file

- [ ] **Step 1: Update the success-file paragraph**

Replace:

```text
HEIC/HEIF/PNG originals are moved to `photos\_processed` after a successful JPEG move. Existing destination files are not overwritten. Ambiguous trailer, missing seal, or no unique PO folder leaves the original in place.
```

with:

```text
HEIC/HEIF/PNG originals are moved to `photos\_processed` after a successful JPEG copy. Existing destination files are not overwritten. If the truck code matches several PO folders, the JPEG is copied into each of them. Ambiguous trailer, missing seal, no PO folder, or an already-filed destination leaves the original in place.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Document copying trailer photos into every matching PO folder."
```

---

### Task 6: Full non-GPU suite

- [ ] **Step 1: Run**

```bash
python3 -m unittest tests.test_index tests.test_move tests.test_gui_copy tests.test_batch tests.test_report tests.test_iso tests.test_extract tests.test_gui_prefs tests.test_tcltk_copy -v
```

Expected: all PASS. Skip `tests.test_gpu` (needs DirectML). `tests.test_images` / `tests.test_preview` / `tests.test_hardware` only if their deps are present.

- [ ] **Step 2: If anything fails, fix it before finishing**
