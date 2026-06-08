"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import ctypes
import math
import multiprocessing
import platform
import time
import tkinter as tk
import tkinter.font as tkfont
from collections import OrderedDict, deque
from queue import Empty
from tkinter import ttk

import cv2
import supervision as sv
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageTk

from camera_controller import CameraController
from config_manager import ConfigManager
from data_models import TrackingResult
from logger import Logger
from object_tracking_controller import ObjectTrackingController
from shared_frame_pool import SharedFrameAccessor, SharedFramePool


class GUIController:
    STATUS_COLORS = {
        "実行中": "#16A34A",
        "待機中": "#475569",
        "停止処理中": "#D97706",
        "停止中": "#374151",
        "停止失敗": "#DC2626",
        "エラー": "#B91C1C",
    }

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
        self.root.title("物体検出・追跡")
        self._set_window_icon()
        self.root.geometry(
            f"{self.gui_config.window_width}x{self.gui_config.window_height}+"
            f"{self.gui_config.window_x}+{self.gui_config.window_y}"
        )
        self._configure_borderless_maximized()

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
        # Status channel for fatal worker errors (camera open / model load).
        # Unbounded: errors are rare and must never be dropped.
        self.error_queue: multiprocessing.Queue = multiprocessing.Queue()

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
        self.camera_frame_times = deque(maxlen=100)
        self.tracking_result_times = deque(maxlen=100)
        self.display_times = deque(maxlen=100)
        self.last_process_time_ms = 0.0
        self.last_detection_queue_latency_ms = 0.0
        self.last_detection_total_latency_ms = 0.0
        self.last_camera_latency_ms = 0.0
        self.last_display_latency_ms = 0.0

        # Recent frames keyed by frame_id, for synchronized overlay.
        self._frame_buffer: "OrderedDict[int, any]" = OrderedDict()
        self._frame_timestamps: "OrderedDict[int, float]" = OrderedDict()
        self._frame_buffer_max = self._calculate_frame_buffer_max(
            fps=self.camera_config.fps,
            frame_buffer_seconds=self.gui_config.frame_buffer_seconds,
            minimum=max_queue_size + 2,
        )
        self._latest_track: TrackingResult = None
        self._last_display_frame_id = None
        self._last_render_key = None
        self._last_display_image = None
        self._last_display_detections = None
        self._overlay_miss_count = 0
        self._last_overlay_miss_frame_id = None
        self._run_started_at = None
        self._first_frame_logged = False
        self._worker_error = None

        # Supervision Annotators
        self.box_annotator = sv.BoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()

        self._create_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    @staticmethod
    def _calculate_rate(timestamps) -> float:
        if len(timestamps) < 2:
            return 0.0
        elapsed = timestamps[-1] - timestamps[0]
        return (len(timestamps) - 1) / elapsed if elapsed > 0 else 0.0

    def _configure_borderless_maximized(self):
        try:
            self.root.overrideredirect(True)
        except tk.TclError:
            pass

        # overrideredirect removes the title bar, so the window manager no
        # longer delivers a close affordance (and WM_DELETE_WINDOW/Alt+F4 do
        # not fire reliably). Bind keyboard fallbacks so the user is never
        # stuck with a window that can only be closed via Task Manager.
        self.root.bind("<Escape>", lambda event: self.on_closing())
        self.root.bind("<Alt-F4>", lambda event: self.on_closing())

        x, y, width, height = self._get_work_area_geometry()
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _get_work_area_geometry(self):
        if platform.system() == "Windows":
            try:
                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long),
                    ]

                rect = RECT()
                success = ctypes.windll.user32.SystemParametersInfoW(
                    0x0030, 0, ctypes.byref(rect), 0
                )
                if success:
                    return (
                        rect.left,
                        rect.top,
                        rect.right - rect.left,
                        rect.bottom - rect.top,
                    )
            except Exception:
                pass

        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def _set_window_icon(self):
        icon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)

        draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill="#111827")
        draw.rounded_rectangle((12, 20, 52, 44), radius=6, fill="#2563EB")
        draw.rectangle((18, 14, 34, 20), fill="#2563EB")
        draw.ellipse((25, 17, 47, 39), fill="#0F172A", outline="#E5E7EB", width=3)
        draw.ellipse((32, 24, 40, 32), fill="#22C55E")
        draw.line((48, 12, 48, 24), fill="#22C55E", width=3)
        draw.line((42, 18, 54, 18), fill="#22C55E", width=3)
        draw.rectangle((14, 47, 50, 51), fill="#22C55E")

        self._window_icon = ImageTk.PhotoImage(icon)
        self.root.iconphoto(True, self._window_icon)

    def _create_widgets(self):
        style = ttk.Style(self.root)
        style.configure("Large.TButton", font=("TkDefaultFont", 12), padding=(12, 10))
        fixed_font = tkfont.nametofont("TkFixedFont")

        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        right_frame = ttk.Frame(main_frame, width=360)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)

        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.image_area = tk.Frame(left_frame, bg="#20242c")
        self.image_area.pack(fill=tk.BOTH, expand=True)
        self.image_label = tk.Label(self.image_area, anchor=tk.CENTER, bg="#20242c")
        self.image_label.pack(fill=tk.BOTH, expand=True)
        self.video_status_label = tk.Label(
            self.image_area,
            text="待機中",
            font=("TkDefaultFont", 24, "bold"),
            fg="#ffffff",
            bg="#333842",
            padx=24,
            pady=12,
        )
        self.video_status_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        control_frame = ttk.LabelFrame(right_frame, text="操作")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        self.status_label = tk.Label(
            control_frame,
            text="状態: 待機中",
            anchor=tk.W,
            font=("TkDefaultFont", 12, "bold"),
            fg="#ffffff",
            bg=self.STATUS_COLORS["待機中"],
            padx=10,
            pady=6,
        )
        self.status_label.pack(fill=tk.X, padx=5, pady=(8, 6))
        self.start_button = ttk.Button(
            control_frame,
            text="開始",
            command=self.start_tracking,
            style="Large.TButton",
        )
        self.start_button.pack(fill=tk.X, padx=5, pady=8)
        self.stop_button = ttk.Button(
            control_frame,
            text="停止",
            command=self.stop_tracking,
            state=tk.DISABLED,
            style="Large.TButton",
        )
        self.stop_button.pack(fill=tk.X, padx=5, pady=(0, 8))
        self.exit_button = ttk.Button(
            bottom_frame,
            text="終了",
            command=self.on_closing,
            style="Large.TButton",
        )
        self.exit_button.pack(fill=tk.X, padx=5, pady=(10, 0))

        perf_frame = ttk.LabelFrame(right_frame, text="性能")
        perf_frame.pack(fill=tk.X, pady=10)
        perf_table = ttk.Frame(perf_frame)
        perf_table.pack(fill=tk.X, padx=8, pady=8)

        headers = ["", "FPS", "待ち", "処理", "合計"]
        column_widths = [6, 7, 10, 9, 9]
        for col, text in enumerate(headers):
            label = ttk.Label(
                perf_table,
                text=text,
                width=column_widths[col],
                anchor=tk.E,
                font=fixed_font,
            )
            label.grid(row=0, column=col, sticky=tk.EW, padx=(0, 2), pady=(0, 4))

        self.perf_values = {}
        rows = [
            ("camera", "カメラ"),
            ("detection", "検出"),
            ("display", "表示"),
        ]
        for row, (key, title) in enumerate(rows, start=1):
            ttk.Label(
                perf_table,
                text=title,
                width=column_widths[0],
                anchor=tk.W,
                font=fixed_font,
            ).grid(
                row=row, column=0, sticky=tk.W, padx=(0, 2), pady=2
            )
            self.perf_values[key] = {}
            for col, metric in enumerate(("fps", "wait", "process", "total"), start=1):
                value_label = ttk.Label(
                    perf_table,
                    text="--",
                    width=column_widths[col],
                    anchor=tk.E,
                    font=fixed_font,
                )
                value_label.grid(
                    row=row, column=col, sticky=tk.EW, padx=(0, 2), pady=2
                )
                self.perf_values[key][metric] = value_label

        for col, width in enumerate((48, 54, 74, 68, 68)):
            perf_table.columnconfigure(col, minsize=width, weight=0)

        track_frame = ttk.LabelFrame(right_frame, text="追跡中の物体")
        track_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        self.track_list = tk.Listbox(track_frame)
        self.track_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _set_status(self, text: str, *, running: bool):
        color = self.STATUS_COLORS.get(text, self.STATUS_COLORS["待機中"])
        self.status_label.config(text=f"状態: {text}", bg=color, fg="#ffffff")
        if running:
            self.video_status_label.place_forget()
        else:
            self.video_status_label.config(text=text, bg=color, fg="#ffffff")
            self.video_status_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    @staticmethod
    def _drain_queue_nowait(queue: multiprocessing.Queue) -> int:
        drained = 0
        while True:
            try:
                queue.get_nowait()
            except Empty:
                return drained
            drained += 1

    def start_tracking(self):
        self.logger.info("Starting tracking processes...")

        # Recover any slots left dangling from a previous run.
        self.tracking_pool.reset_free_slots()
        self.gui_pool.reset_free_slots()
        drained_tracks = self._drain_queue_nowait(self.track_queue)
        if drained_tracks:
            self.logger.info(
                f"Drained {drained_tracks} stale tracking results before restart."
            )
        self._drain_queue_nowait(self.error_queue)
        self._worker_error = None
        self._frame_buffer.clear()
        self._frame_timestamps.clear()
        self._latest_track = None
        self._last_display_frame_id = None
        self._last_render_key = None
        self._last_display_image = None
        self._last_display_detections = None
        self.camera_frame_times.clear()
        self.tracking_result_times.clear()
        self.display_times.clear()
        self.last_process_time_ms = 0.0
        self.last_detection_queue_latency_ms = 0.0
        self.last_detection_total_latency_ms = 0.0
        self.last_camera_latency_ms = 0.0
        self.last_display_latency_ms = 0.0
        self._run_started_at = time.time()
        self._first_frame_logged = False
        self.stop_event.clear()

        logging_config = self.config_manager.get_config("logging")

        self.camera_process = CameraController(
            self.config_manager,
            logging_config,
            self.tracking_pool.spec,
            self.gui_pool.spec,
            self.stop_event,
            self.error_queue,
        )
        self.tracking_process = ObjectTrackingController(
            self.config_manager,
            logging_config,
            self.tracking_pool.spec,
            self.track_queue,
            self.stop_event,
            self.error_queue,
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
        self._set_status("実行中", running=True)
        self._update_gui()

    def stop_tracking(self):
        self.logger.info("Stopping tracking processes...")
        stop_started_at = time.time()
        self._set_status("停止処理中", running=False)
        self.root.update_idletasks()
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
            self._set_status("停止中", running=False)
            self._show_inactive_display("停止中")
            self.logger.info(
                f"Tracking processes stopped in {time.time() - stop_started_at:.3f}s."
            )
        else:
            self.logger.error(
                "Some worker processes are still alive; shared frame pools remain "
                "active and cannot be reset safely."
            )
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self._set_status("停止失敗", running=False)
            self.logger.warning(
                f"Stop attempt took {time.time() - stop_started_at:.3f}s."
            )

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

    def _drain_worker_errors(self):
        """Return the first worker error reported since the last check.

        Drains any remaining errors so the queue does not accumulate; the
        first error is treated as the root cause.
        """
        try:
            first = self.error_queue.get_nowait()
        except Empty:
            return None
        self._drain_queue_nowait(self.error_queue)
        return first

    def _handle_worker_error(self, error):
        """Stop everything and surface a worker's fatal error in the GUI."""
        self.logger.error(
            f"Worker '{error.source}' reported an error: {error.message}"
        )
        self._worker_error = error
        self.stop_event.set()

        camera_stopped = self._stop_process(self.camera_process, "CameraController")
        tracking_stopped = self._stop_process(
            self.tracking_process, "ObjectTrackingController"
        )
        if camera_stopped and tracking_stopped:
            self.tracking_pool.mark_inactive()
            self.gui_pool.mark_inactive()
        else:
            self.logger.error(
                "Some worker processes are still alive after an error; shared "
                "frame pools remain active and cannot be reset safely."
            )

        # Re-enable start so the user can retry after fixing the cause.
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self._set_status("エラー", running=False)
        self._show_inactive_display(f"エラー: {error.message}")

    def _drain_frames(self):
        """Pull every available frame out of the GUI pool and buffer it."""
        while True:
            try:
                ref, image = self.gui_pool_reader.read_nowait()
            except Empty:
                break
            self._frame_buffer[ref.frame_id] = image
            self._frame_timestamps[ref.frame_id] = ref.timestamp
            received_at = time.time()
            if not self._first_frame_logged and self._run_started_at is not None:
                self._first_frame_logged = True
                self.logger.info(
                    "First GUI frame after start: "
                    f"frame_id={ref.frame_id}, "
                    f"elapsed={received_at - self._run_started_at:.3f}s, "
                    f"camera_latency={(received_at - ref.timestamp) * 1000:.1f}ms"
                )
            self.camera_frame_times.append(ref.timestamp)
            self.last_camera_latency_ms = (received_at - ref.timestamp) * 1000
            # Trim oldest if over capacity.
            while len(self._frame_buffer) > self._frame_buffer_max:
                frame_id, _ = self._frame_buffer.popitem(last=False)
                self._frame_timestamps.pop(frame_id, None)

    def _drain_track_results(self):
        """Keep only the most recent tracking result."""
        latest = self._latest_track
        while True:
            try:
                latest = self.track_queue.get_nowait()
            except Empty:
                break
            self.tracking_result_times.append(time.time())
        if latest is not self._latest_track:
            self._latest_track = latest
            self.last_process_time_ms = latest.process_time_ms
            self.last_detection_queue_latency_ms = getattr(
                latest, "queue_latency_ms", 0.0
            )
            self.last_detection_total_latency_ms = getattr(
                latest, "total_latency_ms", 0.0
            )

            # Update Listbox with the new tracking results.
            self.track_list.delete(0, tk.END)
            class_names = self.config_manager.get_config("detection").class_names
            for i, track in enumerate(latest.track_infos):
                if i >= 10:
                    self.track_list.insert(tk.END, "...")
                    break
                self.track_list.insert(
                    tk.END,
                    f"ID: {track.track_id} / クラス: {class_names[track.class_id]}",
                )

    def _select_display_frame(self):
        """Pick the frame to display.

        Priority: the frame matching the latest tracking result so the
        overlay is drawn on the correct image. If unavailable, show
        the newest buffered frame without an overlay.
        Returns (image, detections_or_None).
        """
        if not self._frame_buffer:
            self._last_display_frame_id = None
            return None, None

        # Try matched frame first.
        if self._latest_track is not None:
            fid = self._latest_track.frame_id
            if fid in self._frame_buffer:
                # Drop any frames older than the matched one to free memory.
                while self._frame_buffer and next(iter(self._frame_buffer)) < fid:
                    old_fid, _ = self._frame_buffer.popitem(last=False)
                    self._frame_timestamps.pop(old_fid, None)
                self._last_display_frame_id = fid
                return self._frame_buffer[fid], self._latest_track.detections
            self._record_overlay_miss_if_stale(fid)

        # Fall back to newest frame, no overlay.
        newest_fid = next(reversed(self._frame_buffer))
        self._last_display_frame_id = newest_fid
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

    def _render_image(self, image, detections=None, *, inactive=False):
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
        img = Image.fromarray(img)

        if inactive:
            img = ImageOps.grayscale(img).convert("RGB")
            img = ImageEnhance.Brightness(img).enhance(0.45)

        area_width = max(1, self.image_label.winfo_width())
        area_height = max(1, self.image_label.winfo_height())
        if area_width <= 1 or area_height <= 1:
            area_width = self.gui_config.display_image_width
            area_height = self.gui_config.display_image_height

        scale = min(area_width / img.width, area_height / img.height)
        target_size = (
            max(1, int(img.width * scale)),
            max(1, int(img.height * scale)),
        )
        img = img.resize(target_size, Image.Resampling.LANCZOS)

        img_tk = ImageTk.PhotoImage(image=img)
        self._imgtk = img_tk  # keep a reference
        self.image_label.config(image=img_tk)

    def _show_inactive_display(self, status_text: str):
        self.video_status_label.config(text=status_text)
        self.video_status_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        if self._last_display_image is not None:
            self._render_image(
                self._last_display_image,
                self._last_display_detections,
                inactive=True,
            )

    def _update_performance_label(self):
        camera_fps = self._calculate_rate(self.camera_frame_times)
        detection_fps = self._calculate_rate(self.tracking_result_times)
        display_fps = self._calculate_rate(self.display_times)
        self.perf_values["camera"]["fps"].config(text=f"{camera_fps:.2f}")
        self.perf_values["camera"]["wait"].config(
            text=f"{self.last_camera_latency_ms:.1f} ms"
        )
        self.perf_values["camera"]["process"].config(text="-")
        self.perf_values["camera"]["total"].config(text="-")

        self.perf_values["detection"]["fps"].config(text=f"{detection_fps:.2f}")
        self.perf_values["detection"]["wait"].config(
            text=f"{self.last_detection_queue_latency_ms:.1f} ms"
        )
        self.perf_values["detection"]["process"].config(
            text=f"{self.last_process_time_ms:.1f} ms"
        )
        self.perf_values["detection"]["total"].config(
            text=f"{self.last_detection_total_latency_ms:.1f} ms"
        )

        self.perf_values["display"]["fps"].config(text=f"{display_fps:.2f}")
        self.perf_values["display"]["wait"].config(
            text=f"{self.last_display_latency_ms:.1f} ms"
        )
        self.perf_values["display"]["process"].config(text="-")
        self.perf_values["display"]["total"].config(text="-")

    def _update_gui(self):
        error = self._drain_worker_errors()
        if error is not None:
            self._handle_worker_error(error)
            return

        self._drain_frames()
        self._drain_track_results()

        image, detections = self._select_display_frame()
        if image is not None:
            track_frame_id = (
                self._latest_track.frame_id
                if detections is not None and self._latest_track is not None
                else None
            )
            render_key = (self._last_display_frame_id, track_frame_id)
            if render_key != self._last_render_key:
                self._render_image(image, detections)
                self._last_render_key = render_key
                self._last_display_image = image.copy()
                self._last_display_detections = detections
                rendered_at = time.time()
                self.display_times.append(rendered_at)
                frame_timestamp = self._frame_timestamps.get(self._last_display_frame_id)
                if frame_timestamp is not None:
                    self.last_display_latency_ms = (
                        rendered_at - frame_timestamp
                    ) * 1000

        self._update_performance_label()

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
