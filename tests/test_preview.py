"""Thumbnail PNG helper without Tk."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

from logiscan.preview import thumbnail_png


class ThumbnailPngTests(unittest.TestCase):
    def test_jpeg_fits_max_size(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "wide.jpg"
            Image.new("RGB", (800, 200), color=(10, 20, 30)).save(path, "JPEG")
            data = thumbnail_png(path, max_size=280)
            out = Image.open(io.BytesIO(data))
            self.assertEqual(out.format, "PNG")
            self.assertLessEqual(out.size[0], 280)
            self.assertLessEqual(out.size[1], 280)
            self.assertEqual(out.size[0], 280)
            self.assertEqual(out.size[1], 70)

    def test_small_image_not_upscaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "tiny.jpg"
            Image.new("RGB", (40, 30), color=(1, 2, 3)).save(path, "JPEG")
            out = Image.open(io.BytesIO(thumbnail_png(path, max_size=280)))
            self.assertEqual(out.size, (40, 30))

    def test_unreadable_raises(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bad.jpg"
            path.write_bytes(b"not-an-image")
            with self.assertRaises(ValueError):
                thumbnail_png(path)


if __name__ == "__main__":
    unittest.main()
