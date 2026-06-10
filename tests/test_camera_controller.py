import multiprocessing
import sys
import unittest
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from camera_controller import CameraController
from config_manager import ConfigManager

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "default.yaml"


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


class ResolveCameraSourceTest(unittest.TestCase):
    def test_int_passes_through_as_device_index(self):
        self.assertEqual(CameraController._resolve_camera_source(0), 0)
        self.assertEqual(CameraController._resolve_camera_source(2), 2)

    def test_digit_string_becomes_int_device_index(self):
        self.assertEqual(CameraController._resolve_camera_source("0"), 0)
        self.assertEqual(CameraController._resolve_camera_source("10"), 10)

    def test_non_digit_string_passes_through_as_path_or_url(self):
        self.assertEqual(
            CameraController._resolve_camera_source("video.mp4"), "video.mp4"
        )
        self.assertEqual(
            CameraController._resolve_camera_source("rtsp://host/stream"),
            "rtsp://host/stream",
        )

    def test_default_source_is_device_zero(self):
        # R-CAM-13d: camera.source unspecified -> device 0 (backward compat).
        from config_manager import CameraConfig

        self.assertEqual(CameraConfig().source, 0)


class InitStateTest(unittest.TestCase):
    # R-CAM-01/02: Process subclass; the constructor keeps the injected
    # collaborators as-is and initializes frame_id to 0 (logger stays None
    # until run() configures it in the child process).

    def test_subclasses_multiprocessing_process(self):
        self.assertTrue(issubclass(CameraController, multiprocessing.Process))

    def test_init_keeps_collaborators_and_zeroes_frame_id(self):
        manager = ConfigManager(str(DEFAULT_CONFIG))
        logging_config = manager.get_config("logging")
        tracking_spec = object()
        gui_spec = object()
        stop_event = object()
        error_queue = object()

        ctrl = CameraController(
            config_manager=manager,
            logging_config=logging_config,
            tracking_pool_spec=tracking_spec,
            gui_pool_spec=gui_spec,
            stop_event=stop_event,
            error_queue=error_queue,
        )

        self.assertIs(ctrl.config, manager.get_config("camera"))
        self.assertIs(ctrl.logging_config, logging_config)
        self.assertIs(ctrl.tracking_pool_spec, tracking_spec)
        self.assertIs(ctrl.gui_pool_spec, gui_spec)
        self.assertIs(ctrl.stop_event, stop_event)
        self.assertIs(ctrl.error_queue, error_queue)
        self.assertEqual(ctrl.frame_id, 0)
        self.assertIsNone(ctrl.logger)


class RecordingLogger:
    """Stand-in for the loguru logger that records (level, message) calls."""

    def __init__(self):
        self.records = []

    def __getattr__(self, level):
        def _record(message, *args, **kwargs):
            self.records.append((level, str(message)))

        return _record

    def messages(self, level):
        return [m for lv, m in self.records if lv == level]


class FakeEvent:
    """stop_event stub: is_set() returns False `false_count` times, then True."""

    def __init__(self, false_count):
        self.remaining = false_count

    def is_set(self):
        if self.remaining > 0:
            self.remaining -= 1
            return False
        return True


class FakeCap:
    def __init__(self, opened=True, reads=None):
        self.opened = opened
        self.reads = list(reads or [])
        self.released = False
        self.props = {}

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        self.props[prop] = value

    def read(self):
        if self.reads:
            return self.reads.pop(0)
        return False, None

    def release(self):
        self.released = True


class FakePool:
    def __init__(self, shape=(480, 640, 3), write_ok=True):
        self.shape = shape
        self.write_ok = write_ok
        self.writes = []
        self.closed = False

    def write(self, frame, frame_id, timestamp):
        self.writes.append((frame_id, frame.shape))
        return self.write_ok

    def close(self):
        self.closed = True


class ErrorQueueStub:
    def __init__(self):
        self.items = []

    def put_nowait(self, item):
        self.items.append(item)


