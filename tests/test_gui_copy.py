"""English status copy for leftover-photo inspect. No Tk."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.config import (
    STATUS_AMBIGUOUS_FOLDER,
    STATUS_AMBIGUOUS_SEAL,
    STATUS_AMBIGUOUS_TRAILER,
    STATUS_CONVERT_ERROR,
    STATUS_DEST_EXISTS,
    STATUS_ERROR,
    STATUS_MOVED,
    STATUS_NO_FOLDER,
    STATUS_NO_SEAL,
    STATUS_NO_TRAILER,
)
from logiscan.gui_copy import (
    inspect_footer,
    is_leftover,
    leftover_reason,
    run_summary,
    status_label,
)


class StatusLabelTests(unittest.TestCase):
    def test_every_machine_status_has_english(self) -> None:
        self.assertEqual(status_label(STATUS_NO_TRAILER), "No truck code")
        self.assertEqual(status_label(STATUS_AMBIGUOUS_TRAILER), "Several truck codes")
        self.assertEqual(status_label(STATUS_NO_SEAL), "No seal")
        self.assertEqual(status_label(STATUS_AMBIGUOUS_SEAL), "Several seals")
        self.assertEqual(status_label(STATUS_NO_FOLDER), "No PO folder")
        self.assertEqual(status_label(STATUS_AMBIGUOUS_FOLDER), "Several PO folders")
        self.assertEqual(status_label(STATUS_DEST_EXISTS), "Already filed")
        self.assertEqual(status_label(STATUS_CONVERT_ERROR), "Could not open")
        self.assertEqual(status_label(STATUS_ERROR), "Error")
        self.assertEqual(status_label(STATUS_MOVED), "Moved")

    def test_blank_status_is_not_processed(self) -> None:
        self.assertEqual(status_label(""), "Not processed")


class LeftoverReasonTests(unittest.TestCase):
    def test_reasons_match_status(self) -> None:
        self.assertEqual(leftover_reason(STATUS_NO_TRAILER), "Could not read a truck code.")
        self.assertEqual(
            leftover_reason(STATUS_AMBIGUOUS_TRAILER),
            "Found more than one truck code.",
        )
        self.assertEqual(leftover_reason(STATUS_NO_SEAL), "Could not read a seal number.")
        self.assertEqual(
            leftover_reason(STATUS_AMBIGUOUS_SEAL),
            "Found more than one seal number.",
        )
        self.assertEqual(
            leftover_reason(STATUS_NO_FOLDER),
            "No PO folder for this truck code.",
        )
        self.assertEqual(
            leftover_reason(STATUS_AMBIGUOUS_FOLDER),
            "This truck code matches more than one PO folder.",
        )
        self.assertEqual(
            leftover_reason(STATUS_DEST_EXISTS),
            "A photo for this truck and seal is already in the PO folder.",
        )
        self.assertEqual(
            leftover_reason(STATUS_CONVERT_ERROR),
            "Could not open this photo.",
        )
        self.assertEqual(leftover_reason(""), "This photo was not processed.")

    def test_error_uses_message_when_present(self) -> None:
        self.assertEqual(leftover_reason(STATUS_ERROR, "corrupt file"), "corrupt file")
        self.assertEqual(leftover_reason(STATUS_ERROR, None), "Processing failed.")
        self.assertEqual(leftover_reason(STATUS_ERROR, ""), "Processing failed.")


class LeftoverFlagTests(unittest.TestCase):
    def test_moved_is_not_leftover(self) -> None:
        self.assertFalse(is_leftover(STATUS_MOVED))

    def test_every_other_status_is_leftover(self) -> None:
        for status in (
            STATUS_NO_TRAILER,
            STATUS_AMBIGUOUS_TRAILER,
            STATUS_NO_SEAL,
            STATUS_AMBIGUOUS_SEAL,
            STATUS_NO_FOLDER,
            STATUS_AMBIGUOUS_FOLDER,
            STATUS_DEST_EXISTS,
            STATUS_CONVERT_ERROR,
            STATUS_ERROR,
            "",
        ):
            self.assertTrue(is_leftover(status), msg=status)


class RunSummaryTests(unittest.TestCase):
    def test_all_moved(self) -> None:
        self.assertEqual(run_summary(12, 0), "12 moved.")

    def test_some_leftover(self) -> None:
        self.assertEqual(run_summary(9, 3), "3 not moved. Click a row to inspect.")

    def test_one_leftover(self) -> None:
        self.assertEqual(run_summary(0, 1), "1 not moved. Click a row to inspect.")


class InspectFooterTests(unittest.TestCase):
    def test_leftover_keeps_photo_in_folder(self) -> None:
        text = inspect_footer("shot02.heic", STATUS_NO_TRAILER)
        self.assertEqual(
            text,
            "shot02.heic is still in the photos folder. Could not read a truck code.",
        )

    def test_cancelled_row(self) -> None:
        text = inspect_footer("later.jpg", "")
        self.assertEqual(
            text,
            "later.jpg is still in the photos folder. This photo was not processed.",
        )

    def test_moved_row(self) -> None:
        self.assertEqual(inspect_footer("done.jpg", STATUS_MOVED), "done.jpg was moved.")


if __name__ == "__main__":
    unittest.main()
