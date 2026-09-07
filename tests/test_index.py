"""PO folder index from filenames that contain ISO-6346 codes."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.index import build_index


class FolderIndexTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
