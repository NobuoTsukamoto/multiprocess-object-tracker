"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import multiprocessing
import time
from queue import Empty, Full

import cv2
import numpy as np
import onnxruntime
import supervision as sv

from config_manager import ConfigManager, LoggingConfig
from data_models import FrameRef, TrackInfo, TrackingResult, WorkerError
from logger import Logger
from shared_frame_pool import SharedFrameAccessor, SharedFrameSpec


FRAME_READ_TIMEOUT_SEC = 0.1


class ObjectTrackingController(multiprocessing.Process):
    def __init__(
        self,
        config_manager: ConfigManager,
        logging_config: LoggingConfig,
        frame_pool_spec: SharedFrameSpec,
        track_queue: multiprocessing.Queue,
        stop_event: multiprocessing.Event,
        error_queue: multiprocessing.Queue,
    ):
        super().__init__()
        self.det_config = config_manager.get_config("detection")
        self.track_config = config_manager.get_config("tracking")
        self.camera_config = config_manager.get_config("camera")
        self.logging_config = logging_config
        self.frame_pool_spec = frame_pool_spec
        self.track_queue = track_queue
        self.stop_event = stop_event
        self.error_queue = error_queue
        self.logger = None

    def _report_error(self, message: str):
        """Send a fatal error to the GUI before exiting the process."""
        if self.error_queue is None:
            return
        try:
            self.error_queue.put_nowait(
                WorkerError(source="tracking", message=message, timestamp=time.time())
            )
        except Exception:
            if self.logger is not None:
                self.logger.error("Failed to report tracking error to GUI.")

    def _read_frame(self, frame_pool: SharedFrameAccessor):
        """Read a frame using the configured latency/quality policy."""
        policy = getattr(self.track_config, "frame_read_policy", "bounded_latest")

        if policy == "fifo":
            frame_ref, image = frame_pool.read(timeout=FRAME_READ_TIMEOUT_SEC)
            return frame_ref, image, 0

        if policy == "latest":
            return frame_pool.read_latest(timeout=FRAME_READ_TIMEOUT_SEC)

        if policy == "bounded_latest":
            max_skip = max(0, int(getattr(self.track_config, "max_frame_skip", 2)))
            return frame_pool.read_latest(
                timeout=FRAME_READ_TIMEOUT_SEC, max_skip=max_skip
            )

        if self.logger is not None:
            self.logger.warning(
                f"Unknown frame_read_policy '{policy}'; using bounded_latest."
            )
        max_skip = max(0, int(getattr(self.track_config, "max_frame_skip", 2)))
        return frame_pool.read_latest(timeout=FRAME_READ_TIMEOUT_SEC, max_skip=max_skip)

    def _preprocess(self, img: np.ndarray, input_size: tuple, swap=(2, 0, 1)):
        if len(img.shape) == 3:
            padded_img = (
                np.ones((input_size[0], input_size[1], 3), dtype=np.uint8) * 114
            )
        else:
            padded_img = np.ones(input_size, dtype=np.uint8) * 114

        r = min(input_size[0] / img.shape[0], input_size[1] / img.shape[1])
        resized_img = cv2.resize(
            img,
            (int(img.shape[1] * r), int(img.shape[0] * r)),
            interpolation=cv2.INTER_LINEAR,
        ).astype(np.uint8)
        padded_img[: int(img.shape[0] * r), : int(img.shape[1] * r)] = resized_img
        padded_img = padded_img.transpose(swap)

        padded_img = np.ascontiguousarray(padded_img, dtype=np.float32)
        return padded_img, r

    def _postprocess(self, outputs: np.ndarray, img_size: tuple, p6=False):
        grids = []
        expanded_strides = []
        strides = [8, 16, 32] if not p6 else [8, 16, 32, 64]

        hsizes = [img_size[0] // stride for stride in strides]
        wsizes = [img_size[1] // stride for stride in strides]

        for hsize, wsize, stride in zip(hsizes, wsizes, strides):
            xv, yv = np.meshgrid(np.arange(wsize), np.arange(hsize))
            grid = np.stack((xv, yv), 2).reshape(1, -1, 2)
            grids.append(grid)
            shape = grid.shape[:2]
            expanded_strides.append(np.full((*shape, 1), stride))

        grids = np.concatenate(grids, 1)
        expanded_strides = np.concatenate(expanded_strides, 1)
        outputs[..., :2] = (outputs[..., :2] + grids) * expanded_strides
        outputs[..., 2:4] = np.exp(outputs[..., 2:4]) * expanded_strides

        return outputs

    def run(self):
        self.logger = Logger(self.logging_config).get_logger()
        self.logger.info("ObjectTrackingController process started.")
        try:
            session = onnxruntime.InferenceSession(
                self.det_config.model_path, providers=self.det_config.providers
            )
            self.logger.info(f"ONNX model loaded from {self.det_config.model_path}")
            input_shape = session.get_inputs()[0].shape[2:]
        except Exception as e:
            self.logger.error(f"Failed to load ONNX model: {e}")
            self._report_error(f"モデルの読み込みに失敗しました: {e}")
            return

        tracker = sv.ByteTrack(
            track_activation_threshold=self.det_config.score_threshold,
            lost_track_buffer=self.track_config.max_lost,
            minimum_matching_threshold=self.track_config.iou_threshold,
            frame_rate=self.camera_config.fps,
        )

        frame_pool = SharedFrameAccessor(self.frame_pool_spec)

        frame_count = 0
        perf_start_time = time.time()
        last_input_frame_id = None
        last_skipped_count = 0
        last_input_lag_ms = 0.0
        last_frame_id_delta = 0
        try:
            while not self.stop_event.is_set():
                try:
                    frame_ref: FrameRef
                    frame_ref, image, skipped_count = self._read_frame(frame_pool)
                except Empty:
                    continue
                if self.stop_event.is_set():
                    break

                start_time = time.time()
                last_skipped_count = skipped_count
                last_input_lag_ms = (start_time - frame_ref.timestamp) * 1000
                if last_input_frame_id is None:
                    last_frame_id_delta = 0
                else:
                    last_frame_id_delta = frame_ref.frame_id - last_input_frame_id
                last_input_frame_id = frame_ref.frame_id

                # Preprocess
                preprocessed_image, ratio = self._preprocess(image, input_shape)

                # Inference
                input_name = session.get_inputs()[0].name
                outputs = session.run(
                    None, {input_name: preprocessed_image[None, :, :, :]}
                )[0]

                if not isinstance(outputs, np.ndarray):
                    outputs = np.array(outputs)

                # Postprocess
                predictions = self._postprocess(outputs, input_shape)[0]

                boxes = predictions[:, :4]
                scores = predictions[:, 4:5] * predictions[:, 5:]

                boxes_xyxy = np.ones_like(boxes)
                boxes_xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2.0
                boxes_xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2.0
                boxes_xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2.0
                boxes_xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2.0
                boxes_xyxy /= ratio

                class_ids = np.argmax(scores, axis=1)
                confidences = np.max(scores, axis=1)
                detections = sv.Detections(
                    xyxy=boxes_xyxy,
                    confidence=confidences,
                    class_id=class_ids,
                )
                detections = detections[detections.confidence > 0.1]
                detections = detections.with_nms(threshold=0.45)

                mask = np.isin(detections.class_id, self.track_config.class_id)
                detections = detections[mask]
                detections = detections[detections.area >= self.track_config.min_box_area]

                tracked_detections = tracker.update_with_detections(detections=detections)

                track_results = []
                if tracked_detections.tracker_id is not None:
                    for i in range(len(tracked_detections)):
                        track_info = TrackInfo(
                            track_id=int(tracked_detections.tracker_id[i]),
                            class_id=int(tracked_detections.class_id[i]),
                        )
                        track_results.append(track_info)

                end_time = time.time()
                process_time_ms = (end_time - start_time) * 1000
                total_latency_ms = (end_time - frame_ref.timestamp) * 1000

                tracking_result = TrackingResult(
                    frame_id=frame_ref.frame_id,
                    timestamp=frame_ref.timestamp,
                    track_infos=track_results,
                    detections=tracked_detections,
                    process_time_ms=process_time_ms,
                    queue_latency_ms=last_input_lag_ms,
                    total_latency_ms=total_latency_ms,
                )

                try:
                    self.track_queue.put_nowait(tracking_result)
                except Full:
                    # Drop oldest tracking result so the GUI sees the
                    # most recent inference, not stale ones.
                    try:
                        self.track_queue.get_nowait()
                    except Empty:
                        pass
                    try:
                        self.track_queue.put_nowait(tracking_result)
                    except Full:
                        self.logger.warning("Track queue is full; dropped result.")

                frame_count += 1
                if frame_count % self.logging_config.performance_interval == 0:
                    elapsed = time.time() - perf_start_time
                    avg_fps = (
                        self.logging_config.performance_interval / elapsed
                        if elapsed > 0
                        else 0
                    )
                    self.logger.log(
                        "PERFORMANCE",
                        f"frame={frame_count} | "
                        f"process_time={process_time_ms:.2f}ms | "
                        f"avg_fps={avg_fps:.2f} | "
                        f"frame_id_delta={last_frame_id_delta} | "
                        f"skipped={last_skipped_count} | "
                        f"input_lag={last_input_lag_ms:.2f}ms",
                    )
                    perf_start_time = time.time()
        finally:
            frame_pool.close()
            self.logger.info("ObjectTrackingController process stopped.")
