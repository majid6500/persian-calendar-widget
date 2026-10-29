"""Settings validation and per-user persistence tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from app.core.paths import config_dir, config_file
from app.storage.settings import (
    DEFAULTS,
    DEFAULT_ACCENT,
    SettingsStore,
    SettingsValues,
    clamp_int,
    coerce_bool,
    normalize_accent,
)


def test_normalize_accent() -> None:
    assert normalize_accent("#AABBCC") == "#aabbcc"
    assert normalize_accent("AABBCC") == "#aabbcc"
    assert normalize_accent("  #aabbcc  ") == "#aabbcc"
    assert normalize_accent("not-a-color") == DEFAULT_ACCENT.lower()
    assert normalize_accent(None) == DEFAULT_ACCENT.lower()
    assert normalize_accent("bad", fallback="#123456") == "#123456"


def test_clamp_int_and_coerce_bool() -> None:
    assert clamp_int("80", 60, 100, 94) == 80
    assert clamp_int(5, 60, 100, 94) == 60
    assert clamp_int(999, 60, 100, 94) == 100
    assert clamp_int("abc", 60, 100, 94) == 94
    assert clamp_int(None, 60, 100, 94) == 94

    assert coerce_bool(True) is True
    assert coerce_bool(False) is False
    assert coerce_bool("yes") is True
    assert coerce_bool("OFF") is False
    assert coerce_bool("1") is True
    assert coerce_bool("0") is False
    assert coerce_bool(None, True) is True
    assert coerce_bool("unexpected", False) is False


def test_values_normalize_and_preserve_positions() -> None:
    values = SettingsValues(
        accent="AABBCC",
        opacity=5,
        size_percent=999,
        show_gregorian="yes",  # type: ignore[arg-type]
        always_on_top="0",  # type: ignore[arg-type]
        start_with_windows="on",  # type: ignore[arg-type]
        widget_x="12",  # type: ignore[arg-type]
        widget_y=None,
    ).normalized()
    assert values.accent == "#aabbcc"
    assert values.opacity == 60
    assert values.size_percent == 130
    assert values.show_gregorian is True
    assert values.always_on_top is False
    assert values.start_with_windows is True
    assert values.widget_x == 12
    assert values.widget_y is None
    assert values.has_position is False
    assert values.with_position(30, 40).has_position is True


def test_defaults_are_sane() -> None:
    assert DEFAULTS.opacity == 94
    assert DEFAULTS.size_percent == 100
    assert DEFAULTS.show_gregorian is True
    assert DEFAULTS.always_on_top is False
    assert DEFAULTS.start_with_windows is False
    assert DEFAULTS.has_position is False


def test_store_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    store = SettingsStore(path)
    assert store.load() == SettingsValues(accent=DEFAULT_ACCENT.lower())

    values = SettingsValues(
        accent="#F472B6",
        opacity=72,
        size_percent=125,
        show_gregorian=False,
        always_on_top=True,
        start_with_windows=True,
        widget_x=321,
        widget_y=456,
    )
    saved = store.save(values)
    assert saved == values.normalized()
    assert path.is_file()

    reloaded = SettingsStore(path).load()
    assert reloaded == saved


def test_save_position_and_reset(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    store = SettingsStore(path)
    store.save(
        SettingsValues(
            accent="#2DD4BF",
            opacity=70,
            size_percent=90,
            show_gregorian=False,
            always_on_top=True,
            start_with_windows=True,
            widget_x=1,
            widget_y=2,
        )
    )
    store.save_position(100, 200)
    loaded = store.load()
    assert (loaded.widget_x, loaded.widget_y) == (100, 200)
    assert loaded.accent == "#2dd4bf"

    reset = store.reset()
    assert reset.accent == DEFAULT_ACCENT.lower()
    assert reset.opacity == 94
    assert reset.size_percent == 100
    assert reset.show_gregorian is True
    assert reset.always_on_top is False
    assert reset.start_with_windows is False
    assert reset.has_position is False
    assert store.load() == reset


def test_invalid_hand_edited_values_fall_back_safely(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    raw = QSettings(str(path), QSettings.Format.IniFormat)
    raw.setValue("appearance/accent", "#GGGGGG")
    raw.setValue("appearance/opacity", "not-a-number")
    raw.setValue("appearance/size_percent", 10000)
    raw.setValue("appearance/show_gregorian", "maybe")
    raw.setValue("behavior/always_on_top", "maybe")
    raw.setValue("behavior/start_with_windows", "yes")
    raw.setValue("widget/x", "not-a-number")
    raw.setValue("widget/y", "")
    raw.sync()
    raw = None

    loaded = SettingsStore(path).load()
    assert loaded.accent == DEFAULT_ACCENT.lower()
    assert loaded.opacity == 94
    assert loaded.size_percent == 130
    assert loaded.show_gregorian is True
    assert loaded.always_on_top is False
    assert loaded.start_with_windows is True
    assert loaded.widget_x is None
    assert loaded.widget_y is None


def test_config_override_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "config"
    monkeypatch.setenv("PCW_CONFIG_DIR", str(override))
    assert config_dir() == override
    assert config_file("alternate.ini") == override / "alternate.ini"
    store = SettingsStore()
    assert store.path == override / "settings.ini"
    store.save(SettingsValues(opacity=88))
    assert (override / "settings.ini").is_file()


def test_weather_defaults_and_invalid_values_fall_back() -> None:
    assert DEFAULT_ACCENT == "#2DD4BF"
    assert DEFAULTS.normalized().accent == DEFAULT_ACCENT.lower()
    assert DEFAULTS.weather_city == ""
    assert DEFAULTS.weather_latitude is None
    assert DEFAULTS.weather_longitude is None
    assert DEFAULTS.weather_timezone == "auto"
    assert DEFAULTS.weather_temperature_unit == "celsius"
    assert DEFAULTS.weather_wind_speed_unit == "kmh"
    assert DEFAULTS.has_weather_location is False

    values = SettingsValues(
        weather_city="Somewhere",
        weather_latitude="not-a-number",  # type: ignore[arg-type]
        weather_longitude=999,  # type: ignore[arg-type]
        weather_timezone="",
        weather_location_id="bad-id",  # type: ignore[arg-type]
        weather_temperature_unit="kelvin",
        weather_wind_speed_unit="furlongs",
    ).normalized()
    assert values.weather_latitude is None
    assert values.weather_longitude is None
    assert values.weather_timezone == "auto"
    assert values.weather_location_id is None
    assert values.weather_temperature_unit == "celsius"
    assert values.weather_wind_speed_unit == "kmh"
    assert values.has_weather_location is False


def test_weather_settings_round_trip_and_position_update(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    store = SettingsStore(path)
    values = SettingsValues(
        weather_city="تهران",
        weather_latitude=35.7,
        weather_longitude=51.4,
        weather_timezone="Asia/Tehran",
        weather_country="ایران",
        weather_admin1="تهران",
        weather_location_id=112931,
        weather_temperature_unit="fahrenheit",
        weather_wind_speed_unit="mph",
    )
    saved = store.save(values)
    loaded = store.load()
    assert loaded.weather_key == saved.weather_key
    assert loaded.weather_city == "تهران"
    assert loaded.weather_latitude == pytest.approx(35.7)
    assert loaded.weather_longitude == pytest.approx(51.4)
    assert loaded.weather_timezone == "Asia/Tehran"
    assert loaded.weather_country == "ایران"
    assert loaded.weather_admin1 == "تهران"
    assert loaded.weather_location_id == 112931
    assert loaded.weather_temperature_unit == "fahrenheit"
    assert loaded.weather_wind_speed_unit == "mph"
    assert loaded.has_weather_location is True

    store.save_position(12, 34)
    after_move = store.load()
    assert (after_move.widget_x, after_move.widget_y) == (12, 34)
    assert after_move.weather_key == loaded.weather_key

