import sys
import unittest
from collections import OrderedDict
from pathlib import Path
from queue import Empty
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


class _QueueStub:
    def __init__(self, items):
        self.items = list(items)

    def get_nowait(self):
        if not self.items:
            raise Empty
        return self.items.pop(0)


def _make_controller(frame_ids, track_frame_id=None, detections="detections"):
    controller = object.__new__(GUIController)
    controller._frame_buffer = OrderedDict((fid, f"frame-{fid}") for fid in frame_ids)
    controller._frame_timestamps = OrderedDict((fid, float(fid)) for fid in frame_ids)
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

    def test_calculate_rate_uses_elapsed_between_samples(self):
        self.assertEqual(GUIController._calculate_rate([]), 0.0)
        self.assertEqual(GUIController._calculate_rate([1.0]), 0.0)
        self.assertEqual(GUIController._calculate_rate([1.0, 1.5, 2.0]), 2.0)

    def test_drain_queue_nowait_returns_drained_item_count(self):
        queue = _QueueStub(["old-1", "old-2", "old-3"])

        self.assertEqual(GUIController._drain_queue_nowait(queue), 3)
        self.assertEqual(queue.items, [])

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

    def test_drain_worker_errors_returns_first_and_drains_rest(self):
        controller = object.__new__(GUIController)
        err1 = SimpleNamespace(source="camera", message="m1", timestamp=1.0)
        err2 = SimpleNamespace(source="tracking", message="m2", timestamp=2.0)
        controller.error_queue = _QueueStub([err1, err2])

        self.assertIs(controller._drain_worker_errors(), err1)
        self.assertEqual(controller.error_queue.items, [])

    def test_drain_worker_errors_returns_none_when_empty(self):
        controller = object.__new__(GUIController)
        controller.error_queue = _QueueStub([])

        self.assertIsNone(controller._drain_worker_errors())

    def test_workers_alive_checks_camera_and_tracking_processes(self):
        controller = object.__new__(GUIController)
        controller.camera_process = _ProcessStub(alive=False)
        controller.tracking_process = _ProcessStub(alive=True)

        self.assertTrue(controller._workers_alive())

        controller.tracking_process = _ProcessStub(alive=False)
        self.assertFalse(controller._workers_alive())


if __name__ == "__main__":
    unittest.main()
