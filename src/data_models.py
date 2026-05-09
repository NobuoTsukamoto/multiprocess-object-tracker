"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

from dataclasses import dataclass
from typing import Any, List
import numpy as np


@dataclass
class FrameData:
    frame_id: int
    timestamp: float
    image: np.ndarray


@dataclass
class FrameRef:
    """Lightweight reference to a frame stored in a SharedFramePool slot."""

    frame_id: int
    timestamp: float
    slot: int


@dataclass
class DetectionResult:
    boxes: List[List[float]]
    scores: List[float]
    class_ids: List[int]


@dataclass
class TrackInfo:
    track_id: int
    class_id: int
    box: List[float]
    score: float


@dataclass
class TrackingResult:
    """Tracking output paired with the frame_id it was computed for."""

    frame_id: int
    timestamp: float
    track_infos: List[TrackInfo]
    detections: Any  # supervision.Detections
    process_time_ms: float
