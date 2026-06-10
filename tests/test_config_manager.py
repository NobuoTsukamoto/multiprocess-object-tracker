import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config_manager import ConfigManager, EmptyConfigError


class ConfigManagerTest(unittest.TestCase):
    def test_empty_file_raises_empty_config_error(self):
        # An empty YAML file parses to None; ConfigManager should raise a
        # dedicated EmptyConfigError instead of an opaque AttributeError.
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("")
            path = f.name
        try:
            with self.assertRaises(EmptyConfigError):
                ConfigManager(path)
        finally:
            Path(path).unlink()

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            ConfigManager("definitely_missing_config_file.yaml")

    def test_loads_default_yaml(self):
        default_path = (
            Path(__file__).resolve().parents[1] / "config" / "default.yaml"
        )

        manager = ConfigManager(str(default_path))

        self.assertEqual(manager.get_config("camera").source, 0)

    def test_missing_sections_built_with_defaults(self):
        # R-CM-04: sections absent from the YAML are constructed entirely
        # from dataclass defaults; present sections keep their values.
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("camera:\n  fps: 5\n")
            path = f.name
        try:
            manager = ConfigManager(path)
            self.assertEqual(manager.get_config("camera").fps, 5)
            self.assertEqual(manager.get_config("tracking").max_lost, 30)
            self.assertEqual(manager.get_config("logging").level, "INFO")
        finally:
            Path(path).unlink()

    def test_get_config_returns_section_dataclass(self):
        # R-CM-05: get_config(name) returns the dataclass for that section.
        from config_manager import CameraConfig, GuiConfig

        default_path = (
            Path(__file__).resolve().parents[1] / "config" / "default.yaml"
        )

        manager = ConfigManager(str(default_path))

        self.assertIsInstance(manager.get_config("camera"), CameraConfig)
        self.assertIsInstance(manager.get_config("gui"), GuiConfig)

    def test_unknown_key_raises_type_error(self):
        # R-CM-07: keys not defined on the section dataclass are rejected
        # via the ** expansion (unexpected keyword argument).
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("camera:\n  no_such_key: 1\n")
            path = f.name
        try:
            with self.assertRaises(TypeError):
                ConfigManager(path)
        finally:
            Path(path).unlink()

    def test_unknown_section_name_raises_attribute_error(self):
        # R-CM-08: get_config with a name not on AppConfig raises via getattr.
        default_path = (
            Path(__file__).resolve().parents[1] / "config" / "default.yaml"
        )

        manager = ConfigManager(str(default_path))

        with self.assertRaises(AttributeError):
            manager.get_config("no_such_section")

    def test_non_utf8_file_raises_unicode_decode_error(self):
        # R-CM-11: the file is read as UTF-8 regardless of the platform
        # default encoding, so cp932-encoded content fails loudly.
        with tempfile.NamedTemporaryFile("wb", suffix=".yaml", delete=False) as f:
            f.write("logging:\n  level: INFO  # コメント\n".encode("cp932"))
            path = f.name
        try:
            with self.assertRaises(UnicodeDecodeError):
                ConfigManager(path)
        finally:
            Path(path).unlink()

    def test_detection_threshold_keys_have_defaults(self):
        from config_manager import DetectionConfig

        detection = DetectionConfig()

        self.assertEqual(detection.detection_threshold, 0.1)
        self.assertEqual(detection.nms_iou_threshold, 0.45)

    def test_removed_keys_are_rejected(self):
        # detection.fp16 / tracking.max_track_num are deleted from the schema;
        # passing them must fail loudly (unknown keys raise TypeError, R-CM-07).
        from config_manager import DetectionConfig, TrackingConfig

        with self.assertRaises(TypeError):
            DetectionConfig(fp16=False)
        with self.assertRaises(TypeError):
            TrackingConfig(max_track_num=10)


if __name__ == "__main__":
    unittest.main()
