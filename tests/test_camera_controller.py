import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera_controller import CameraController


class FitToPoolTest(unittest.TestCase):
    EXPECTED = (480, 640, 3)

    def test_resizes_when_height_width_differ(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        fitted = CameraController._fit_to_pool(frame, self.EXPECTED)

        self.assertIsNotNone(fitted)
        self.assertEqual(fitted.shape, self.EXPECTED)

    def test_returns_frame_when_shape_already_matches(self):
        frame = np.zeros(self.EXPECTED, dtype=np.uint8)

        fitted = CameraController._fit_to_pool(frame, self.EXPECTED)

        self.assertEqual(fitted.shape, self.EXPECTED)

    def test_returns_none_for_grayscale_frame(self):
        frame = np.zeros((240, 320), dtype=np.uint8)

        self.assertIsNone(CameraController._fit_to_pool(frame, self.EXPECTED))

    def test_returns_none_for_four_channel_frame(self):
        frame = np.zeros((240, 320, 4), dtype=np.uint8)

        self.assertIsNone(CameraController._fit_to_pool(frame, self.EXPECTED))


if __name__ == "__main__":
    unittest.main()
