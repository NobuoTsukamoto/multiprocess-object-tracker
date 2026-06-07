from pathlib import Path

import pytest

from config_manager import ConfigManager


def _write_config(tmp_path: Path, text: str) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_config_manager_uses_defaults_for_missing_sections(tmp_path):
    manager = ConfigManager(
        _write_config(
            tmp_path,
            """
camera:
  fps: 60
tracking:
  frame_read_policy: latest
""",
        )
    )

    assert manager.get_config("camera").fps == 60
    assert manager.get_config("camera").width == 1280
    assert manager.get_config("tracking").frame_read_policy == "latest"
    assert manager.get_config("gui").frame_buffer_seconds == 2.0
    assert manager.get_config("logging").level == "INFO"


def test_config_manager_treats_empty_yaml_as_default_config(tmp_path):
    manager = ConfigManager(_write_config(tmp_path, ""))

    assert manager.get_config("camera").fps == 30
    assert manager.get_config("detection").providers == ["CPUExecutionProvider"]
    assert manager.get_config("tracking").max_frame_skip == 2


def test_get_config_raises_for_unknown_section(tmp_path):
    manager = ConfigManager(_write_config(tmp_path, "camera: {}"))

    with pytest.raises(AttributeError):
        manager.get_config("does_not_exist")
