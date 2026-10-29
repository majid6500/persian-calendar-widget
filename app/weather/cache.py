"""Small, atomic JSON cache for the last successful weather response."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.paths import config_file
from app.weather.models import (
    WeatherLocation,
    WeatherSnapshot,
    normalize_temperature_unit,
    normalize_wind_speed_unit,
)

CACHE_VERSION = 1


class WeatherCache:
    """Persist one snapshot, keyed by coordinates and display units."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else config_file("weather-cache.json")

    def load(
        self,
        location: WeatherLocation,
        temperature_unit: str = "celsius",
        wind_speed_unit: str = "kmh",
    ) -> WeatherSnapshot | None:
        if not location.is_valid:
            return None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
            return None
        snapshot_payload = payload.get("snapshot")
        snapshot = WeatherSnapshot.from_dict(snapshot_payload)
        if snapshot is None:
            return None
        if snapshot.location.cache_key != location.cache_key:
            return None
        if snapshot.temperature_unit != normalize_temperature_unit(temperature_unit):
            return None
        if snapshot.wind_speed_unit != normalize_wind_speed_unit(wind_speed_unit):
            return None
        return snapshot

    def save(self, snapshot: WeatherSnapshot) -> bool:
        payload: dict[str, Any] = {
            "version": CACHE_VERSION,
            "snapshot": snapshot.to_dict(),
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            return True
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
