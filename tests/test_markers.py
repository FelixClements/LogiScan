"""Unit tests for MRSU and tracking regex — no OCR, GPU, or model download."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan import Config


class MarkerRegexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config()

    def test_mrsu_plain(self) -> None:
        self.assertTrue(self.config.mrsu_found("container MRSU8692215 sealed"))

    def test_mrsu_space(self) -> None:
        self.assertTrue(self.config.mrsu_found("MRSU 8692215"))

    def test_mrsu_hyphen(self) -> None:
        self.assertTrue(self.config.mrsu_found("MRSU-8692215"))

    def test_mrsu_case_insensitive(self) -> None:
        self.assertTrue(self.config.mrsu_found("mrsu8692215"))
        self.assertTrue(self.config.mrsu_found("MrsU 8692215"))

    def test_mrsu_absent(self) -> None:
        self.assertFalse(self.config.mrsu_found("MRSU8692214"))
        self.assertFalse(self.config.mrsu_found("no container code here"))

    def test_tracking_canonical(self) -> None:
        self.assertEqual(self.config.tracking_count("ref 73868 done"), 1)

    def test_tracking_sixth_digit_typo(self) -> None:
        self.assertEqual(self.config.tracking_count("ref 73888 done"), 1)

    def test_tracking_rejects_other_fourth_digit(self) -> None:
        self.assertEqual(self.config.tracking_count("73878"), 0)
        self.assertEqual(self.config.tracking_count("73858"), 0)

    def test_tracking_digit_boundaries(self) -> None:
        self.assertEqual(self.config.tracking_count("1738689"), 0)
        self.assertEqual(self.config.tracking_count("id73868x"), 1)

    def test_tracking_count_two_instances(self) -> None:
        text = "A4 73868 metal 73888"
        self.assertEqual(self.config.tracking_count(text), 2)

    def test_markers_complete_requires_mrsu_and_two_tracking(self) -> None:
        self.assertFalse(self.config.markers_complete("MRSU8692215 73868"))
        self.assertTrue(self.config.markers_complete("MRSU8692215 73868 73888"))
        self.assertFalse(self.config.markers_complete("73868 73888"))


if __name__ == "__main__":
    unittest.main()
