"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

from dataclasses import dataclass
from typing import Any, List


@dataclass
class FrameRef:
    """Lightweight reference to a frame stored in a SharedFramePool slot."""

    frame_id: int
    timestamp: float
    slot: int


@dataclass
class TrackInfo:
    track_id: int
    class_id: int


@dataclass
class TrackingResult:
    """Tracking output paired with the frame_id it was computed for."""

    frame_id: int
    timestamp: float
    track_infos: List[TrackInfo]
    detections: Any  # supervision.Detections
    process_time_ms: float
    queue_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class WorkerError:
    """Fatal error reported by a worker process to the GUI (main) process.

    Sent on a dedicated status queue so the GUI can distinguish an error
    exit from a normal (stop_event-driven) exit and surface the reason.
    """

    source: str  # "camera" | "tracking"
    message: str
    timestamp: float