class CameraRunTest(unittest.TestCase):
    """run() paths with cv2.VideoCapture / SharedFrameAccessor mocked out."""

    POOL_SHAPE = (480, 640, 3)

    def setUp(self):
        self.tracking_pool = FakePool(self.POOL_SHAPE)
        self.gui_pool = FakePool(self.POOL_SHAPE)
        self.logger = RecordingLogger()
        self.error_queue = ErrorQueueStub()

    def make_controller(self, stop_event):
        manager = ConfigManager(str(DEFAULT_CONFIG))
        return CameraController(
            config_manager=manager,
            logging_config=manager.get_config("logging"),
            tracking_pool_spec=None,
            gui_pool_spec=None,
            stop_event=stop_event,
            error_queue=self.error_queue,
        )

    def run_controller(self, ctrl, cap):
        with mock.patch("camera_controller.Logger") as logger_cls, mock.patch(
            "camera_controller.SharedFrameAccessor",
            side_effect=[self.tracking_pool, self.gui_pool],
        ) as accessor_cls, mock.patch(
            "camera_controller.cv2.VideoCapture", return_value=cap
        ), mock.patch(
            "time.sleep"
        ):
            logger_cls.return_value.get_logger.return_value = self.logger
            ctrl.run()
        self.logger_cls = logger_cls
        self.accessor_cls = accessor_cls

    def good_frame(self):
        return np.zeros(self.POOL_SHAPE, dtype=np.uint8)

    def test_open_failure_reports_error_closes_pools_and_returns(self):
        # R-CAM-04/14
        ctrl = self.make_controller(FakeEvent(0))
        cap = FakeCap(opened=False)

        self.run_controller(ctrl, cap)

        self.assertEqual(len(self.error_queue.items), 1)
        error = self.error_queue.items[0]
        self.assertEqual(error.source, "camera")
        self.assertTrue(self.tracking_pool.closed)
        self.assertTrue(self.gui_pool.closed)
        self.assertEqual(self.tracking_pool.writes, [])
        self.assertTrue(any("Failed to open" in m for m in self.logger.messages("error")))

    def test_run_configures_logger_and_attaches_both_pools(self):
        # R-CAM-03: run() builds the logger from logging_config and
        # attaches one SharedFrameAccessor per pool spec, tracking first.
        # (Doing so inside run() is what defers it to the child process.)
        tracking_spec = object()
        gui_spec = object()
        ctrl = self.make_controller(FakeEvent(0))
        ctrl.tracking_pool_spec = tracking_spec
        ctrl.gui_pool_spec = gui_spec

        self.run_controller(ctrl, FakeCap())

        self.logger_cls.assert_called_once_with(ctrl.logging_config)
        self.assertEqual(
            self.accessor_cls.call_args_list,
            [mock.call(tracking_spec), mock.call(gui_spec)],
        )

    def test_requests_resolution_and_fps_from_config(self):
        # R-CAM-05: width/height/fps are requested via cap.set (the camera
        # is not guaranteed to honor them).
        ctrl = self.make_controller(FakeEvent(0))
        cap = FakeCap()

        self.run_controller(ctrl, cap)

        self.assertEqual(cap.props[cv2.CAP_PROP_FRAME_WIDTH], ctrl.config.width)
        self.assertEqual(cap.props[cv2.CAP_PROP_FRAME_HEIGHT], ctrl.config.height)
        self.assertEqual(cap.props[cv2.CAP_PROP_FPS], ctrl.config.fps)

    def test_frames_written_to_both_pools_with_incrementing_frame_id(self):
        # R-CAM-09/11: each grabbed frame goes to both pools, frame_id +1.
        ctrl = self.make_controller(FakeEvent(2))
        cap = FakeCap(reads=[(True, self.good_frame()), (True, self.good_frame())])

        self.run_controller(ctrl, cap)

        self.assertEqual([w[0] for w in self.tracking_pool.writes], [0, 1])
        self.assertEqual([w[0] for w in self.gui_pool.writes], [0, 1])
        self.assertEqual(ctrl.frame_id, 2)

    def test_stop_event_exits_loop_and_releases_resources(self):
        # R-CAM-06/12: loop ends on stop_event; cap released, pools closed.
        ctrl = self.make_controller(FakeEvent(1))
        cap = FakeCap(reads=[(True, self.good_frame())])

        self.run_controller(ctrl, cap)

        self.assertTrue(cap.released)
        self.assertTrue(self.tracking_pool.closed)
        self.assertTrue(self.gui_pool.closed)

    def test_grab_failure_warns_and_continues(self):
        # R-CAM-07: ret=False -> warning + sleep + continue (no write).
        ctrl = self.make_controller(FakeEvent(2))
        cap = FakeCap(reads=[(False, None), (True, self.good_frame())])

        self.run_controller(ctrl, cap)

        self.assertTrue(
            any("Failed to grab" in m for m in self.logger.messages("warning"))
        )
        self.assertEqual([w[0] for w in self.tracking_pool.writes], [0])
        self.assertEqual(ctrl.frame_id, 1)

    def test_channel_mismatch_frame_dropped_without_frame_id_increment(self):
        # R-CAM-15: _fit_to_pool returns None -> error log + continue.
        ctrl = self.make_controller(FakeEvent(1))
        four_channel = np.zeros((480, 640, 4), dtype=np.uint8)
        cap = FakeCap(reads=[(True, four_channel)])

        self.run_controller(ctrl, cap)

        self.assertEqual(self.tracking_pool.writes, [])
        self.assertEqual(self.gui_pool.writes, [])
        self.assertEqual(ctrl.frame_id, 0)
        self.assertTrue(
            any("cannot fit pool shape" in m for m in self.logger.messages("error"))
        )

    def test_write_failure_warns_per_pool_but_frame_id_advances(self):
        # R-CAM-10: write False -> warning naming the pool; id still +1.
        self.tracking_pool.write_ok = False
        self.gui_pool.write_ok = False
        ctrl = self.make_controller(FakeEvent(1))
        cap = FakeCap(reads=[(True, self.good_frame())])

        self.run_controller(ctrl, cap)

        warnings = self.logger.messages("warning")
        self.assertTrue(any("Tracking pool dropped" in m for m in warnings))
        self.assertTrue(any("GUI pool dropped" in m for m in warnings))
        self.assertEqual(ctrl.frame_id, 1)


if __name__ == "__main__":
    unittest.main()
