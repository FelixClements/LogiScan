# Trailer photo filing

LogiScan is a USB-portable CLI. A run converts HEIC photos to JPEG, reads an ISO-6346 trailer code and a 5-digit seal from each image with RapidOCR on DirectML, finds the matching PO folder under a search root, and moves the JPEG there only when every gate passes.

This replaces the old hardcoded MRSU8692215 plus tracking-number (73868/73888) checker.

## Non-goals

- GUI, watch mode, or a two-step dry-run / `--apply` flow
- Reading PDF, Excel, or other file contents under the search root
- CPU OCR fallback
- Overwriting a file that already exists at the destination
- Recursing the input photo directory
- Deleting HEIC/HEIF/PNG originals on success (they move to `input/_processed` instead)

## CLI

```text
python -m logiscan --input-dir photos --search-root "D:\POs"
```

- `--input-dir` defaults to `photos` (USB kit layout). Must exist and be a directory.
- `--search-root` is required for a processing run. Must exist and be a directory. UNC paths are allowed.
- `--check-hardware` still prints DirectML / OpenCL status and exits. It does not require `--search-root`.
- `--log-file` and `--report-file` keep their current defaults.

Missing input dir, missing search root, or a path that is not a directory: exit 1, no convert, no OCR, no moves.

Empty input dir (no matching files): exit 0.

DirectML unavailable at engine init: exit 2, same as today.

## Pipeline

1. Resolve paths. Validate `--input-dir` and `--search-root`.
2. Walk `--search-root` once. Build an in-memory map from normalized ISO code to the set of parent folders of matching filenames.
3. List photos in `--input-dir` (top level only). Skip the `_processed` directory.
4. Initialize RapidOCR on DirectML. Refuse CPU OCR.
5. For each photo, convert if needed, OCR, extract, look up, then move or leave in place.
6. Append every outcome to the CSV report. Append a line to the success log only for `MOVED`.

```text
input photos + search root
        |
        v
  filename index (once)
        |
        v
  each photo --> jpg/jpeg? --no--> temp JPG from HEIC/HEIF/PNG
        |                              |
        +--yes-------------------------+
                    |
                    v
              RapidOCR (DML)
                    |
                    v
         extract trailer + seal
                    |
                    v
         lookup unique PO folder
                    |
          all gates pass? --no--> original stays, temp JPG deleted
                    |
                   yes
                    v
         dest = PO / TRAILER_SEAL.jpg
                    |
                    v
         move JPG; HEIC/HEIF/PNG original -> input/_processed
```

Files added under the search root after the index is built are ignored until the next process.

## Photo listing

Include files in `--input-dir` whose suffix (case-insensitive) is `.heic`, `.heif`, `.jpg`, `.jpeg`, or `.png`. Do not recurse. Do not list files inside `_processed`.

## HEIC conversion

Use `pillow-heif` (add to `requirements.txt` and the USB wheel set in `scripts/prepare.ps1`).

- `.heic` / `.heif`: decode to a temp JPEG (quality 95) in a temp directory. The original stays in the input dir until a successful move.
- `.jpg` / `.jpeg`: OCR that file in place. No temp copy.
- `.png`: decode and write a temp JPEG (quality 95), same as HEIC, so the destination is always `.jpg`. On success the original PNG is moved to `_processed` like a HEIC.

Convert failure: status `CONVERT_ERROR`. Original untouched. No temp file left behind.

## OCR

Keep RapidOCR + onnxruntime-directml. Keep Pass 2 (CLAHE + bilateral, OpenCL if available) as an independent retry, not a text concat.

1. Run OCR on the working JPEG. Extract trailer and seal from that text only.
2. If that pass does not produce both a unique trailer and a unique confirmed seal, run Pass 2 enhancement and OCR again. Extract from Pass 2 text only.
3. The first pass that is complete wins. If Pass 1 is incomplete, Pass 2 always runs. If Pass 2 is also incomplete, the reported trailer/seal/status come from Pass 2.

