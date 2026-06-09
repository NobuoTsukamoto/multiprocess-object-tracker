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


if __name__ == "__main__":
    unittest.main()
