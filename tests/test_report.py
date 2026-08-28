"""ReportManager and CLI without OCR."""

from __future__ import annotations

from unittest.mock import patch
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan import (
    STATUS_ERROR,
    STATUS_MOVED,
    STATUS_NO_TRAILER,
    Config,
    ReportManager,
    ScanResult,
)
from logiscan.hardware import DirectMLUnavailableError


class ReportManagerTests(unittest.TestCase):
    def test_moved_log_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = Config(
                photos_dir=root / "photos",
                log_path=root / "ocr_matches.log",
                report_path=root / "ocr_report.csv",
                model_dir=root / "models" / "rapidocr",
            )
            reporter = ReportManager(config)
            result = ScanResult(
                timestamp="2026-08-28 07:00:00",
                filename="shot.heic",
                trailer="MRSU8692215",
                seal="48291",
                dest_folder=str(root / "PO-1"),
                status=STATUS_MOVED,
            )
            reporter.record(result)
            log_text = config.log_path.read_text(encoding="utf-8")
            self.assertIn("MOVED: shot.heic", log_text)
            self.assertIn("trailer=MRSU8692215", log_text)
            self.assertIn("seal=48291", log_text)
            csv_text = config.report_path.read_text(encoding="utf-8")
            self.assertIn("Timestamp,Filename,Trailer,Seal,DestFolder,Status", csv_text)
            self.assertIn("shot.heic", csv_text)
            self.assertIn(STATUS_MOVED, csv_text)

    def test_failures_skip_success_log(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = Config(
                photos_dir=root / "photos",
                log_path=root / "ocr_matches.log",
                report_path=root / "ocr_report.csv",
            )
            reporter = ReportManager(config)
            reporter.record(
                ScanResult("2026-08-28 07:00:00", "bad.png", status=STATUS_ERROR, error="corrupt")
            )
            reporter.record(
                ScanResult("2026-08-28 07:00:01", "miss.jpg", status=STATUS_NO_TRAILER)
            )
            self.assertFalse(config.log_path.exists())
            csv_text = config.report_path.read_text(encoding="utf-8")
            self.assertIn(STATUS_ERROR, csv_text)
            self.assertIn(STATUS_NO_TRAILER, csv_text)


class CliTests(unittest.TestCase):
    def test_missing_search_root_exits_1(self) -> None:
        from logiscan import main

        with tempfile.TemporaryDirectory() as raw:
            photos = Path(raw) / "photos"
            photos.mkdir()
            self.assertEqual(main(["--input-dir", str(photos)]), 1)

    def test_missing_input_dir_exits_1(self) -> None:
        from logiscan import main

        with tempfile.TemporaryDirectory() as raw:
            search = Path(raw) / "pos"
            search.mkdir()
            self.assertEqual(
                main(
                    [
                        "--input-dir",
                        str(Path(raw) / "missing-photos"),
                        "--search-root",
                        str(search),
                    ]
                ),
                1,
            )

    def test_empty_input_dir_exits_0(self) -> None:
        from logiscan import main

        with tempfile.TemporaryDirectory() as raw:
            photos = Path(raw) / "photos"
            search = Path(raw) / "pos"
            photos.mkdir()
            search.mkdir()
            self.assertEqual(
                main(["--input-dir", str(photos), "--search-root", str(search)]),
                0,
            )

    def test_check_hardware_uses_probe_exit_code(self) -> None:
        from logiscan import main

        with patch("logiscan.cli.probe_hardware", return_value=1) as probe:
            self.assertEqual(main(["--check-hardware"]), 1)
            probe.assert_called_once()

    def test_dml_init_failure_exits_2(self) -> None:
        from logiscan import main

        with tempfile.TemporaryDirectory() as raw:
            photos = Path(raw) / "photos"
            search = Path(raw) / "pos"
            photos.mkdir()
            search.mkdir()
            (photos / "a.jpg").write_bytes(b"x")
            with patch(
                "logiscan.cli.OCRProcessor",
                side_effect=DirectMLUnavailableError("DmlExecutionProvider is not available"),
            ):
                self.assertEqual(
                    main(["--input-dir", str(photos), "--search-root", str(search)]),
                    2,
                )


if __name__ == "__main__":
    unittest.main()