Do not concatenate Pass 1 and Pass 2 text. The same 5-digit number seen once in each pass would look like two hits.

## Trailer extract

Uppercase the OCR text. Find all matches of:

```text
(?<![A-Z0-9])([A-Z]{4})[\s\-]*(\d{7})(?!\d)
```

Each match is `letters + digits` with spaces and hyphens stripped, e.g. `MRSU 8692215` and `MRSU-8692215` both become `MRSU8692215`.

Keep only codes that pass the ISO-6346 check digit:

1. Map the first 10 characters to numbers. Digits keep their value. Letters: A=10, B=12, C=13, D=14, E=15, F=16, G=17, H=18, I=19, J=20, K=21, L=23, M=24, N=25, O=26, P=27, Q=28, R=29, S=30, T=31, U=32, V=34, W=35, X=36, Y=37, Z=38 (multiples of 11 are skipped).
2. Multiply character `i` (0-based, left to right) by `2^i`.
3. Sum those products. Check digit is `sum % 11`. Remainder 10 means check digit 0.
4. The 11th character must equal that check digit.

Do not restrict the fourth letter to U/J/Z. `MRSU8692215` is valid (remainder 5).

Distinct valid codes (after normalization) decide the outcome:

- 0 → `NO_TRAILER`
- 2 or more → `AMBIGUOUS_TRAILER`
- exactly 1 → that is the trailer

## Seal extract

In the same uppercase OCR text, find standalone 5-digit numbers:

```text
(?<!\d)(\d{5})(?!\d)
```

Count occurrences by digit string. Confirmed seals are values with at least two hits.

- 0 confirmed values → `NO_SEAL`
- 2 or more distinct confirmed values → `AMBIGUOUS_SEAL`
- exactly 1 confirmed value → that is the seal

The trailer's 7-digit serial is not a 5-digit token, so it is not a seal candidate. No extra exclusion rule.

The word SEAL is not used.

## PO folder index

Walk `--search-root` recursively (`Path.rglob("*")`), files only, `follow_symlinks=False`. On an unreadable directory, log a warning and continue.

For each file, run the same trailer regex and check-digit function used for OCR, on the uppercased filename (name plus suffix, not the full path). Each valid ISO-6346 code maps to the file's parent folder, stored as `Path.resolve()`. A filename that looks like an ISO code but fails the check digit does not enter the index.

The value for each code is a set of folders:

- Several files in the same PO folder still count as one folder.
- The same code in two different PO folders is ambiguous.

Lookup uses the extracted trailer string (`MRSU8692215`):

- 0 folders → `NO_FOLDER`
- 2 or more → `AMBIGUOUS_FOLDER`
- exactly 1 → destination folder

## Move gates

Move only when all of these hold:

1. Unique trailer
2. Unique confirmed seal
3. Unique PO folder
4. Destination path does not already exist

Destination path is always:

```text
{po_folder}/{TRAILER}_{SEAL}.jpg
```

Example: `MRSU8692215_48291.jpg`.

If that path exists: `DEST_EXISTS`. Do not overwrite. Do not append `_2`. Original stays in input. Temp JPEG deleted.

### Success

- Working file is the temp JPEG (HEIC/HEIF/PNG) or the original JPEG. `shutil.move` it to the destination path (works across drives).
- HEIC/HEIF/PNG original: after the JPEG is at the destination, move the original into `{input-dir}/_processed`, creating that directory if needed. If that second move fails, status is still `MOVED` and the log records the `_processed` error. The JPEG is already in the right PO folder.
- JPEG/JPG original: only the destination move. There is no `_processed` copy.

### Failure

Original stays in `--input-dir`. Delete any temp JPEG. Do not create `_processed` for that file.

## Statuses

