import sys
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gui_controller import GUIController


class _LoggerStub:
    def __init__(self):
        self.warning_messages = []
        self.error_messages = []

    def warning(self, message):
        self.warning_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)


class _ProcessStub:
    def __init__(self, alive):
        self._alive = alive

    def is_alive(self):
        return self._alive


def _make_controller(frame_ids, track_frame_id=None, detections="detections"):
    controller = object.__new__(GUIController)
    controller._frame_buffer = OrderedDict((fid, f"frame-{fid}") for fid in frame_ids)
    controller._frame_buffer_max = 10
    controller._overlay_miss_count = 0
    controller._last_overlay_miss_frame_id = None
    controller.logger = _LoggerStub()
    controller._latest_track = (
        None
        if track_frame_id is None
        else SimpleNamespace(frame_id=track_frame_id, detections=detections)
    )
    return controller


class GUIControllerTest(unittest.TestCase):
    def test_frame_buffer_max_uses_seconds_but_keeps_minimum(self):
        self.assertEqual(
            GUIController._calculate_frame_buffer_max(
                fps=15, frame_buffer_seconds=2.0, minimum=12
            ),
            30,
        )
        self.assertEqual(
            GUIController._calculate_frame_buffer_max(
                fps=15, frame_buffer_seconds=0.5, minimum=12
            ),
            12,
        )

    def test_select_display_frame_prefers_matching_tracking_frame(self):
        controller = _make_controller(frame_ids=[10, 11, 12], track_frame_id=11)

        image, detections = controller._select_display_frame()

        self.assertEqual(image, "frame-11")
        self.assertEqual(detections, "detections")
        self.assertEqual(list(controller._frame_buffer.keys()), [11, 12])
        self.assertEqual(controller._overlay_miss_count, 0)

    def test_select_display_frame_logs_stale_overlay_miss_once(self):
        controller = _make_controller(frame_ids=[10, 11, 12], track_frame_id=8)

        image, detections = controller._select_display_frame()
        second_image, second_detections = controller._select_display_frame()

        self.assertEqual(image, "frame-12")
        self.assertIsNone(detections)
        self.assertEqual(second_image, "frame-12")
        self.assertIsNone(second_detections)
        self.assertEqual(controller._overlay_miss_count, 1)
        self.assertEqual(len(controller.logger.warning_messages), 1)
        self.assertIn("track_frame_id=8", controller.logger.warning_messages[0])

    def test_select_display_frame_does_not_log_when_track_frame_is_pending(self):
        controller = _make_controller(frame_ids=[10, 11, 12], track_frame_id=13)

        image, detections = controller._select_display_frame()

        self.assertEqual(image, "frame-12")
        self.assertIsNone(detections)
        self.assertEqual(controller._overlay_miss_count, 0)
        self.assertEqual(controller.logger.warning_messages, [])

    def test_workers_alive_checks_camera_and_tracking_processes(self):
        controller = object.__new__(GUIController)
        controller.camera_process = _ProcessStub(alive=False)
        controller.tracking_process = _ProcessStub(alive=True)

        self.assertTrue(controller._workers_alive())

        controller.tracking_process = _ProcessStub(alive=False)
        self.assertFalse(controller._workers_alive())


if __name__ == "__main__":
    unittest.main()
