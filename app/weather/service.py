"""Non-blocking weather service with cache, de-duplication and scheduling."""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QObject, QTimer, Signal

from app.weather.cache import WeatherCache
from app.weather.models import (
    WeatherLocation,
    WeatherSnapshot,
    WeatherState,
    normalize_temperature_unit,
    normalize_wind_speed_unit,
)
from app.weather.open_meteo import OpenMeteoForecastClient

DEFAULT_REFRESH_MS = 15 * 60 * 1000


class WeatherService(QObject):
    """Own the one active forecast request and expose a single UI state."""

    stateChanged = Signal(object)  # WeatherState

    def __init__(
        self,
        client: OpenMeteoForecastClient | None = None,
        cache: WeatherCache | None = None,
        *,
        refresh_ms: int = DEFAULT_REFRESH_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client or OpenMeteoForecastClient(parent=self)
        self._cache = cache or WeatherCache()
        self._refresh_interval = dt.timedelta(milliseconds=max(30_000, int(refresh_ms)))
        self._refresh_ms = max(30_000, int(refresh_ms))

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)

        self._client.finished.connect(self._on_finished)
        self._client.failed.connect(self._on_failed)

        self._location: WeatherLocation | None = None
        self._temperature_unit = "celsius"
        self._wind_speed_unit = "kmh"
        self._state = WeatherState()
        self._started = False
        self._loading = False

    @property
    def state(self) -> WeatherState:
        return self._state

    @property
    def location(self) -> WeatherLocation | None:
        return self._location

    @property
    def temperature_unit(self) -> str:
        return self._temperature_unit

    @property
    def wind_speed_unit(self) -> str:
        return self._wind_speed_unit

    def configure(
        self,
        location: WeatherLocation | None,
        temperature_unit: str = "celsius",
        wind_speed_unit: str = "kmh",
    ) -> None:
        """Apply user choices; fetch only when running and cache is unusable."""
        if location is not None and not location.is_valid:
            location = None
        temperature = normalize_temperature_unit(temperature_unit)
        wind = normalize_wind_speed_unit(wind_speed_unit)
        changed = (
            location != self._location
            or temperature != self._temperature_unit
            or wind != self._wind_speed_unit
        )
        if not changed:
            return

        self._client.cancel()
        self._timer.stop()
        self._loading = False
        self._location = location
        self._temperature_unit = temperature
        self._wind_speed_unit = wind

        if location is None:
            self._set_state(WeatherState(status="idle"))
            return

        cached = self._cache.load(location, temperature, wind)
        if cached is not None and not cached.is_stale(self._refresh_interval):
            self._set_state(
                WeatherState(status="ready", snapshot=cached, location=location)
            )
            if self._started:
                self._schedule_remaining(cached)
            return

        self._set_state(
            WeatherState(
                status="loading",
                snapshot=cached,
                location=location,
                message="در حال به‌روزرسانی…",
            )
        )
        if self._started:
            self.refresh(force=True)

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        if self._location is None:
            self._set_state(WeatherState(status="idle"))
            return
        snapshot = self._state.snapshot
        if snapshot is not None and not snapshot.is_stale(self._refresh_interval):
            self._schedule_remaining(snapshot)
            return
        self.refresh(force=True)

    def stop(self) -> None:
        self._started = False
        self._timer.stop()
        self._loading = False
        self._client.cancel()

    def refresh(self, force: bool = True) -> None:
        if self._location is None:
            self._set_state(WeatherState(status="idle"))
            return
        if self._loading:
            if not force:
                return
            self._client.cancel()
        self._timer.stop()
        self._loading = True
        self._state = WeatherState(
            status="loading",
            snapshot=self._state.snapshot,
            location=self._location,
            message="در حال به‌روزرسانی…",
        )
        self.stateChanged.emit(self._state)
        self._client.request(
            self._location,
            self._temperature_unit,
            self._wind_speed_unit,
        )

    def _on_finished(self, snapshot: object) -> None:
        if not isinstance(snapshot, WeatherSnapshot):
            self._loading = False
            return
        if self._location is None or snapshot.location.cache_key != self._location.cache_key:
            self._loading = False
            return
        if snapshot.temperature_unit != self._temperature_unit:
            self._loading = False
            return
        if snapshot.wind_speed_unit != self._wind_speed_unit:
            self._loading = False
            return
        self._loading = False
        self._cache.save(snapshot)
        self._set_state(
            WeatherState(status="ready", snapshot=snapshot, location=self._location)
        )
        self._schedule()

    def _on_failed(self, message: str) -> None:
        if not message:
            self._loading = False
            return
        self._loading = False
        snapshot = self._state.snapshot
        self._set_state(
            WeatherState(
                status="stale" if snapshot is not None else "error",
                snapshot=snapshot,
                location=self._location,
                message=message,
            )
        )
        self._schedule()

    def _schedule(self) -> None:
        if self._started and self._location is not None:
            self._timer.start(self._refresh_ms)

    def _schedule_remaining(self, snapshot: WeatherSnapshot) -> None:
        if not self._started or self._location is None:
            return
        remaining = self._refresh_interval - snapshot.age()
        self._timer.start(
            max(5_000, min(self._refresh_ms, int(remaining.total_seconds() * 1000)))
        )

    def _set_state(self, state: WeatherState) -> None:
        if state != self._state:
            self._state = state
            self.stateChanged.emit(state)