| Status | When |
|---|---|
| `MOVED` | All gates passed and the JPEG is in the PO folder |
| `CONVERT_ERROR` | HEIC/HEIF/PNG could not be decoded or written as JPEG |
| `ERROR` | Unexpected exception during OCR or I/O |
| `NO_TRAILER` | No valid ISO-6346 code in OCR text |
| `AMBIGUOUS_TRAILER` | Two or more distinct valid ISO codes |
| `NO_SEAL` | No 5-digit value with at least two hits |
| `AMBIGUOUS_SEAL` | Two or more distinct 5-digit values each with at least two hits |
| `NO_FOLDER` | Trailer not present in any indexed filename |
| `AMBIGUOUS_FOLDER` | Trailer present under two or more PO folders |
| `DEST_EXISTS` | `{TRAILER}_{SEAL}.jpg` already exists in the unique PO folder |

Trailer and seal fields on the result are filled when known, even on a later failure (e.g. `NO_FOLDER` still records the trailer and seal). Dest folder is filled when the unique folder is known (`DEST_EXISTS` and `MOVED`).

## Report

CSV columns:

```text
Timestamp, Filename, Trailer, Seal, DestFolder, Status
```

Empty cells for unknown trailer, seal, or dest.

Success log (`ocr_matches.log`), append-only, only for `MOVED`:

```text
[YYYY-MM-DD HH:MM:SS] MOVED: original-name.heic | trailer=MRSU8692215 seal=48291 dest=D:\POs\PO-123
```

The old "Found MRSU Marker and N instances of 73868 variants" line is removed.

## Code shape

Keep the `logiscan` package and USB scripts. Delete `logiscan/markers.py` and the MRSU/tracking fields on `Config` / `ScanResult`.

| Piece | Role |
|---|---|
| `logiscan/iso.py` | Normalize ISO strings, check digit, filename/OCR regex |
| `logiscan/extract.py` | Trailer and seal extract from OCR text, including ambiguity statuses |
| `logiscan/index.py` | One-pass filename index, lookup returning 0/1/many folders |
| `logiscan/images.py` | Listing, load, Pass 2 enhance, HEIC/PNG → temp JPEG |
| `logiscan/processor.py` | Convert → OCR → extract → lookup → move for one photo |
| `logiscan/cli.py` | `--search-root`, index then loop |
| `logiscan/config.py` | Paths, suffixes including HEIC, CLAHE settings. No MRSU/tracking patterns. |
| `logiscan/report.py` | New CSV columns and MOVED log line |
| `logiscan/ocr.py` / `hardware.py` | Unchanged DirectML hard-fail |

`ScanResult` fields: `timestamp`, `filename` (original input name), `trailer`, `seal`, `dest_folder`, `status`, `error`.

## Testing

GPU path for anything that OCRs a photo. Same `RapidOCREngine` and DirectML requirement as a normal run. No CPU OCR fallback. Scripted fake engines are not used for extract/move pipeline tests.

### Fixtures

`tests/fixtures/` holds real photos. `tests/fixtures/expected.csv` columns:

```text
filename,trailer,seal
```

If DirectML is missing, GPU tests fail with the existing `DirectMLUnavailableError` message (not skip). If the fixtures directory or `expected.csv` is missing, or a listed file is missing, GPU tests fail with a clear error naming the path.

### What to assert

- For each manifest row, run the real processor as far as extract (temp PO tree, not the live share) and assert trailer and seal match the row.
- Move tests: create a temp search root with one dummy file whose name contains the expected trailer. Assert the JPEG lands at `{po}/{TRAILER}_{SEAL}.jpg` and HEIC/PNG originals land in `_processed`. Assert `DEST_EXISTS` does not overwrite.
- Index tests may use temp directories and dummy filenames only (no OCR): unique folder, same-folder duplicates, two-folder ambiguity, hyphen/space variants in filenames.
- CLI: missing `--search-root` exits 1. `--check-hardware` still works without it. Missing input dir exits 1.
- Hardware guard tests in `tests/test_hardware.py` stay as they are (no real ORT session).

`tests/test_markers.py` is removed with `markers.py`.

## USB kit

`scripts/prepare.ps1` must vendor `pillow-heif` wheels next to the existing RapidOCR / DirectML / OpenCV set so offline `install.bat` still works.
