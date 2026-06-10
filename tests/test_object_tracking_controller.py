import sys
import unittest
from pathlib import Path
from queue import Empty, Full, Queue
from unittest import mock

import numpy as np
import supervision as sv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config_manager import ConfigManager
from data_models import FrameRef, TrackingResult
from object_tracking_controller import (
    FRAME_READ_TIMEOUT_SEC,
    ObjectTrackingController,
)

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "default.yaml"


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


class FakeFramePool:
    """Records read/read_latest calls and returns a fixed frame."""

    def __init__(self):
        self.calls = []
        self.frame_ref = FrameRef(frame_id=7, timestamp=1.0, slot=0)
        self.image = np.zeros((4, 4, 3), dtype=np.uint8)

    def read(self, timeout=None):
        self.calls.append(("read", timeout))
        return self.frame_ref, self.image

    def read_latest(self, timeout=None, max_skip=None):
        self.calls.append(("read_latest", timeout, max_skip))
        return self.frame_ref, self.image, 3


class ErrorQueueStub:
    def __init__(self):
        self.items = []

    def put_nowait(self, item):
        self.items.append(item)


def make_controller():
    manager = ConfigManager(str(DEFAULT_CONFIG))
    return ObjectTrackingController(
        config_manager=manager,
        logging_config=manager.get_config("logging"),
        frame_pool_spec=None,
        track_queue=None,
        stop_event=None,
        error_queue=None,
    )


class ReadFrameTest(unittest.TestCase):
    # R-OTC-09: each policy maps to the right pool call and a 3-tuple.

    def test_fifo_uses_read_with_zero_skip(self):
        ctrl = make_controller()
        ctrl.track_config.frame_read_policy = "fifo"
        pool = FakeFramePool()

        frame_ref, image, skipped = ctrl._read_frame(pool)

        self.assertEqual(pool.calls, [("read", FRAME_READ_TIMEOUT_SEC)])
        self.assertIs(frame_ref, pool.frame_ref)
        self.assertIs(image, pool.image)
        self.assertEqual(skipped, 0)

    def test_latest_uses_read_latest_without_skip_bound(self):
        ctrl = make_controller()
        ctrl.track_config.frame_read_policy = "latest"
        pool = FakeFramePool()

        frame_ref, image, skipped = ctrl._read_frame(pool)

        self.assertEqual(pool.calls, [("read_latest", FRAME_READ_TIMEOUT_SEC, None)])
        self.assertIs(frame_ref, pool.frame_ref)
        self.assertEqual(skipped, 3)

    def test_bounded_latest_passes_max_frame_skip(self):
        ctrl = make_controller()
        ctrl.track_config.frame_read_policy = "bounded_latest"
        ctrl.track_config.max_frame_skip = 5
        pool = FakeFramePool()

        ctrl._read_frame(pool)

        self.assertEqual(pool.calls, [("read_latest", FRAME_READ_TIMEOUT_SEC, 5)])

    def test_bounded_latest_clamps_negative_skip_to_zero(self):
        ctrl = make_controller()
        ctrl.track_config.frame_read_policy = "bounded_latest"
        ctrl.track_config.max_frame_skip = -5
        pool = FakeFramePool()

        ctrl._read_frame(pool)

        self.assertEqual(pool.calls, [("read_latest", FRAME_READ_TIMEOUT_SEC, 0)])

    def test_unknown_policy_warns_and_falls_back_to_bounded_latest(self):
        # R-OTC-10
        ctrl = make_controller()
        ctrl.track_config.frame_read_policy = "no_such_policy"
        ctrl.logger = RecordingLogger()
        pool = FakeFramePool()

        ctrl._read_frame(pool)

        self.assertEqual(
            pool.calls,
            [("read_latest", FRAME_READ_TIMEOUT_SEC, ctrl.track_config.max_frame_skip)],
        )
        warnings = ctrl.logger.messages("warning")
        self.assertEqual(len(warnings), 1)
        self.assertIn("no_such_policy", warnings[0])


