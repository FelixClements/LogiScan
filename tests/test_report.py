"""ReportManager writes SUCCESS logs and CSV rows without OCR."""

from __future__ import annotations

from unittest.mock import patch
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan import (
    STATUS_ERROR,
    STATUS_NO_MATCH,
    STATUS_SUCCESS,
    Config,
    OCRProcessor,
    ReportManager,
    ScanResult,
    list_images,
)
from logiscan.hardware import DirectMLUnavailableError


class ReportManagerTests(unittest.TestCase):
    def test_success_log_and_csv(self) -> None:
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
                timestamp="2026-08-27 21:00:00",
                filename="scan.jpg",
                mrsu_match=True,
                tracking_match_count=2,
                status=STATUS_SUCCESS,
            )
            reporter.record(result)
            log_text = config.log_path.read_text(encoding="utf-8")
            self.assertIn("SUCCESS: scan.jpg", log_text)
            self.assertIn("2 instances of 73868 variants", log_text)
            csv_text = config.report_path.read_text(encoding="utf-8")
            self.assertIn("Timestamp,Filename,MRSU_Match,Tracking_Match_Count,Status", csv_text)
            self.assertIn("scan.jpg", csv_text)
            self.assertIn(STATUS_SUCCESS, csv_text)

    def test_error_and_nomatch_skip_success_log(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = Config(
                photos_dir=root / "photos",
                log_path=root / "ocr_matches.log",
                report_path=root / "ocr_report.csv",
            )
            reporter = ReportManager(config)
            reporter.record(
                ScanResult("2026-08-27 21:00:00", "bad.png", False, 0, STATUS_ERROR, "corrupt")
            )
            reporter.record(
                ScanResult("2026-08-27 21:00:01", "miss.jpg", False, 1, STATUS_NO_MATCH)
            )
            self.assertFalse(config.log_path.exists())
            csv_text = config.report_path.read_text(encoding="utf-8")
            self.assertIn(STATUS_ERROR, csv_text)
            self.assertIn(STATUS_NO_MATCH, csv_text)


class CliTests(unittest.TestCase):
    def test_missing_input_dir_exits_1(self) -> None:
        from logiscan import main

        self.assertEqual(main(["--input-dir", str(Path("missing-logiscan-photos-xyz"))]), 1)

    def test_empty_input_dir_exits_0(self) -> None:
        from logiscan import main

        with tempfile.TemporaryDirectory() as raw:
            photos = Path(raw) / "photos"
            photos.mkdir()
            self.assertEqual(main(["--input-dir", str(photos)]), 0)

    def test_check_hardware_uses_probe_exit_code(self) -> None:
        from logiscan import main

        with patch("logiscan.cli.probe_hardware", return_value=1) as probe:
            self.assertEqual(main(["--check-hardware"]), 1)
            probe.assert_called_once()

    def test_dml_init_failure_exits_2(self) -> None:
        from logiscan import main

        with tempfile.TemporaryDirectory() as raw:
            photos = Path(raw) / "photos"
            photos.mkdir()
            (photos / "a.jpg").write_bytes(b"x")
            with patch(
                "logiscan.cli.OCRProcessor",
                side_effect=DirectMLUnavailableError("DmlExecutionProvider is not available"),
            ):
                self.assertEqual(main(["--input-dir", str(photos)]), 2)


class ListImagesTests(unittest.TestCase):
    def test_filters_extensions_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            (folder / "a.JPG").write_bytes(b"x")
            (folder / "b.jpeg").write_bytes(b"x")
            (folder / "c.png").write_bytes(b"x")
            (folder / "d.txt").write_bytes(b"x")
            names = {path.name.lower() for path in list_images(folder, (".jpg", ".jpeg", ".png"))}
            self.assertEqual(names, {"a.jpg", "b.jpeg", "c.png"})


class TwoPassLogicTests(unittest.TestCase):
    def test_skips_pass2_when_markers_complete(self) -> None:
        engine = _ScriptedEngine(["MRSU8692215\n73868\n73888"])
        processor = _processor_with_engine(engine)
        with patch("logiscan.processor.load_image", return_value=object()):
            result = processor.process_image(Path("hit.jpg"))
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(result.tracking_match_count, 2)
        self.assertEqual(engine.calls, 1)

    def test_runs_pass2_when_pass1_incomplete(self) -> None:
        engine = _ScriptedEngine(["noise", "MRSU 8692215\n73888\n73868"])
        processor = _processor_with_engine(engine)
        with (
            patch("logiscan.processor.load_image", return_value=object()),
            patch("logiscan.processor.enhance_pass2", return_value=object()) as enhance,
        ):
            result = processor.process_image(Path("retry.jpg"))
        enhance.assert_called_once()
        self.assertEqual(result.status, STATUS_SUCCESS)
        self.assertEqual(engine.calls, 2)


class _ScriptedEngine:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def recognize(self, image: object) -> str:
        self.calls += 1
        if not self._responses:
            return ""
        return self._responses.pop(0)


def _processor_with_engine(engine: _ScriptedEngine) -> OCRProcessor:
    processor = OCRProcessor.__new__(OCRProcessor)
    processor.config = Config()
    processor._opencl = False
    processor._engine = engine
    return processor


if __name__ == "__main__":
    unittest.main()
