"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import cv2
import time
import multiprocessing
from queue import Empty, Full

from config_manager import ConfigManager, LoggingConfig
from logger import Logger
from data_models import FrameData


class CameraController(multiprocessing.Process):
    def __init__(
        self,
        config_manager: ConfigManager,
        logging_config: LoggingConfig,
        tracking_frame_queue: multiprocessing.Queue,
        gui_frame_queue: multiprocessing.Queue,
        stop_event: multiprocessing.Event,
    ):
        super().__init__()
        self.config = config_manager.get_config("camera")
        self.logging_config = logging_config
        self.tracking_frame_queue = tracking_frame_queue
        self.gui_frame_queue = gui_frame_queue
        self.stop_event = stop_event
        self.frame_id = 0
        self.logger = None

        # キューのインスタンスをログ出力（warning出力時に区別できるように）
        self.tracking_frame_queue_name = (
            f"TrackingQueue-{id(self.tracking_frame_queue)}"
        )
        self.gui_frame_queue_name = f"GuiQueue-{id(self.gui_frame_queue)}"

    def _put_frame_to_queue(
        self, queue: multiprocessing.Queue, frame_data: FrameData, queue_name: str
    ):
        # キューがいっぱいなら一番古いものを捨てる
        if queue.full():
            try:
                queue.get_nowait()
            except Empty:
                pass  # 他のプロセスが同時にgetした場合

        try:
            queue.put_nowait(frame_data)
            if self.logger is not None:
                self.logger.debug(
                    f"Frame {frame_data.frame_id} put into {queue_name}. size = {queue.qsize()}"
                )
        except Full:
            if self.logger is not None:
                self.logger.warning(
                    f"Queue for {queue_name} is still full after trying to make space."
                )

    def run(self):
        self.logger = Logger(self.logging_config).get_logger()
        self.logger.info("CameraController process started.")

        cap = cv2.VideoCapture(0)  # 0はデフォルトのカメラ
        if not cap.isOpened():
            self.logger.error("Failed to open camera.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        cap.set(cv2.CAP_PROP_FPS, self.config.fps)

        # cap.read() がカメラのハードウェアFPSでブロックするため、
        # こちら側では追加の待機を行わずフレームレートに追従する
        while not self.stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                self.logger.warning("Failed to grab frame.")
                time.sleep(0.1)
                continue

            timestamp = time.time()
            frame_data = FrameData(
                frame_id=self.frame_id, timestamp=timestamp, image=frame
            )

            # 両方のキューにフレームを入れる
            self._put_frame_to_queue(
                self.tracking_frame_queue, frame_data, self.tracking_frame_queue_name
            )
            self._put_frame_to_queue(
                self.gui_frame_queue, frame_data, self.gui_frame_queue_name
            )

            self.frame_id += 1

            self.logger.debug(
                f"Frame {self.frame_id} captured and put into queues: "
                f"{self.tracking_frame_queue_name}, {self.gui_frame_queue_name}"
            )

        cap.release()
        self.logger.info("CameraController process stopped.")
