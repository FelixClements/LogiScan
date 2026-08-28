"""ISO-6346 check digit and filename/OCR token normalization."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.iso import codes_in_text, is_valid_iso, normalize_iso


class NormalizeIsoTests(unittest.TestCase):
    def test_strips_space_and_hyphen(self) -> None:
        self.assertEqual(normalize_iso("MRSU 8692215"), "MRSU8692215")
        self.assertEqual(normalize_iso("MRSU-8692215"), "MRSU8692215")

    def test_uppercases(self) -> None:
        self.assertEqual(normalize_iso("mrsu8692215"), "MRSU8692215")


class CheckDigitTests(unittest.TestCase):
    def test_accepts_mrsu8692215(self) -> None:
        self.assertTrue(is_valid_iso("MRSU8692215"))

    def test_rejects_one_digit_mutation(self) -> None:
        self.assertFalse(is_valid_iso("MRSU8692214"))

    def test_rejects_wrong_length(self) -> None:
        self.assertFalse(is_valid_iso("MRSU869221"))
        self.assertFalse(is_valid_iso(""))


class CodesInTextTests(unittest.TestCase):
    def test_finds_spaced_and_hyphenated_forms(self) -> None:
        text = "see MRSU 8692215 and also MRSU-8692215"
        self.assertEqual(codes_in_text(text), ("MRSU8692215",))

    def test_ignores_invalid_check_digit(self) -> None:
        self.assertEqual(codes_in_text("ABCD1234567"), ())

    def test_finds_two_distinct_valid_codes(self) -> None:
        text = "MRSU8692215 then CSQU3054383"
        codes = codes_in_text(text)
        self.assertEqual(len(codes), 2)
        self.assertIn("MRSU8692215", codes)
        self.assertIn("CSQU3054383", codes)


if __name__ == "__main__":
    unittest.main()