class PreprocessTest(unittest.TestCase):
    # R-OTC-14: letterbox resize keeps aspect ratio, pads with 114, returns
    # CHW float32 and the resize ratio.

    def test_output_shape_dtype_and_ratio(self):
        ctrl = make_controller()
        img = np.full((240, 320, 3), 200, dtype=np.uint8)

        preprocessed, ratio = ctrl._preprocess(img, (416, 416))

        self.assertEqual(preprocessed.shape, (3, 416, 416))
        self.assertEqual(preprocessed.dtype, np.float32)
        self.assertTrue(preprocessed.flags["C_CONTIGUOUS"])
        self.assertAlmostEqual(ratio, min(416 / 240, 416 / 320))

    def test_image_area_filled_and_padding_is_114(self):
        ctrl = make_controller()
        img = np.full((240, 320, 3), 200, dtype=np.uint8)

        preprocessed, ratio = ctrl._preprocess(img, (416, 416))

        filled_h = int(240 * ratio)  # 312
        filled_w = int(320 * ratio)  # 416
        self.assertTrue(np.all(preprocessed[:, :filled_h, :filled_w] == 200.0))
        self.assertTrue(np.all(preprocessed[:, filled_h:, :] == 114.0))


class PostprocessTest(unittest.TestCase):
    # R-OTC-14: YOLOX grid decode — xy = (pred + grid) * stride,
    # wh = exp(pred) * stride, over strides [8, 16, 32].

    def test_grid_decode_for_zero_predictions(self):
        ctrl = make_controller()
        # (416/8)^2 + (416/16)^2 + (416/32)^2 = 2704 + 676 + 169
        n_anchors = 52 * 52 + 26 * 26 + 13 * 13
        outputs = np.zeros((1, n_anchors, 6), dtype=np.float32)

        decoded = ctrl._postprocess(outputs, (416, 416))

        self.assertEqual(decoded.shape, (1, n_anchors, 6))
        # First anchor of the stride-8 grid: cell (0, 0).
        np.testing.assert_allclose(decoded[0, 0, :2], [0.0, 0.0])
        np.testing.assert_allclose(decoded[0, 0, 2:4], [8.0, 8.0])
        # Second anchor is cell (1, 0): x = (0 + 1) * 8.
        np.testing.assert_allclose(decoded[0, 1, :2], [8.0, 0.0])
        # First anchor of the stride-16 grid.
        np.testing.assert_allclose(decoded[0, 52 * 52, 2:4], [16.0, 16.0])
        # Last anchor belongs to the stride-32 grid.
        np.testing.assert_allclose(decoded[0, -1, 2:4], [32.0, 32.0])


class FilterDetectionsTest(unittest.TestCase):
    # R-OTC-16: staged filters in order confidence -> NMS -> class -> area.
    # Defaults: detection_threshold 0.1, nms_iou_threshold 0.45,
    # class_id [0], min_box_area 100.

    def test_each_stage_removes_its_candidate(self):
        ctrl = make_controller()
        detections = sv.Detections(
            xyxy=np.array(
                [
                    [0, 0, 50, 50],  # survivor: conf .9, class 0, area 2500
                    [2, 2, 52, 52],  # near-duplicate of survivor -> NMS
                    [100, 100, 150, 150],  # conf .05 -> confidence filter
                    [200, 200, 250, 250],  # class 1 -> class filter
                    [300, 300, 305, 305],  # area 25 -> area filter
                ],
                dtype=float,
            ),
            confidence=np.array([0.9, 0.5, 0.05, 0.9, 0.9]),
            class_id=np.array([0, 0, 0, 1, 0]),
        )

        filtered = ctrl._filter_detections(detections)

        self.assertEqual(len(filtered), 1)
        np.testing.assert_allclose(filtered.xyxy[0], [0, 0, 50, 50])
        self.assertEqual(filtered.confidence[0], 0.9)

    def test_confidence_is_exclusive_and_area_is_inclusive(self):
        ctrl = make_controller()
        detections = sv.Detections(
            xyxy=np.array(
                [
                    [0, 0, 10, 10],  # area exactly 100 -> kept (>=)
                    [100, 100, 150, 150],  # conf exactly 0.1 -> dropped (>)
                ],
                dtype=float,
            ),
            confidence=np.array([0.9, 0.1]),
            class_id=np.array([0, 0]),
        )

        filtered = ctrl._filter_detections(detections)

        self.assertEqual(len(filtered), 1)
        np.testing.assert_allclose(filtered.xyxy[0], [0, 0, 10, 10])


