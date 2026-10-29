"""Per-user settings with defensive validation.

Settings live in an INI file under ``%APPDATA%\\PersianCalendarWidget`` (or
``PCW_CONFIG_DIR``), never inside the application directory.  Missing, stale or
hand-edited values fall back to safe defaults.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from pathlib import Path

from PySide6.QtCore import QSettings

from app.core.paths import config_file
from app.weather.models import (
    normalize_temperature_unit,
    normalize_wind_speed_unit,
)

DEFAULT_ACCENT = "#2DD4BF"
DEFAULT_OPACITY = 94
DEFAULT_SIZE_PERCENT = 100
MIN_OPACITY, MAX_OPACITY = 60, 100
MIN_SIZE_PERCENT, MAX_SIZE_PERCENT = 80, 130

ACCENT_PRESETS: tuple[tuple[str, str], ...] = (
    ("آبی", "#6EA8FF"),
    ("بنفش", "#A78BFA"),
    ("فیروزه‌ای", "#2DD4BF"),
    ("سبز", "#4ADE80"),
    ("صورتی", "#F472B6"),
    ("نارنجی", "#FB923C"),
    ("طلایی", "#F5C26B"),
)

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def normalize_accent(value: object, fallback: str = DEFAULT_ACCENT) -> str:
    text = str(value or "").strip()
    if _HEX_RE.match(text):
        if not text.startswith("#"):
            text = "#" + text
        return text.lower()
    fallback_text = str(fallback or DEFAULT_ACCENT).strip()
    if not _HEX_RE.match(fallback_text):
        return DEFAULT_ACCENT.lower()
    if not fallback_text.startswith("#"):
        fallback_text = "#" + fallback_text
    return fallback_text.lower()


def clamp_int(value: object, minimum: int, maximum: int, fallback: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, number))


def coerce_bool(value: object, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return fallback


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class SettingsValues:
    accent: str = DEFAULT_ACCENT
    opacity: int = DEFAULT_OPACITY
    size_percent: int = DEFAULT_SIZE_PERCENT
    show_gregorian: bool = True
    always_on_top: bool = False
    start_with_windows: bool = False
    widget_x: int | None = None
    widget_y: int | None = None
    weather_city: str = ""
    weather_latitude: float | None = None
    weather_longitude: float | None = None
    weather_timezone: str = "auto"
    weather_country: str = ""
    weather_admin1: str = ""
    weather_location_id: int | None = None
    weather_temperature_unit: str = "celsius"
    weather_wind_speed_unit: str = "kmh"

    def normalized(self) -> "SettingsValues":
        latitude = _optional_float(self.weather_latitude)
        longitude = _optional_float(self.weather_longitude)
        if latitude is not None and not -90.0 <= latitude <= 90.0:
            latitude = None
        if longitude is not None and not -180.0 <= longitude <= 180.0:
            longitude = None
        if latitude is None or longitude is None:
            latitude = None
            longitude = None
        return replace(
            self,
            accent=normalize_accent(self.accent),
            opacity=clamp_int(
                self.opacity, MIN_OPACITY, MAX_OPACITY, DEFAULT_OPACITY
            ),
            size_percent=clamp_int(
                self.size_percent,
                MIN_SIZE_PERCENT,
                MAX_SIZE_PERCENT,
                DEFAULT_SIZE_PERCENT,
            ),
            show_gregorian=coerce_bool(self.show_gregorian, True),
            always_on_top=coerce_bool(self.always_on_top, False),
            start_with_windows=coerce_bool(self.start_with_windows, False),
            widget_x=_optional_int(self.widget_x),
            widget_y=_optional_int(self.widget_y),
            weather_city=_optional_text(self.weather_city),
            weather_latitude=latitude,
            weather_longitude=longitude,
            weather_timezone=_optional_text(self.weather_timezone) or "auto",
            weather_country=_optional_text(self.weather_country),
            weather_admin1=_optional_text(self.weather_admin1),
            weather_location_id=_optional_int(self.weather_location_id),
            weather_temperature_unit=normalize_temperature_unit(
                self.weather_temperature_unit
            ),
            weather_wind_speed_unit=normalize_wind_speed_unit(
                self.weather_wind_speed_unit
            ),
        )

    @property
    def has_position(self) -> bool:
        return self.widget_x is not None and self.widget_y is not None

    @property
    def has_weather_location(self) -> bool:
        return bool(self.weather_city) and (
            self.weather_latitude is not None and self.weather_longitude is not None
        )

    @property
    def weather_key(self) -> tuple[object, ...]:
        return (
            self.weather_city,
            self.weather_latitude,
            self.weather_longitude,
            self.weather_timezone,
            self.weather_country,
            self.weather_admin1,
            self.weather_location_id,
            self.weather_temperature_unit,
            self.weather_wind_speed_unit,
        )

    def with_position(self, x: int | None, y: int | None) -> "SettingsValues":
        return replace(self, widget_x=x, widget_y=y)


DEFAULTS = SettingsValues()


class SettingsStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else config_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._settings = QSettings(str(self.path), QSettings.Format.IniFormat)

    # ------------------------------------------------------------------ read
    def _raw(self, key: str) -> object:
        return self._settings.value(key)

    def load(self) -> SettingsValues:
        accent = normalize_accent(self._raw("appearance/accent"))
        opacity = clamp_int(
            self._raw("appearance/opacity"),
            MIN_OPACITY,
            MAX_OPACITY,
            DEFAULT_OPACITY,
        )
        size = clamp_int(
            self._raw("appearance/size_percent"),
            MIN_SIZE_PERCENT,
            MAX_SIZE_PERCENT,
            DEFAULT_SIZE_PERCENT,
        )
        show_gregorian = coerce_bool(
            self._raw("appearance/show_gregorian"), True
        )
        always_on_top = coerce_bool(self._raw("behavior/always_on_top"), False)
        start_with_windows = coerce_bool(
            self._raw("behavior/start_with_windows"), False
        )
        x = _optional_int(self._raw("widget/x"))
        y = _optional_int(self._raw("widget/y"))
        return SettingsValues(
            accent=accent,
            opacity=opacity,
            size_percent=size,
            show_gregorian=show_gregorian,
            always_on_top=always_on_top,
            start_with_windows=start_with_windows,
            widget_x=x,
            widget_y=y,
            weather_city=_optional_text(self._raw("weather/city")),
            weather_latitude=_optional_float(self._raw("weather/latitude")),
            weather_longitude=_optional_float(self._raw("weather/longitude")),
            weather_timezone=_optional_text(self._raw("weather/timezone")) or "auto",
            weather_country=_optional_text(self._raw("weather/country")),
            weather_admin1=_optional_text(self._raw("weather/admin1")),
            weather_location_id=_optional_int(self._raw("weather/location_id")),
            weather_temperature_unit=normalize_temperature_unit(
                self._raw("weather/temperature_unit")
            ),
            weather_wind_speed_unit=normalize_wind_speed_unit(
                self._raw("weather/wind_speed_unit")
            ),
        ).normalized()

    # ----------------------------------------------------------------- write
    def save(self, values: SettingsValues) -> SettingsValues:
        values = values.normalized()
        self._settings.setValue("appearance/accent", values.accent)
        self._settings.setValue("appearance/opacity", int(values.opacity))
        self._settings.setValue(
            "appearance/size_percent", int(values.size_percent)
        )
        self._settings.setValue(
            "appearance/show_gregorian", bool(values.show_gregorian)
        )
        self._settings.setValue(
            "behavior/always_on_top", bool(values.always_on_top)
        )
        self._settings.setValue(
            "behavior/start_with_windows", bool(values.start_with_windows)
        )
        self._settings.setValue("widget/x", values.widget_x)
        self._settings.setValue("widget/y", values.widget_y)
        self._settings.setValue("weather/city", values.weather_city)
        self._settings.setValue("weather/latitude", values.weather_latitude)
        self._settings.setValue("weather/longitude", values.weather_longitude)
        self._settings.setValue("weather/timezone", values.weather_timezone)
        self._settings.setValue("weather/country", values.weather_country)
        self._settings.setValue("weather/admin1", values.weather_admin1)
        self._settings.setValue("weather/location_id", values.weather_location_id)
        self._settings.setValue(
            "weather/temperature_unit", values.weather_temperature_unit
        )
        self._settings.setValue(
            "weather/wind_speed_unit", values.weather_wind_speed_unit
        )
        self._settings.sync()
        return values

    def save_position(self, x: int, y: int) -> None:
        self._settings.setValue("widget/x", int(x))
        self._settings.setValue("widget/y", int(y))
        self._settings.sync()

    def reset(self) -> SettingsValues:
        self._settings.clear()
        self._settings.sync()
        return self.save(DEFAULTS)

    # ---------------------------------------------------------------- helpers
    def raw_value(self, key: str) -> object:
        return self._settings.value(key)

    def sync(self) -> None:
        self._settings.sync()
