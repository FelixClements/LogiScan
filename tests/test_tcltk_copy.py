"""Copy staged Tcl/Tk files into a fake USB runtime."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.tcltk import copy_tcltk


class CopyTcltkTests(unittest.TestCase):
    def test_copies_layout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            vendor = root / "vendor" / "tcltk"
            runtime = root / "runtime" / "python"
            (vendor / "tcl" / "tcl8.6").mkdir(parents=True)
            (vendor / "tcl" / "tk8.6").mkdir(parents=True)
            (vendor / "Lib" / "site-packages" / "tkinter").mkdir(parents=True)
            (vendor / "_tkinter.pyd").write_bytes(b"pyd")
            (vendor / "tcl86t.dll").write_bytes(b"dll")
            (vendor / "tk86t.dll").write_bytes(b"dll")
            (vendor / "zlib1.dll").write_bytes(b"dll")
            (vendor / "tcl" / "tcl8.6" / "init.tcl").write_text("x", encoding="utf-8")
            (vendor / "Lib" / "site-packages" / "tkinter" / "__init__.py").write_text(
                "# tk", encoding="utf-8"
            )
            self.assertTrue(copy_tcltk(vendor, runtime))
            self.assertEqual((runtime / "_tkinter.pyd").read_bytes(), b"pyd")
            self.assertTrue((runtime / "tcl86t.dll").exists())
            self.assertTrue((runtime / "tk86t.dll").exists())
            self.assertTrue((runtime / "zlib1.dll").exists())
            self.assertTrue((runtime / "tcl" / "tcl8.6" / "init.tcl").exists())
            self.assertTrue((runtime / "tcl" / "tk8.6").is_dir())
            self.assertTrue(
                (runtime / "Lib" / "site-packages" / "tkinter" / "__init__.py").exists()
            )

    def test_missing_vendor_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            runtime = root / "runtime" / "python"
            runtime.mkdir(parents=True)
            self.assertFalse(copy_tcltk(root / "vendor" / "tcltk", runtime))
            self.assertFalse((runtime / "_tkinter.pyd").exists())

    def test_runtime_pyd_without_vendor_pyd_returns_true(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            vendor = root / "vendor" / "tcltk"
            runtime = root / "runtime" / "python"
            runtime.mkdir(parents=True)
            (runtime / "_tkinter.pyd").write_bytes(b"existing")
            (vendor / "tcl" / "tcl8.6").mkdir(parents=True)
            (vendor / "tcl" / "tk8.6").mkdir(parents=True)
            (vendor / "tcl" / "tcl8.6" / "init.tcl").write_text("x", encoding="utf-8")
            self.assertTrue(copy_tcltk(vendor, runtime))
            self.assertEqual((runtime / "_tkinter.pyd").read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
