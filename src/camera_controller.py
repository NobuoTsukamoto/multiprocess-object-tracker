"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import multiprocessing
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

    def run(self):
        self.logger = Logger(self.logging_config).get_logger()
        self.logger.info("CameraController process started.")

        # Attach to shared memory pools (must be done in the child process).
        tracking_pool = SharedFrameAccessor(self.tracking_pool_spec)
        gui_pool = SharedFrameAccessor(self.gui_pool_spec)

        cap = cv2.VideoCapture(0)  # 0 はデフォルトのカメラ
        if not cap.isOpened():
            self.logger.error("Failed to open camera.")
            self._report_error("カメラを開けませんでした。")
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

                # Resize/pad if camera returned an unexpected shape so it
                # fits the SHM slot. Most cameras honor the requested
                # resolution; this is a safety net.
                expected_shape = tracking_pool.shape
                if frame.shape != expected_shape:
                    frame = cv2.resize(
                        frame, (expected_shape[1], expected_shape[0])
                    )

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
