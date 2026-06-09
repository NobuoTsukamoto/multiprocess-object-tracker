"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Union
import yaml


@dataclass
class CameraConfig:
    # source: int=デバイスインデックス / 数字文字列=int 化 / それ以外の文字列=パス/URL。
    source: Union[int, str] = 0
    fps: int = 30
    width: int = 1280
    height: int = 720
    max_queue_length: int = 10


@dataclass
class DetectionConfig:
    model_path: str = "models/yolox_s.onnx"
    providers: List[str] = field(default_factory=lambda: ["CPUExecutionProvider"])
    score_threshold: float = 0.5  # ByteTrack の track_activation_threshold（検出フィルタではない）
    detection_threshold: float = 0.1  # 生検出 confidence の下限フィルタ
    nms_iou_threshold: float = 0.45  # NMS の IoU しきい値
    class_names: List[str] = field(default_factory=list)


@dataclass
class TrackingConfig:
    class_id: List[int] = field(default_factory=lambda: [0])
    max_lost: int = 30
    min_box_area: int = 100
    iou_threshold: float = 0.5
    frame_read_policy: str = "bounded_latest"
    max_frame_skip: int = 2


@dataclass
class GuiConfig:
    window_width: int = 1600
    window_height: int = 900
    window_x: int = 100
    window_y: int = 100
    display_image_width: int = 1280
    display_image_height: int = 720
    frame_buffer_seconds: float = 2.0


@dataclass
class LoggingConfig:
    level: str = "INFO"
    output: str = "console"
    performance_interval: int = 100


@dataclass
class AppConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class EmptyConfigError(ValueError):
    """Raised when the configuration file is empty (YAML parses to None)."""


class ConfigManager:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str) -> AppConfig:
        # Always read as UTF-8 so non-ASCII content (comments, paths, class
        # names) loads regardless of the platform default encoding (e.g.
        # cp932 on Japanese Windows).
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)
        if config_dict is None:
            raise EmptyConfigError(f"Configuration file is empty: {config_path}")
        return self._create_app_config(config_dict)

    def _create_app_config(self, config_dict: Dict[str, Any]) -> AppConfig:
        return AppConfig(
            camera=CameraConfig(**config_dict.get("camera", {})),
            detection=DetectionConfig(**config_dict.get("detection", {})),
            tracking=TrackingConfig(**config_dict.get("tracking", {})),
            gui=GuiConfig(**config_dict.get("gui", {})),
            logging=LoggingConfig(**config_dict.get("logging", {})),
        )

    def get_config(self, name: str) -> Any:
        return getattr(self.config, name)
