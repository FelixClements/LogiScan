"""Trailer and seal extract from OCR text."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.extract import extract_fields


class TrailerExtractTests(unittest.TestCase):
    def test_one_valid_iso_is_the_trailer(self) -> None:
        result = extract_fields("MRSU 8692215\n48291\n48291")
        self.assertEqual(result.trailer, "MRSU8692215")
        self.assertIsNone(result.trailer_status)

    def test_no_valid_iso(self) -> None:
        result = extract_fields("no container here 48291 48291")
        self.assertIsNone(result.trailer)
        self.assertEqual(result.trailer_status, "NO_TRAILER")

    def test_two_distinct_valid_isos(self) -> None:
        result = extract_fields("MRSU8692215 CSQU3054383 48291 48291")
        self.assertIsNone(result.trailer)
        self.assertEqual(result.trailer_status, "AMBIGUOUS_TRAILER")


class SealExtractTests(unittest.TestCase):
    def test_five_digits_twice_is_the_seal(self) -> None:
        result = extract_fields("MRSU8692215 48291 and 48291 again")
        self.assertEqual(result.seal, "48291")
        self.assertIsNone(result.seal_status)

    def test_five_digits_once_is_not_enough(self) -> None:
        result = extract_fields("MRSU8692215 48291")
        self.assertIsNone(result.seal)
        self.assertEqual(result.seal_status, "NO_SEAL")

    def test_two_confirmed_seals_are_ambiguous(self) -> None:
        result = extract_fields("MRSU8692215 48291 48291 11990 11990")
        self.assertIsNone(result.seal)
        self.assertEqual(result.seal_status, "AMBIGUOUS_SEAL")

    def test_complete_when_one_trailer_and_one_seal(self) -> None:
        result = extract_fields("MRSU8692215\nSEAL 48291\n48291")
        self.assertTrue(result.complete)
        self.assertEqual(result.trailer, "MRSU8692215")
        self.assertEqual(result.seal, "48291")


if __name__ == "__main__":
    unittest.main()
