"""Move gates and file placement without OCR."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.config import STATUS_DEST_EXISTS, STATUS_MOVED, STATUS_NO_FOLDER
from logiscan.extract import ExtractedFields
from logiscan.index import build_index
from logiscan.processor import commit_move, destination_for, gate_status


def _complete() -> ExtractedFields:
    return ExtractedFields("MRSU8692215", "48291", None, None)


class DestinationTests(unittest.TestCase):
    def test_name_is_trailer_underscore_seal_jpg(self) -> None:
        dest = destination_for(Path("D:/POs/PO-1"), "MRSU8692215", "48291")
        self.assertEqual(dest.name, "MRSU8692215_48291.jpg")


class GateStatusTests(unittest.TestCase):
    def test_unique_folder_ready_to_move(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-1"
            po.mkdir()
            (po / "MRSU8692215.pdf").write_bytes(b"x")
            index = build_index(root)
            status, folder = gate_status(_complete(), index)
            self.assertEqual(status, STATUS_MOVED)
            self.assertEqual(folder, po.resolve())

    def test_dest_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            po = root / "PO-1"
            po.mkdir()
            (po / "MRSU8692215.pdf").write_bytes(b"x")
            (po / "MRSU8692215_48291.jpg").write_bytes(b"existing")
            index = build_index(root)
            status, folder = gate_status(_complete(), index)
            self.assertEqual(status, STATUS_DEST_EXISTS)
            self.assertEqual(folder, po.resolve())

    def test_no_folder(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            index = build_index(Path(raw))
            status, folder = gate_status(_complete(), index)
            self.assertEqual(status, STATUS_NO_FOLDER)
            self.assertIsNone(folder)

    def test_trailer_failure_wins(self) -> None:
        fields = ExtractedFields(None, "48291", "NO_TRAILER", None)
        with tempfile.TemporaryDirectory() as raw:
            status, folder = gate_status(fields, build_index(Path(raw)))
        self.assertEqual(status, "NO_TRAILER")
        self.assertIsNone(folder)


class CommitMoveTests(unittest.TestCase):
    def test_jpeg_source_is_moved_not_archived(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            original = root / "in" / "shot.jpg"
            original.parent.mkdir()
            original.write_bytes(b"jpeg-bytes")
            dest = root / "PO-1" / "MRSU8692215_48291.jpg"
            dest.parent.mkdir()
            processed = root / "in" / "_processed"
            commit_move(original=original, working=original, dest=dest, processed_dir=processed)
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
            commit_move(original=original, working=working, dest=dest, processed_dir=processed)
            self.assertEqual(dest.read_bytes(), b"jpeg-bytes")
            self.assertFalse(original.exists())
            self.assertEqual((processed / "shot.heic").read_bytes(), b"heic-bytes")
            self.assertFalse(working.exists())

    def test_existing_dest_untouched_when_gate_says_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            po = Path(raw) / "PO-1"
            po.mkdir()
            dest = po / "MRSU8692215_48291.jpg"
            dest.write_bytes(b"keep-me")
            (po / "MRSU8692215.pdf").write_bytes(b"x")
            status, _folder = gate_status(_complete(), build_index(Path(raw)))
            self.assertEqual(status, STATUS_DEST_EXISTS)
            self.assertEqual(dest.read_bytes(), b"keep-me")


if __name__ == "__main__":
    unittest.main()
