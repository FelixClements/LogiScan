"""Move gates and file placement without OCR."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.config import DEST_FOLDER_SEP, STATUS_DEST_EXISTS, STATUS_MOVED, STATUS_NO_FOLDER
from logiscan.extract import ExtractedFields
from logiscan.index import build_index
from logiscan.processor import commit_copies, destination_for, gate_status, join_dest_folders


def _complete() -> ExtractedFields:
    return ExtractedFields("MRSU8692215", "48291", None, None)


class DestinationTests(unittest.TestCase):
    def test_name_is_trailer_underscore_seal_jpg(self) -> None:
        dest = destination_for(Path("D:/POs/PO-1"), "MRSU8692215", "48291")
        self.assertEqual(dest.name, "MRSU8692215_48291.jpg")


class JoinDestFoldersTests(unittest.TestCase):
    def test_empty_is_none(self) -> None:
        self.assertIsNone(join_dest_folders([]))

    def test_joins_with_semicolon_space(self) -> None:
        a = Path("/po/a")
        b = Path("/po/b")
        self.assertEqual(join_dest_folders([a, b]), f"{a}{DEST_FOLDER_SEP}{b}")


class GateStatusTests(unittest.TestCase):
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

    def test_existing_dest_untouched_when_gate_says_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            po = Path(raw) / "PO-1"
            po.mkdir()
            dest = po / "MRSU8692215_48291.jpg"
            dest.write_bytes(b"keep-me")
            (po / "MRSU8692215.pdf").write_bytes(b"x")
            status, _folders = gate_status(_complete(), build_index(Path(raw)))
            self.assertEqual(status, STATUS_DEST_EXISTS)
            self.assertEqual(dest.read_bytes(), b"keep-me")


if __name__ == "__main__":
    unittest.main()
