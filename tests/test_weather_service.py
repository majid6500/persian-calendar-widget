"""Weather service state machine tests using a fake, offline client."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.weather.cache import WeatherCache
from app.weather.models import DailyForecast, WeatherLocation, WeatherSnapshot, WeatherState
from app.weather.service import WeatherService

LOCATION = WeatherLocation(
    "تهران", 35.7, 51.4, "Asia/Tehran", "ایران", "تهران", 112931
)


class FakeForecastClient(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[WeatherLocation, str, str]] = []
        self.cancelled = 0

    def request(
        self,
        location: WeatherLocation,
        temperature_unit: str = "celsius",
        wind_speed_unit: str = "kmh",
    ) -> None:
        self.requests.append((location, temperature_unit, wind_speed_unit))

    def cancel(self) -> None:
        self.cancelled += 1


def _snapshot(location: WeatherLocation = LOCATION) -> WeatherSnapshot:
    return WeatherSnapshot(
        location=location,
        temperature=18.4,
        humidity=46,
        wind_speed=8.2,
        weather_code=2,
        is_day=False,
        daily=(
            DailyForecast(dt.date(2026, 10, 28), 2, 22, 11),
            DailyForecast(dt.date(2026, 10, 29), 61, 19, 10),
        ),
        fetched_at=dt.datetime.now().astimezone(),
    )


def _service(
    tmp_path: Path, client: FakeForecastClient, refresh_ms: int = 60_000
) -> WeatherService:
    return WeatherService(
        client=client,
        cache=WeatherCache(tmp_path / "weather-cache.json"),
        refresh_ms=refresh_ms,
    )


def test_loading_success_caches_and_schedules(qtbot, tmp_path: Path) -> None:
    client = FakeForecastClient()
    service = _service(tmp_path, client, refresh_ms=60_000)
    states: list[WeatherState] = []
    service.stateChanged.connect(states.append)

    service.configure(LOCATION)
    assert service.state.status == "loading"
    assert client.requests == []

    service.start()
    assert len(client.requests) == 1
    assert client.requests[0][0] == LOCATION
    assert client.requests[0][1:] == ("celsius", "kmh")

    snapshot = _snapshot()
    client.finished.emit(snapshot)
    assert service.state.status == "ready"
    assert service.state.snapshot == snapshot
    assert service.state.location == LOCATION
    assert (tmp_path / "weather-cache.json").is_file()
    assert service._timer.isActive()
    assert states


def test_failure_keeps_cached_snapshot_as_stale(qtbot, tmp_path: Path) -> None:
    client = FakeForecastClient()
    service = _service(tmp_path, client)
    service.configure(LOCATION)
    service.start()
    client.finished.emit(_snapshot())

    service.refresh()
    assert service.state.status == "loading"
    assert service.state.snapshot is not None
    client.failed.emit("اتصال قطع است")
    assert service.state.status == "stale"
    assert service.state.snapshot is not None
    assert service.state.message == "اتصال قطع است"


def test_failure_without_data_is_error(qtbot, tmp_path: Path) -> None:
    client = FakeForecastClient()
    service = _service(tmp_path, client)
    service.configure(LOCATION)
    service.start()
    client.failed.emit("offline")
    assert service.state.status == "error"
    assert service.state.snapshot is None


def test_fresh_cache_avoids_an_immediate_request(qtbot, tmp_path: Path) -> None:
    cache = WeatherCache(tmp_path / "weather-cache.json")
    assert cache.save(_snapshot()) is True
    client = FakeForecastClient()
    service = _service(tmp_path, client)
    service.configure(LOCATION)
    assert service.state.status == "ready"
    service.start()
    assert client.requests == []
    assert service._timer.isActive()


def test_units_change_triggers_a_new_request(qtbot, tmp_path: Path) -> None:
    client = FakeForecastClient()
    service = _service(tmp_path, client)
    service.configure(LOCATION)
    service.start()
    client.finished.emit(_snapshot())

    service.configure(LOCATION, "fahrenheit", "mph")
    assert len(client.requests) == 2
    assert client.requests[-1][1:] == ("fahrenheit", "mph")
    assert service.state.status == "loading"


def test_no_city_stays_idle_and_never_requests(qtbot, tmp_path: Path) -> None:
    client = FakeForecastClient()
    service = _service(tmp_path, client)
    service.configure(None)
    service.start()
    assert service.state.status == "idle"
    assert client.requests == []
    service.refresh()
    assert client.requests == []


def test_stop_cancels_request_and_timer(qtbot, tmp_path: Path) -> None:
    client = FakeForecastClient()
    service = _service(tmp_path, client)
    service.configure(LOCATION)
    service.start()
    service.stop()
    assert client.cancelled >= 1
    assert not service._timer.isActive()
