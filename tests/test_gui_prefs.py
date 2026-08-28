"""GUI folder prefs without Tk."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.gui_prefs import GuiPrefs, load_prefs, prefs_path, save_prefs


class GuiPrefsTests(unittest.TestCase):
    def test_missing_file_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("photos"))
            self.assertIsNone(prefs.search_root)

    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            save_prefs(
                root,
                GuiPrefs(photos_dir=Path("E:/photos"), search_root=Path("D:/POs")),
            )
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("E:/photos"))
            self.assertEqual(prefs.search_root, Path("D:/POs"))
            payload = json.loads(prefs_path(root).read_text(encoding="utf-8"))
            self.assertEqual(payload["photos_dir"], str(Path("E:/photos")))
            self.assertEqual(payload["search_root"], str(Path("D:/POs")))

    def test_garbage_json_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prefs_path(root).write_text("{not json", encoding="utf-8")
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("photos"))
            self.assertIsNone(prefs.search_root)

    def test_unknown_keys_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            prefs_path(root).write_text(
                '{"photos_dir": "x", "search_root": "y", "extra": 1}',
                encoding="utf-8",
            )
            prefs = load_prefs(root)
            self.assertEqual(prefs.photos_dir, Path("x"))
            self.assertEqual(prefs.search_root, Path("y"))


if __name__ == "__main__":
    unittest.main()
