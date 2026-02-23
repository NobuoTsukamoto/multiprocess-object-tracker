"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import tkinter as tk
from tkinter import ttk
import multiprocessing
from queue import Empty
from collections import deque
import time

from PIL import Image, ImageTk
import cv2
import numpy as np
import supervision as sv

from config_manager import ConfigManager
from logger import Logger
from camera_controller import CameraController
from object_tracking_controller import ObjectTrackingController


class GUIController:
    def __init__(self, config_manager: ConfigManager, logger: Logger):
        self.config_manager = config_manager
        self.logger = logger.get_logger()
        self.gui_config = self.config_manager.get_config("gui")

        self.root = tk.Tk()
        self.root.title("Object Detection and Tracking")
        self.root.geometry(
            f"{self.gui_config.window_width}x{self.gui_config.window_height}+"
            f"{self.gui_config.window_x}+{self.gui_config.window_y}"
        )

        # Process management
        self.stop_event = multiprocessing.Event()
        max_queue_size = self.config_manager.get_config("camera").max_queue_length
        self.tracking_frame_queue = multiprocessing.Queue(maxsize=max_queue_size)
        self.gui_frame_queue = multiprocessing.Queue(maxsize=max_queue_size)
        self.track_queue = multiprocessing.Queue()
        self.camera_process = None
        self.tracking_process = None

        # Performance stats
        self.frame_times = deque(maxlen=100)

        # Tracking results
        self.last_track_results = []
        self.last_tracked_detections = None

        # Supervision Annotators
        self.box_annotator = sv.BoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Right: Controls and Info (Pack this first to secure its space)
        right_frame = ttk.Frame(main_frame, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)

        # Left: Camera Feed
        left_frame = ttk.Frame(main_frame, width=self.gui_config.display_image_width)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        left_frame.pack_propagate(False)
        
        self.image_label = tk.Label(left_frame, anchor=tk.CENTER)
        self.image_label.pack(fill=tk.BOTH, expand=True)

        # Controls (inside right_frame)
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

        # Performance
        perf_frame = ttk.LabelFrame(right_frame, text="Performance")
        perf_frame.pack(fill=tk.X, pady=10)
        self.perf_label = ttk.Label(perf_frame, text="-- ms, -- FPS")
        self.perf_label.pack(padx=5, pady=5)

        # Track List
        track_frame = ttk.LabelFrame(right_frame, text="Tracked Objects")
        track_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.track_list = tk.Listbox(track_frame)
        self.track_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def start_tracking(self):
        self.logger.info("Starting tracking processes...")
        self.stop_event.clear()

        logging_config = self.config_manager.get_config("logging")

        self.camera_process = CameraController(
            self.config_manager,
            logging_config,
            self.tracking_frame_queue,
            self.gui_frame_queue,
            self.stop_event,
        )
        self.tracking_process = ObjectTrackingController(
            self.config_manager,
            logging_config,
            self.tracking_frame_queue,
            self.track_queue,
            self.stop_event,
        )

        self.camera_process.start()
        self.tracking_process.start()

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self._update_gui()

    def stop_tracking(self):
        self.logger.info("Stopping tracking processes...")
        self.stop_event.set()

        if self.camera_process:
            self.camera_process.join(timeout=5)
            if self.camera_process.is_alive():
                self.logger.warning(
                    "CameraController did not terminate gracefully. Terminating."
                )
                self.camera_process.terminate()
        if self.tracking_process:
            self.tracking_process.join(timeout=5)
            if self.tracking_process.is_alive():
                self.logger.warning(
                    "ObjectTrackingController did not terminate gracefully. Terminating."
                )
                self.tracking_process.terminate()

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def _update_gui(self):
        self.logger.debug("IN: _update_gui")

        try:
            # Get the latest frame
            frame_data = self.gui_frame_queue.get_nowait()
            self.last_frame_time = time.time()
            self.frame_times.append(self.last_frame_time)
            img = frame_data.image

            # Get the latest tracking results
            if not self.track_queue.empty():
                self.last_track_results, self.last_tracked_detections = self.track_queue.get_nowait()

                # Update Listbox
                self.track_list.delete(0, tk.END)
                class_names = self.config_manager.get_config("detection").class_names
                for i, track in enumerate(self.last_track_results):
                    if i >= 10:
                        self.track_list.insert(tk.END, "...")
                        break
                    self.track_list.insert(
                        tk.END, f"ID: {track.track_id}, Class: {class_names[track.class_id]}"
                    )

            # Draw bounding boxes if there are tracking results
            if self.last_tracked_detections is not None:
                class_names = self.config_manager.get_config("detection").class_names
                # Draw using supervision
                labels = [
                    f"ID:{tracker_id} {class_names[class_id]} ({confidence:.2f})"
                    for confidence, class_id, tracker_id
                    in zip(self.last_tracked_detections.confidence, self.last_tracked_detections.class_id, self.last_tracked_detections.tracker_id)
                ]
                img = self.box_annotator.annotate(scene=img, detections=self.last_tracked_detections)
                img = self.label_annotator.annotate(scene=img, detections=self.last_tracked_detections, labels=labels)

            # Convert image for display
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
            self._imgtk = img_tk  # Keep a reference to avoid garbage collection
            self.image_label.config(image=img_tk)

        except Empty:
            pass  # Queues might be empty, which is fine

        # Update performance stats
        if len(self.frame_times) > 1:
            elapsed = self.frame_times[-1] - self.frame_times[0]
            avg_fps = len(self.frame_times) / elapsed if elapsed > 0 else 0
            # Calculate processing time based on the last frame time
            process_time = (
                (time.time() - self.last_frame_time) * 1000
                if hasattr(self, "last_frame_time")
                else 0
            )
            self.perf_label.config(text=f"{process_time:.2f} ms, {avg_fps:.2f} FPS")

        if not self.stop_event.is_set():
            self.root.after(5, self._update_gui)  # ~60 FPS

        self.logger.debug("OUT: _update_gui")

    def on_closing(self):
        if self.camera_process and self.camera_process.is_alive():
            self.stop_tracking()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
