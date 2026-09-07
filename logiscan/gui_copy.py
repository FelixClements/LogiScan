"""Plain-language status copy for the operator GUI. No Tk."""

from __future__ import annotations

from logiscan.config import (
    DEST_FOLDER_SEP,
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

_STATUS_LABELS = {
    STATUS_NO_TRAILER: "No truck code",
    STATUS_AMBIGUOUS_TRAILER: "Several truck codes",
    STATUS_NO_SEAL: "No seal",
    STATUS_AMBIGUOUS_SEAL: "Several seals",
    STATUS_NO_FOLDER: "No PO folder",
    STATUS_AMBIGUOUS_FOLDER: "Several PO folders",
    STATUS_DEST_EXISTS: "Already filed",
    STATUS_CONVERT_ERROR: "Could not open",
    STATUS_ERROR: "Error",
    STATUS_MOVED: "Moved",
}

_LEFTOVER_REASONS = {
    STATUS_NO_TRAILER: "Could not read a truck code.",
    STATUS_AMBIGUOUS_TRAILER: "Found more than one truck code.",
    STATUS_NO_SEAL: "Could not read a seal number.",
    STATUS_AMBIGUOUS_SEAL: "Found more than one seal number.",
    STATUS_NO_FOLDER: "No PO folder for this truck code.",
    STATUS_AMBIGUOUS_FOLDER: "This truck code matches more than one PO folder.",
    STATUS_DEST_EXISTS: "A photo for this truck and seal is already in the PO folder.",
    STATUS_CONVERT_ERROR: "Could not open this photo.",
}


def status_label(status: str) -> str:
    if not status:
        return "Not processed"
    return _STATUS_LABELS.get(status, status)


def leftover_reason(
    status: str,
    error: str | None = None,
    dest_folder: str | None = None,
) -> str:
    if status == STATUS_ERROR:
        if error:
            return error
        return "Processing failed."
    if not status:
        return "This photo was not processed."
    if (
        status == STATUS_DEST_EXISTS
        and dest_folder
        and DEST_FOLDER_SEP in dest_folder
    ):
        return (
            "This truck code matches more than one PO folder, and a photo "
            "for this truck and seal is already in at least one of them."
        )
    return _LEFTOVER_REASONS.get(status, status)


def is_leftover(status: str) -> bool:
    return status != STATUS_MOVED


def run_summary(moved: int, leftover: int) -> str:
    if leftover:
        return f"{leftover} not moved. Click a row to inspect."
    return f"{moved} moved."


def inspect_footer(
    filename: str,
    status: str,
    error: str | None = None,
    dest_folder: str | None = None,
) -> str:
    if not is_leftover(status):
        return f"{filename} was moved."
    return (
        f"{filename} is still in the photos folder. "
        f"{leftover_reason(status, error, dest_folder=dest_folder)}"
    )
