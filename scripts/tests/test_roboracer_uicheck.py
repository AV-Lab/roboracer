"""S2 (D21 A): automated pre-Connect check on synthetic window images (no player needed)."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import roboracer_uicheck as uc  # noqa: E402


def window(path, text_boxes, background=40, noise=0, seed=0):
    """A 1280x720 frame: dark background (+ optional sub-threshold noise, like the 3D view behind the
    semi-transparent HUD) with white 'glyph' boxes."""
    rng = np.random.default_rng(seed)
    pixels = np.full((720, 1280, 3), background, dtype=np.int16)
    if noise:
        pixels += rng.integers(-noise, noise + 1, size=pixels.shape, dtype=np.int16)
    for x0, y0, x1, y1 in text_boxes:
        pixels[y0:y1, x0:x1] = 235
    Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8)).save(path)
    return path


SAFE = [(30, 260, 200, 285), (30, 330, 160, 352), (1050, 120, 1200, 130), (1050, 178, 1150, 196), (1050, 215, 1120, 226)]


class UiCheckTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.d = Path(self.dir.name)
        ref_image = window(self.d / "ref.png", SAFE)
        self.ref_path = self.d / "ref.json"
        self.ref_path.write_text(json.dumps(uc.make_reference(ref_image, "safe state", "tester")))
        self.ref = uc.load_reference(self.ref_path)

    def tearDown(self):
        self.dir.cleanup()

    def test_same_text_passes_despite_background_changes(self):
        image = window(self.d / "a.png", SAFE, background=60, noise=40, seed=3)  # 3D view moved, text the same
        result = uc.check(image, self.ref)
        self.assertTrue(result["passed"], result)
        self.assertEqual(set(uc.REGIONS), set(result["mismatch_px"]))

    def test_changed_label_fails_its_region(self):
        changed = list(SAFE)
        changed[1] = (30, 330, 120, 352)  # "Manual" is shorter than "Guarded"
        result = uc.check(window(self.d / "b.png", changed), self.ref)
        self.assertFalse(result["passed"])
        self.assertGreater(result["mismatch_px"]["mode (Guarded)"], uc.MAX_MISMATCH_PX)
        self.assertEqual(0, result["mismatch_px"]["connection state (Disconnected)"])

    def test_wrong_window_size_is_refused(self):
        Image.new("RGB", (800, 600)).save(self.d / "small.png")
        with self.assertRaises(ValueError):
            uc.check(self.d / "small.png", self.ref)

    def test_reference_image_changed_after_review_is_refused(self):
        window(self.d / "ref.png", SAFE[:2])  # overwrite the reviewed image
        with self.assertRaises(ValueError):
            uc.load_reference(self.ref_path)

    def test_cli_exit_codes(self):
        ok = uc.main(["check", "--reference", str(self.ref_path), "--image", str(window(self.d / "c.png", SAFE))])
        bad = uc.main(["check", "--reference", str(self.ref_path), "--image", str(window(self.d / "d.png", SAFE[:3]))])
        self.assertEqual((0, 1), (ok, bad))


if __name__ == "__main__":
    unittest.main()