class PublishResultTest(unittest.TestCase):
    # R-OTC-20: put_nowait; on Full drop the oldest and retry; if still
    # Full, log a warning and drop the new result.

    @staticmethod
    def make_result(frame_id):
        return TrackingResult(
            frame_id=frame_id,
            timestamp=0.0,
            track_infos=[],
            detections=None,
            process_time_ms=0.0,
        )

    def test_puts_result_when_queue_has_space(self):
        ctrl = make_controller()
        ctrl.track_queue = Queue(maxsize=1)
        result = self.make_result(1)

        ctrl._publish_result(result)

        self.assertIs(ctrl.track_queue.get_nowait(), result)

    def test_full_queue_drops_oldest_and_keeps_newest(self):
        ctrl = make_controller()
        ctrl.track_queue = Queue(maxsize=1)
        ctrl.track_queue.put_nowait(self.make_result(1))
        newest = self.make_result(2)

        ctrl._publish_result(newest)

        self.assertIs(ctrl.track_queue.get_nowait(), newest)
        with self.assertRaises(Empty):
            ctrl.track_queue.get_nowait()

    def test_persistently_full_queue_warns_and_drops_result(self):
        class AlwaysFullQueue:
            def __init__(self):
                self.get_calls = 0

            def put_nowait(self, item):
                raise Full

            def get_nowait(self):
                self.get_calls += 1
                raise Empty

        ctrl = make_controller()
        ctrl.track_queue = AlwaysFullQueue()
        ctrl.logger = RecordingLogger()

        ctrl._publish_result(self.make_result(1))  # must not raise

        self.assertEqual(ctrl.track_queue.get_calls, 1)
        warnings = ctrl.logger.messages("warning")
        self.assertEqual(len(warnings), 1)
        self.assertIn("Track queue is full", warnings[0])


class OnnxLoadFailureTest(unittest.TestCase):
    def test_load_failure_reports_worker_error_and_returns(self):
        # R-OTC-05/23: a failed InferenceSession load sends WorkerError to
        # the GUI and returns early. frame_pool_spec is None, so reaching
        # the tracking loop would raise — no exception proves the early
        # return.
        ctrl = make_controller()
        ctrl.error_queue = ErrorQueueStub()
        logger = RecordingLogger()
        with mock.patch("object_tracking_controller.Logger") as logger_cls, mock.patch(
            "object_tracking_controller.onnxruntime.InferenceSession",
            side_effect=RuntimeError("boom"),
        ):
            logger_cls.return_value.get_logger.return_value = logger
            ctrl.run()

        self.assertEqual(len(ctrl.error_queue.items), 1)
        error = ctrl.error_queue.items[0]
        self.assertEqual(error.source, "tracking")
        self.assertIn("boom", error.message)
        self.assertTrue(any("boom" in m for m in logger.messages("error")))


class ReportErrorTest(unittest.TestCase):
    def test_puts_worker_error_on_queue(self):
        ctrl = make_controller()
        ctrl.error_queue = ErrorQueueStub()

        ctrl._report_error("something failed")

        self.assertEqual(len(ctrl.error_queue.items), 1)
        error = ctrl.error_queue.items[0]
        self.assertEqual(error.source, "tracking")
        self.assertEqual(error.message, "something failed")

    def test_noop_when_queue_is_none(self):
        ctrl = make_controller()
        ctrl.error_queue = None

        ctrl._report_error("ignored")  # must not raise

    def test_put_failure_is_logged_not_raised(self):
        class FullQueue:
            def put_nowait(self, item):
                raise RuntimeError("queue full")

        ctrl = make_controller()
        ctrl.error_queue = FullQueue()
        ctrl.logger = RecordingLogger()

        ctrl._report_error("something failed")  # must not raise

        self.assertEqual(len(ctrl.logger.messages("error")), 1)


if __name__ == "__main__":
    unittest.main()
