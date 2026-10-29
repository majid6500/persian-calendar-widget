"""Immutable weather values shared by the service, cache and UI."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Literal

TEMPERATURE_UNITS = ("celsius", "fahrenheit")
WIND_SPEED_UNITS = ("kmh", "ms", "mph", "kn")

TEMPERATURE_SYMBOLS = {
    "celsius": "°C",
    "fahrenheit": "°F",
}

WIND_SPEED_LABELS = {
    "kmh": "km/h",
    "ms": "m/s",
    "mph": "mph",
    "kn": "kn",
}

WeatherStatus = Literal["idle", "loading", "ready", "stale", "error"]


def normalize_temperature_unit(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in TEMPERATURE_UNITS else "celsius"


def normalize_wind_speed_unit(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in WIND_SPEED_UNITS else "kmh"


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class WeatherLocation:
    """A manually selected city and its WGS84 coordinates."""

    name: str
    latitude: float
    longitude: float
    timezone: str = "auto"
    country: str = ""
    admin1: str = ""
    location_id: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name).strip())
        object.__setattr__(self, "latitude", _as_float(self.latitude))
        object.__setattr__(self, "longitude", _as_float(self.longitude))
        object.__setattr__(self, "timezone", str(self.timezone or "auto").strip() or "auto")
        object.__setattr__(self, "country", str(self.country or "").strip())
        object.__setattr__(self, "admin1", str(self.admin1 or "").strip())
        if self.location_id is not None:
            object.__setattr__(self, "location_id", _as_int(self.location_id))

    @property
    def display_name(self) -> str:
        return self.name or "شهر انتخاب‌نشده"

    @property
    def subtitle(self) -> str:
        parts = [part for part in (self.admin1, self.country) if part]
        return "، ".join(parts)

    @property
    def is_valid(self) -> bool:
        return (
            bool(self.name)
            and -90.0 <= self.latitude <= 90.0
            and -180.0 <= self.longitude <= 180.0
        )

    @property
    def cache_key(self) -> str:
        return f"{self.latitude:.4f},{self.longitude:.4f}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "country": self.country,
            "admin1": self.admin1,
            "location_id": self.location_id,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "WeatherLocation | None":
        if not isinstance(payload, dict):
            return None
        try:
            location = cls(
                name=str(payload.get("name", "")),
                latitude=_as_float(payload.get("latitude")),
                longitude=_as_float(payload.get("longitude")),
                timezone=str(payload.get("timezone", "auto")),
                country=str(payload.get("country", "")),
                admin1=str(payload.get("admin1", "")),
                location_id=payload.get("location_id"),
            )
        except (TypeError, ValueError):
            return None
        return location if location.is_valid else None


@dataclass(frozen=True)
class DailyForecast:
    date: dt.date
    weather_code: int
    temp_max: float
    temp_min: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "weather_code": int(self.weather_code),
            "temp_max": float(self.temp_max),
            "temp_min": float(self.temp_min),
        }

    @classmethod
    def from_dict(cls, payload: object) -> "DailyForecast | None":
        if not isinstance(payload, dict):
            return None
        try:
            return cls(
                date=dt.date.fromisoformat(str(payload["date"])),
                weather_code=_as_int(payload["weather_code"]),
                temp_max=_as_float(payload["temp_max"]),
                temp_min=_as_float(payload["temp_min"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class WeatherSnapshot:
    location: WeatherLocation
    temperature: float
    humidity: int | None
    wind_speed: float | None
    weather_code: int
    is_day: bool
    daily: tuple[DailyForecast, ...]
    fetched_at: dt.datetime
    temperature_unit: str = "celsius"
    wind_speed_unit: str = "kmh"
    apparent_temperature: float | None = None
    from_cache: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "temperature_unit", normalize_temperature_unit(self.temperature_unit))
        object.__setattr__(self, "wind_speed_unit", normalize_wind_speed_unit(self.wind_speed_unit))
        object.__setattr__(self, "temperature", _as_float(self.temperature, 0.0))
        if self.humidity is not None:
            object.__setattr__(self, "humidity", max(0, min(100, _as_int(self.humidity))))
        if self.wind_speed is not None:
            object.__setattr__(self, "wind_speed", _as_float(self.wind_speed, 0.0))
        if self.apparent_temperature is not None:
            object.__setattr__(
                self,
                "apparent_temperature",
                _as_float(self.apparent_temperature, 0.0),
            )
        object.__setattr__(self, "daily", tuple(self.daily))
        if self.fetched_at.tzinfo is None:
            object.__setattr__(
                self,
                "fetched_at",
                self.fetched_at.replace(tzinfo=dt.datetime.now().astimezone().tzinfo),
            )

    @property
    def temperature_symbol(self) -> str:
        return TEMPERATURE_SYMBOLS.get(self.temperature_unit, "°C")

    @property
    def wind_speed_label(self) -> str:
        return WIND_SPEED_LABELS.get(self.wind_speed_unit, "km/h")

    def age(self, now: dt.datetime | None = None) -> dt.timedelta:
        current = now or dt.datetime.now().astimezone()
        if current.tzinfo is None:
            current = current.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
        return current - self.fetched_at

    def is_stale(self, max_age: dt.timedelta, now: dt.datetime | None = None) -> bool:
        return self.age(now) > max_age

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location.to_dict(),
            "temperature": float(self.temperature),
            "apparent_temperature": self.apparent_temperature,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "weather_code": int(self.weather_code),
            "is_day": bool(self.is_day),
            "daily": [day.to_dict() for day in self.daily],
            "fetched_at": self.fetched_at.isoformat(),
            "temperature_unit": self.temperature_unit,
            "wind_speed_unit": self.wind_speed_unit,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "WeatherSnapshot | None":
        if not isinstance(payload, dict):
            return None
        location = WeatherLocation.from_dict(payload.get("location"))
        if location is None:
            return None
        try:
            fetched_at = dt.datetime.fromisoformat(str(payload["fetched_at"]))
            daily_payload = payload.get("daily", [])
            if not isinstance(daily_payload, list):
                return None
            daily = tuple(
                item
                for item in (DailyForecast.from_dict(raw) for raw in daily_payload)
                if item is not None
            )
            return cls(
                location=location,
                temperature=_as_float(payload["temperature"]),
                humidity=payload.get("humidity"),
                wind_speed=payload.get("wind_speed"),
                weather_code=_as_int(payload["weather_code"]),
                is_day=bool(payload.get("is_day", True)),
                daily=daily,
                fetched_at=fetched_at,
                temperature_unit=str(payload.get("temperature_unit", "celsius")),
                wind_speed_unit=str(payload.get("wind_speed_unit", "kmh")),
                apparent_temperature=payload.get("apparent_temperature"),
                from_cache=True,
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class WeatherState:
    status: WeatherStatus = "idle"
    snapshot: WeatherSnapshot | None = None
    location: WeatherLocation | None = None
    message: str = ""

    @property
    def has_data(self) -> bool:
        return self.snapshot is not None

    @property
    def is_stale(self) -> bool:
        return self.status == "stale" or bool(
            self.snapshot is not None and self.snapshot.from_cache and self.status != "ready"
        )
