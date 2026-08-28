"""GPU pipeline tests against real photos in tests/fixtures."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.config import STATUS_DEST_EXISTS, STATUS_MOVED, Config
from logiscan.hardware import require_directml
from logiscan.index import build_index
from logiscan.ocr import RapidOCREngine
from logiscan.processor import OCRProcessor, destination_for

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MANIFEST = FIXTURES / "expected.csv"


def load_manifest() -> list[dict[str, str]]:
    if not FIXTURES.is_dir():
        raise FileNotFoundError(f"Missing fixtures directory: {FIXTURES}")
    if not MANIFEST.is_file():
        raise FileNotFoundError(f"Missing fixture manifest: {MANIFEST}")
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise FileNotFoundError(f"No photos listed in {MANIFEST}")
    for row in rows:
        path = FIXTURES / row["filename"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing fixture photo: {path}")
    return rows


class GpuFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        require_directml()
        cls.rows = load_manifest()
        cls.engine = RapidOCREngine(Config().resolved())

    def test_extracts_trailer_and_seal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            photos = root / "photos"
            search = root / "pos"
            photos.mkdir()
            search.mkdir()
            config = Config(
                photos_dir=photos,
                search_root=search,
                log_path=root / "ocr_matches.log",
                report_path=root / "ocr_report.csv",
            ).resolved()
            processor = OCRProcessor(config, build_index(search), engine=self.engine)
            for row in self.rows:
                source = FIXTURES / row["filename"]
                local = photos / source.name
                local.write_bytes(source.read_bytes())
                result = processor.process_image(local)
                self.assertEqual(result.trailer, row["trailer"], msg=source.name)
                self.assertEqual(result.seal, row["seal"], msg=source.name)

    def test_moves_jpeg_into_temp_po_folder(self) -> None:
        row = self.rows[0]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            photos = root / "photos"
            po = root / "pos" / "PO-1"
            photos.mkdir()
            po.mkdir(parents=True)
            (po / f"{row['trailer']}-cmr.pdf").write_bytes(b"x")
            config = Config(
                photos_dir=photos,
                search_root=root / "pos",
                log_path=root / "ocr_matches.log",
                report_path=root / "ocr_report.csv",
            ).resolved()
            source = FIXTURES / row["filename"]
            local = photos / source.name
            local.write_bytes(source.read_bytes())
            processor = OCRProcessor(
                config, build_index(config.search_root), engine=self.engine
            )
            result = processor.process_image(local)
            dest = destination_for(po.resolve(), row["trailer"], row["seal"])
            self.assertEqual(result.status, STATUS_MOVED)
            self.assertTrue(dest.is_file())
            suffix = source.suffix.lower()
            if suffix in {".heic", ".heif", ".png"}:
                self.assertTrue((photos / "_processed" / source.name).is_file())
            else:
                self.assertFalse(local.exists())

    def test_dest_exists_does_not_overwrite(self) -> None:
        row = self.rows[0]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            photos = root / "photos"
            po = root / "pos" / "PO-1"
            photos.mkdir()
            po.mkdir(parents=True)
            (po / f"{row['trailer']}-cmr.pdf").write_bytes(b"x")
            dest = destination_for(po.resolve(), row["trailer"], row["seal"])
            dest.write_bytes(b"keep-me")
            config = Config(
                photos_dir=photos,
                search_root=root / "pos",
                log_path=root / "ocr_matches.log",
                report_path=root / "ocr_report.csv",
            ).resolved()
            source = FIXTURES / row["filename"]
            local = photos / source.name
            local.write_bytes(source.read_bytes())
            processor = OCRProcessor(
                config, build_index(config.search_root), engine=self.engine
            )
            result = processor.process_image(local)
            self.assertEqual(result.status, STATUS_DEST_EXISTS)
            self.assertEqual(dest.read_bytes(), b"keep-me")
            self.assertTrue(local.exists())


if __name__ == "__main__":
    unittest.main()
