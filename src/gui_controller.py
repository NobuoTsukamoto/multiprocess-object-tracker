"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import math
import multiprocessing
import time
import tkinter as tk
from collections import OrderedDict, deque
from queue import Empty
from tkinter import ttk

import cv2
import supervision as sv
from PIL import Image, ImageTk

from camera_controller import CameraController
from config_manager import ConfigManager
from data_models import TrackingResult
from logger import Logger
from object_tracking_controller import ObjectTrackingController
from shared_frame_pool import SharedFrameAccessor, SharedFramePool


class GUIController:
    @staticmethod
    def _calculate_frame_buffer_max(
        fps: int, frame_buffer_seconds: float, minimum: int
    ) -> int:
        buffered_frames = math.ceil(max(0, fps) * max(0.0, frame_buffer_seconds))
        return max(minimum, buffered_frames)

    def __init__(self, config_manager: ConfigManager, logger: Logger):
        self.config_manager = config_manager
        self.logger = logger.get_logger()
        self.gui_config = self.config_manager.get_config("gui")
        self.camera_config = self.config_manager.get_config("camera")

        self.root = tk.Tk()
        self.root.title("Object Detection and Tracking")
        self.root.geometry(
            f"{self.gui_config.window_width}x{self.gui_config.window_height}+"
            f"{self.gui_config.window_x}+{self.gui_config.window_y}"
        )

        # Process management
        self.stop_event = multiprocessing.Event()
        max_queue_size = self.camera_config.max_queue_length

        # Shared-memory pools. Slot count is queue size + 2 so the
        # consumer always has a spare slot in flight.
        frame_shape = (self.camera_config.height, self.camera_config.width, 3)
        n_slots = max_queue_size + 2

        self.tracking_data_queue: multiprocessing.Queue = multiprocessing.Queue(
            maxsize=max_queue_size
        )
        self.gui_data_queue: multiprocessing.Queue = multiprocessing.Queue(
            maxsize=max_queue_size
        )
        self.track_queue: multiprocessing.Queue = multiprocessing.Queue(
            maxsize=max_queue_size
        )

        self.tracking_pool = SharedFramePool(
            n_slots=n_slots,
            shape=frame_shape,
            dtype="uint8",
            data_queue=self.tracking_data_queue,
        )
        self.gui_pool = SharedFramePool(
            n_slots=n_slots,
            shape=frame_shape,
            dtype="uint8",
            data_queue=self.gui_data_queue,
        )

        # Reader handle for the GUI (main) process
        self.gui_pool_reader = SharedFrameAccessor(self.gui_pool.spec)

        self.camera_process = None
        self.tracking_process = None

        # Performance stats
        self.frame_times = deque(maxlen=100)
        self.last_process_time_ms = 0.0

        # Recent frames keyed by frame_id, for synchronized overlay.
        self._frame_buffer: "OrderedDict[int, any]" = OrderedDict()
        self._frame_buffer_max = self._calculate_frame_buffer_max(
            fps=self.camera_config.fps,
            frame_buffer_seconds=self.gui_config.frame_buffer_seconds,
            minimum=max_queue_size + 2,
        )
        self._latest_track: TrackingResult = None
        self._overlay_miss_count = 0
        self._last_overlay_miss_frame_id = None

        # Supervision Annotators
        self.box_annotator = sv.BoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        right_frame = ttk.Frame(main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)

        left_frame = ttk.Frame(main_frame, width=self.gui_config.display_image_width)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        left_frame.pack_propagate(False)

        self.image_label = tk.Label(left_frame, anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)

        control_frame = ttk.LabelFrame(right_frame, text="Controls")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        self.start_button = ttk.Button(
            control_frame, text="Start Tracking", command=self.start_tracking
        )
        self.start_button.pack(fill=tk.X, padx=5, pady=5)
        self.stop_button = ttk.Button(
            control_frame,
            text="Stop Tracking",
            command=self.stop_tracking,
            state=tk.DISABLED,
        )
        self.stop_button.pack(fill=tk.X, padx=5, pady=5)

        perf_frame = ttk.LabelFrame(right_frame, text="Performance")
        perf_frame.pack(fill=tk.X, pady=10)
        self.perf_label = ttk.Label(perf_frame, text="-- ms, -- FPS")
        self.perf_label.pack(padx=5, pady=5)

        track_frame = ttk.LabelFrame(right_frame, text="Tracked Objects")
        track_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.track_list = tk.Listbox(track_frame)
        self.track_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def start_tracking(self):
        self.logger.info("Starting tracking processes...")

        # Recover any slots left dangling from a previous run.
        self.tracking_pool.reset_free_slots()
        self.gui_pool.reset_free_slots()
        self._frame_buffer.clear()
        self._latest_track = None
        self.stop_event.clear()

        logging_config = self.config_manager.get_config("logging")

        self.camera_process = CameraController(
            self.config_manager,
            logging_config,
            self.tracking_pool.spec,
            self.gui_pool.spec,
            self.stop_event,
        )
        self.tracking_process = ObjectTrackingController(
            self.config_manager,
            logging_config,
            self.tracking_pool.spec,
            self.track_queue,
            self.stop_event,
        )

        self.tracking_pool.mark_active()
        self.gui_pool.mark_active()
        try:
            self.camera_process.start()
            self.tracking_process.start()
        except Exception:
            self.stop_event.set()
            self._terminate_process_if_alive(self.camera_process, "CameraController")
            self._terminate_process_if_alive(
                self.tracking_process, "ObjectTrackingController"
            )
            self.tracking_pool.mark_inactive()
            self.gui_pool.mark_inactive()
            raise

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self._update_gui()

    def stop_tracking(self):
        self.logger.info("Stopping tracking processes...")
        self.stop_event.set()

        camera_stopped = self._stop_process(self.camera_process, "CameraController")
        tracking_stopped = self._stop_process(
            self.tracking_process, "ObjectTrackingController"
        )
        if camera_stopped and tracking_stopped:
            self.tracking_pool.mark_inactive()
            self.gui_pool.mark_inactive()
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
        else:
            self.logger.error(
                "Some worker processes are still alive; shared frame pools remain "
                "active and cannot be reset safely."
            )
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

    def _stop_process(self, process, process_name: str) -> bool:
        if process is None:
            return True

        process.join(timeout=5)
        if process.is_alive():
            self.logger.warning(
                f"{process_name} did not terminate gracefully. Terminating."
            )
            self._terminate_process_if_alive(process, process_name)

        return not process.is_alive()

    def _terminate_process_if_alive(self, process, process_name: str):
        if process is None or not process.is_alive():
            return

        process.terminate()
        process.join(timeout=2)
        if process.is_alive():
            self.logger.error(
                f"{process_name} is still alive after terminate(); killing."
            )
            process.kill()
            process.join(timeout=2)
            if process.is_alive():
                self.logger.error(f"{process_name} is still alive after kill().")
    def _workers_alive(self) -> bool:
        return any(
            process is not None and process.is_alive()
            for process in (self.camera_process, self.tracking_process)
        )

    def _drain_frames(self):
        """Pull every available frame out of the GUI pool and buffer it."""
        while True:
            try:
                ref, image = self.gui_pool_reader.read_nowait()
            except Empty:
                break
            self._frame_buffer[ref.frame_id] = image
            self.frame_times.append(time.time())
            # Trim oldest if over capacity.
            while len(self._frame_buffer) > self._frame_buffer_max:
                self._frame_buffer.popitem(last=False)

    def _drain_track_results(self):
        """Keep only the most recent tracking result."""
        latest = self._latest_track
        while True:
            try:
                latest = self.track_queue.get_nowait()
            except Empty:
                break
        if latest is not self._latest_track:
            self._latest_track = latest
            self.last_process_time_ms = latest.process_time_ms

            # Update Listbox with the new tracking results.
            self.track_list.delete(0, tk.END)
            class_names = self.config_manager.get_config("detection").class_names
            for i, track in enumerate(latest.track_infos):
                if i >= 10:
                    self.track_list.insert(tk.END, "...")
                    break
                self.track_list.insert(
                    tk.END,
                    f"ID: {track.track_id}, Class: {class_names[track.class_id]}",
                )

    def _select_display_frame(self):
        """Pick the frame to display.

        Priority: the frame matching the latest tracking result so the
        overlay is drawn on the correct image. If unavailable, show
        the newest buffered frame without an overlay.
        Returns (image, detections_or_None).
        """
        if not self._frame_buffer:
            return None, None

        # Try matched frame first.
        if self._latest_track is not None:
            fid = self._latest_track.frame_id
            if fid in self._frame_buffer:
                # Drop any frames older than the matched one to free memory.
                while self._frame_buffer and next(iter(self._frame_buffer)) < fid:
                    self._frame_buffer.popitem(last=False)
                return self._frame_buffer[fid], self._latest_track.detections
            self._record_overlay_miss_if_stale(fid)

        # Fall back to newest frame, no overlay.
        newest_fid = next(reversed(self._frame_buffer))
        return self._frame_buffer[newest_fid], None

    def _record_overlay_miss_if_stale(self, track_frame_id: int):
        """Log once when a tracking result is older than the GUI frame buffer."""
        if not self._frame_buffer:
            return

        oldest_fid = next(iter(self._frame_buffer))
        if track_frame_id >= oldest_fid:
            return

        if self._last_overlay_miss_frame_id == track_frame_id:
            return

        newest_fid = next(reversed(self._frame_buffer))
        self._overlay_miss_count += 1
        self._last_overlay_miss_frame_id = track_frame_id
        self.logger.warning(
            "Overlay miss: "
            f"track_frame_id={track_frame_id}, "
            f"oldest_buffered_frame_id={oldest_fid}, "
            f"newest_buffered_frame_id={newest_fid}, "
            f"buffer_size={len(self._frame_buffer)}, "
            f"buffer_limit={self._frame_buffer_max}, "
            f"miss_count={self._overlay_miss_count}"
        )

    def _update_gui(self):
        self._drain_frames()
        self._drain_track_results()

        image, detections = self._select_display_frame()
        if image is not None:
            img = image
            if detections is not None and len(detections) > 0:
                class_names = self.config_manager.get_config("detection").class_names
                labels = [
                    f"ID:{tracker_id} {class_names[class_id]} ({confidence:.2f})"
                    for confidence, class_id, tracker_id in zip(
                        detections.confidence,
                        detections.class_id,
                        detections.tracker_id,
                    )
                ]
                img = self.box_annotator.annotate(scene=img.copy(), detections=detections)
                img = self.label_annotator.annotate(
                    scene=img, detections=detections, labels=labels
                )

            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(
                img,
                (
                    self.gui_config.display_image_width,
                    self.gui_config.display_image_height,
                ),
            )
            img = Image.fromarray(img)
            img_tk = ImageTk.PhotoImage(image=img)
            self._imgtk = img_tk  # keep a reference
            self.image_label.config(image=img_tk)

        # Performance: show the actual inference latency reported by
        # the tracking process plus the camera-to-GUI FPS.
        if len(self.frame_times) > 1:
            elapsed = self.frame_times[-1] - self.frame_times[0]
            avg_fps = len(self.frame_times) / elapsed if elapsed > 0 else 0
            self.perf_label.config(
                text=f"{self.last_process_time_ms:.2f} ms, {avg_fps:.2f} FPS"
            )

        if not self.stop_event.is_set():
            self.root.after(5, self._update_gui)

    def on_closing(self):
        if self._workers_alive():
            self.stop_tracking()
        # Release shared memory.
        try:
            self.gui_pool_reader.close()
        except Exception:
            pass

        if self._workers_alive():
            self.logger.error(
                "Skipping shared memory cleanup because worker processes are "
                "still alive."
            )
        else:
            self.tracking_pool.mark_inactive()
            self.gui_pool.mark_inactive()
            self.tracking_pool.cleanup()
            self.gui_pool.cleanup()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
