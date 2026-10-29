"""Bundled-resource and per-user path tests."""

from __future__ import annotations

from pathlib import Path

from app.core import paths


def test_resource_root_contains_data_and_assets() -> None:
    root = paths.resource_root()
    assert (root / "main.py").is_file()
    assert paths.data_path("holidays", "holidays.json").is_file()
    assert paths.assets_path("icons", "app.png").is_file()
    assert paths.assets_path("fonts", "Vazirmatn-Regular.ttf").is_file()


def test_config_override_creates_directory(tmp_path: Path, monkeypatch) -> None:
    override = tmp_path / "custom-config"
    monkeypatch.setenv("PCW_CONFIG_DIR", str(override))
    assert paths.config_dir() == override
    assert override.is_dir()
    assert paths.config_file() == override / "settings.ini"
    assert paths.log_file() == override / "error.log"


def test_appdata_is_used_without_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PCW_CONFIG_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.config_dir() == tmp_path / "PersianCalendarWidget"
    assert paths.config_file("x.ini") == tmp_path / "PersianCalendarWidget" / "x.ini"
