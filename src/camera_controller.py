"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import multiprocessing
import re
import time

import cv2

from config_manager import ConfigManager, LoggingConfig
from data_models import WorkerError
from logger import Logger
from shared_frame_pool import SharedFrameAccessor, SharedFrameSpec


class CameraController(multiprocessing.Process):
    def __init__(
        self,
        config_manager: ConfigManager,
        logging_config: LoggingConfig,
        tracking_pool_spec: SharedFrameSpec,
        gui_pool_spec: SharedFrameSpec,
        stop_event: multiprocessing.Event,
        error_queue: multiprocessing.Queue,
    ):
        super().__init__()
        self.config = config_manager.get_config("camera")
        self.logging_config = logging_config
        self.tracking_pool_spec = tracking_pool_spec
        self.gui_pool_spec = gui_pool_spec
        self.stop_event = stop_event
        self.error_queue = error_queue
        self.frame_id = 0
        self.logger = None

    def _report_error(self, message: str):
        """Send a fatal error to the GUI before exiting the process."""
        if self.error_queue is None:
            return
        try:
            self.error_queue.put_nowait(
                WorkerError(source="camera", message=message, timestamp=time.time())
            )
        except Exception:
            if self.logger is not None:
                self.logger.error("Failed to report camera error to GUI.")

    @staticmethod
    def _resolve_camera_source(source):
        """Resolve camera.source to a cv2.VideoCapture argument (rule B).

        - int          → device index as-is
        - all-digit str → device index (int()), so "0" behaves like 0
        - other str     → path / URL passed through (video file, RTSP, ...)
        """
        if isinstance(source, str) and re.fullmatch(r"[0-9]+", source):
            return int(source)
        return source

    @staticmethod
    def _fit_to_pool(frame, expected_shape):
        """Fit a frame to the pool's expected shape.

        Resizes height/width when they differ. cv2.resize cannot change the
        channel count, so if the shape still differs (e.g. a grayscale or
        4-channel frame) the frame cannot fit the SHM slot; None is returned
        so the caller drops it instead of silently failing the write.
        """
        if frame.shape != expected_shape:
            frame = cv2.resize(frame, (expected_shape[1], expected_shape[0]))
        if frame.shape != expected_shape:
            return None
        return frame

    def run(self):
        self.logger = Logger(self.logging_config).get_logger()
        self.logger.info("CameraController process started.")

        # Attach to shared memory pools (must be done in the child process).
        tracking_pool = SharedFrameAccessor(self.tracking_pool_spec)
        gui_pool = SharedFrameAccessor(self.gui_pool_spec)

        source = self._resolve_camera_source(self.config.source)
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            self.logger.error(f"Failed to open camera (source={source!r}).")
            self._report_error(f"カメラを開けませんでした（source={source!r}）。")
            tracking_pool.close()
            gui_pool.close()
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        try:
            while not self.stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("Failed to grab frame.")
                    time.sleep(0.1)
                    continue

                # Fit the frame to the SHM slot shape. cv2.resize corrects
                # only height/width; a channel-count mismatch cannot be fixed,
                # so such frames are dropped explicitly here rather than
                # silently failing the write below. Most cameras honor the
                # requested resolution; this is a safety net.
                expected_shape = tracking_pool.shape
                fitted = self._fit_to_pool(frame, expected_shape)
                if fitted is None:
                    self.logger.error(
                        f"Frame shape {frame.shape} cannot fit pool shape "
                        f"{expected_shape} (channel mismatch); dropping frame."
                    )
                    continue
                frame = fitted

                timestamp = time.time()

                ok_t = tracking_pool.write(frame, self.frame_id, timestamp)
                ok_g = gui_pool.write(frame, self.frame_id, timestamp)

                if not ok_t:
                    self.logger.warning(
                        f"Tracking pool dropped frame {self.frame_id} "
                        "(no free slot)."
                    )
                if not ok_g:
                    self.logger.warning(
                        f"GUI pool dropped frame {self.frame_id} "
                        "(no free slot)."
                    )

                self.logger.debug(f"Frame {self.frame_id} published.")
                self.frame_id += 1
                # cap.read() already paces with camera FPS; no extra sleep.
        finally:
            cap.release()
            tracking_pool.close()
            gui_pool.close()
            self.logger.info("CameraController process stopped.")
