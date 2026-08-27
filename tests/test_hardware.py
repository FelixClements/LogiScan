"""DirectML hard-fail and hardware probe — no real ORT session required."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.config import BACKEND_DML
from logiscan.hardware import (
    DML_PROVIDER,
    DirectMLUnavailableError,
    probe_hardware,
    require_directml,
    require_session_on_dml,
)
from logiscan.ocr import RapidOCREngine, layout_from_result


class DirectMLGuardTests(unittest.TestCase):
    def test_require_directml_raises_without_provider(self) -> None:
        with patch("logiscan.hardware.ort_providers", return_value=["CPUExecutionProvider"]):
            with self.assertRaises(DirectMLUnavailableError):
                require_directml()

    def test_require_directml_ok_when_listed(self) -> None:
        with patch(
            "logiscan.hardware.ort_providers",
            return_value=[DML_PROVIDER, "CPUExecutionProvider"],
        ):
            require_directml()

    def test_session_must_use_dml_first(self) -> None:
        with self.assertRaises(DirectMLUnavailableError):
            require_session_on_dml(["CPUExecutionProvider"], label="Detector")
        require_session_on_dml([DML_PROVIDER, "CPUExecutionProvider"], label="Detector")

    def test_engine_init_hard_fails_before_rapidocr(self) -> None:
        with patch(
            "logiscan.ocr.require_directml",
            side_effect=DirectMLUnavailableError("no dml"),
        ):
            with self.assertRaises(DirectMLUnavailableError):
                RapidOCREngine(MagicMock())


class ProbeHardwareTests(unittest.TestCase):
    def test_probe_fails_without_dml(self) -> None:
        with (
            patch("logiscan.hardware.ort_providers", return_value=["CPUExecutionProvider"]),
            patch("sys.stdout", new_callable=io.StringIO) as out,
        ):
            self.assertEqual(probe_hardware(), 1)
        text = out.getvalue()
        self.assertIn("DmlExecutionProvider present: False", text)
        self.assertIn("FAIL", text)

    def test_probe_ok_with_dml(self) -> None:
        with (
            patch(
                "logiscan.hardware.ort_providers",
                return_value=[DML_PROVIDER, "CPUExecutionProvider"],
            ),
            patch("sys.stdout", new_callable=io.StringIO) as out,
        ):
            self.assertEqual(probe_hardware(), 0)
        text = out.getvalue()
        self.assertIn("DmlExecutionProvider present: True", text)
        self.assertIn(BACKEND_DML, text)


class LayoutJoinTests(unittest.TestCase):
    def test_sorts_boxes_top_to_bottom(self) -> None:
        result = MagicMock()
        result.txts = ("right", "left-top", "bottom")
        result.boxes = (
            [[80, 10], [120, 10], [120, 30], [80, 30]],
            [[10, 8], [40, 8], [40, 28], [10, 28]],
            [[10, 90], [50, 90], [50, 110], [10, 110]],
        )
        self.assertEqual(layout_from_result(result), "left-top\nright\nbottom")

    def test_empty_result(self) -> None:
        result = MagicMock()
        result.txts = None
        result.boxes = None
        self.assertEqual(layout_from_result(result), "")


if __name__ == "__main__":
    unittest.main()
