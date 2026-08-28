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
