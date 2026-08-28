"""Photo listing and JPEG conversion."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logiscan.config import Config
from logiscan.images import list_images, load_image, prepare_working_image


class ListImagesTests(unittest.TestCase):
    def test_default_suffixes_include_heic(self) -> None:
        suffixes = Config().image_suffixes
        self.assertIn(".heic", suffixes)
        self.assertIn(".heif", suffixes)
        self.assertIn(".jpg", suffixes)
        self.assertIn(".png", suffixes)

    def test_lists_heic_and_ignores_processed_subdir(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            (folder / "shot.HEIC").write_bytes(b"x")
            (folder / "keep.jpg").write_bytes(b"x")
            processed = folder / "_processed"
            processed.mkdir()
            (processed / "old.jpg").write_bytes(b"x")
            names = {path.name.lower() for path in list_images(folder, Config().image_suffixes)}
            self.assertEqual(names, {"shot.heic", "keep.jpg"})


class PrepareWorkingImageTests(unittest.TestCase):
    def test_jpeg_is_used_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "a.jpg"
            path.write_bytes(b"not-a-real-jpeg")
            working, temp = prepare_working_image(path)
            self.assertEqual(working, path)
            self.assertIsNone(temp)

    def test_png_becomes_temp_jpeg(self) -> None:
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "a.png"
            ok, encoded = cv2.imencode(".png", np.zeros((16, 16, 3), dtype=np.uint8))
            self.assertTrue(ok)
            encoded.tofile(str(path))
            working, temp = prepare_working_image(path)
            self.assertIsNotNone(temp)
            self.assertEqual(working.suffix.lower(), ".jpg")
            self.assertTrue(path.exists())
            image = load_image(working)
            self.assertEqual(image.shape[0], 16)
            if temp is not None:
                temp.unlink()


if __name__ == "__main__":
    unittest.main()
