"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass
class FrameData:
    frame_id: int
    timestamp: float
    image: np.ndarray


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
