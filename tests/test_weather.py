"""Weather parsing, URL building and cache tests (no live network)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from app.weather.cache import WeatherCache
from app.weather.conditions import condition_kind, condition_text
from app.weather.models import DailyForecast, WeatherLocation, WeatherSnapshot
from app.weather.open_meteo import (
    WeatherDataError,
    build_forecast_url,
    build_geocoding_url,
    parse_forecast_payload,
    parse_geocoding_payload,
)
from app.weather.visuals import visual_from_snapshot

LOCATION = WeatherLocation(
    "تهران",
    35.7,
    51.4,
    "Asia/Tehran",
    "ایران",
    "تهران",
    112931,
)

FETCHED_AT = dt.datetime(2026, 10, 28, 19, 15, tzinfo=dt.timezone(dt.timedelta(hours=3, minutes=30)))


def _payload() -> dict:
    return {
        "latitude": 35.7,
        "longitude": 51.4,
        "timezone": "Asia/Tehran",
        "current": {
            "time": "2026-10-28T19:15",
            "temperature_2m": 18.4,
            "relative_humidity_2m": 46,
            "apparent_temperature": 17.9,
            "weather_code": 2,
            "wind_speed_10m": 8.2,
            "is_day": 0,
            "uv_index": 2.8,
        },
        "daily": {
            "time": [
                "2026-10-28",
                "2026-10-29",
                "2026-10-30",
                "2026-10-31",
                "2026-11-01",
            ],
            "weather_code": [2, 61, 3, 0, 1],
            "temperature_2m_max": [22.0, 19.0, 20.0, 23.0, 21.0],
            "temperature_2m_min": [11.0, 10.0, 9.0, 10.0, 12.0],
            "sunrise": [
                "2026-10-28T06:12",
                "2026-10-29T06:13",
                "2026-10-30T06:14",
                "2026-10-31T06:15",
                "2026-11-01T06:16",
            ],
            "sunset": [
                "2026-10-28T17:10",
                "2026-10-29T17:09",
                "2026-10-30T17:08",
                "2026-10-31T17:07",
                "2026-11-01T17:06",
            ],
        },
    }


def test_build_forecast_url_contains_location_units_and_days() -> None:
    url = build_forecast_url(LOCATION, "fahrenheit", "mph", forecast_days=5)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "api.open-meteo.com"
    assert query["latitude"] == ["35.700000"]
    assert query["longitude"] == ["51.400000"]
    assert query["temperature_unit"] == ["fahrenheit"]
    assert query["wind_speed_unit"] == ["mph"]
    assert query["forecast_days"] == ["5"]
    assert query["timezone"] == ["Asia/Tehran"]
    assert "temperature_2m" in query["current"][0]
    assert "is_day" in query["current"][0].split(",")
    assert "uv_index" in query["current"][0].split(",")
    assert {"sunrise", "sunset"}.issubset(set(query["daily"][0].split(",")))


def test_build_geocoding_url_is_encoded_and_uses_persian() -> None:
    url = build_geocoding_url("تهران", count=5)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "geocoding-api.open-meteo.com"
    assert query["name"] == ["تهران"]
    assert query["count"] == ["5"]
    assert query["language"] == ["fa"]


def test_forecast_payload_parses_current_and_daily() -> None:
    snapshot = parse_forecast_payload(
        _payload(), LOCATION, "celsius", "kmh", fetched_at=FETCHED_AT
    )
    assert snapshot.location == LOCATION
    assert snapshot.temperature == pytest.approx(18.4)
    assert snapshot.humidity == 46
    assert snapshot.wind_speed == pytest.approx(8.2)
    assert snapshot.weather_code == 2
    assert snapshot.is_day is False
    assert snapshot.uv_index == pytest.approx(2.8)
    assert snapshot.sunrise == dt.time(6, 12)
    assert snapshot.sunset == dt.time(17, 10)
    assert snapshot.temperature_symbol == "°C"
    assert snapshot.wind_speed_label == "km/h"
    assert len(snapshot.daily) == 5
    assert snapshot.daily[0].date == dt.date(2026, 10, 28)
    assert snapshot.daily[0].temp_max == pytest.approx(22.0)
    assert snapshot.from_cache is False


@pytest.mark.parametrize(
    ("current_time", "expected"),
    [
        ("2026-10-28T06:12", True),
        ("2026-10-28T12:00", True),
        ("2026-10-28T17:10", False),
        ("2026-10-28T19:15", False),
        ("2026-10-28T03:00", False),
    ],
)
def test_missing_is_day_falls_back_to_local_sunrise_sunset(
    current_time: str, expected: bool
) -> None:
    payload = _payload()
    payload["current"].pop("is_day")
    payload["current"]["time"] = current_time
    snapshot = parse_forecast_payload(payload, LOCATION)
    assert snapshot.is_day is expected


def test_current_is_day_takes_precedence_over_sunrise_sunset() -> None:
    payload = _payload()
    payload["current"]["is_day"] = 1
    assert parse_forecast_payload(payload, LOCATION).is_day is True


def test_malformed_is_day_falls_back_to_sunrise_sunset() -> None:
    payload = _payload()
    payload["current"]["is_day"] = None
    payload["current"]["time"] = "2026-10-28T12:00"
    assert parse_forecast_payload(payload, LOCATION).is_day is True


def test_missing_is_day_and_sunrise_sunset_keeps_day_fallback() -> None:
    payload = _payload()
    payload["current"].pop("is_day")
    payload["daily"].pop("sunrise")
    payload["daily"].pop("sunset")
    assert parse_forecast_payload(payload, LOCATION).is_day is True


def test_sunrise_sunset_fallback_selects_matching_day_and_night_backgrounds() -> None:
    payload = _payload()
    payload["current"].pop("is_day")
    payload["current"]["weather_code"] = 0

    payload["current"]["time"] = "2026-10-28T12:00"
    day_snapshot = parse_forecast_payload(payload, LOCATION)
    day_visual = visual_from_snapshot(day_snapshot)
    assert day_visual is not None
    assert day_visual.background_name == "Clear Day.jpeg"

    payload["current"]["time"] = "2026-10-28T19:15"
    night_snapshot = parse_forecast_payload(payload, LOCATION)
    night_visual = visual_from_snapshot(night_snapshot)
    assert night_visual is not None
    assert night_visual.background_name == "Clear Night.jpeg"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"error": True, "reason": "bad request"},
        {"current": {}},
        {"current": {"temperature_2m": None}},
        {"current": {"temperature_2m": "not-a-number"}},
    ],
)
def test_forecast_payload_rejects_invalid_data(payload: object) -> None:
    with pytest.raises(WeatherDataError):
        parse_forecast_payload(payload, LOCATION)


def test_forecast_payload_skips_bad_daily_rows() -> None:
    payload = _payload()
    payload["daily"]["time"] = ["bad-date", "2026-10-29"]
    payload["daily"]["weather_code"] = [2, 61]
    payload["daily"]["temperature_2m_max"] = [22, 19]
    payload["daily"]["temperature_2m_min"] = [11, 10]
    snapshot = parse_forecast_payload(payload, LOCATION)
    assert [day.date for day in snapshot.daily] == [dt.date(2026, 10, 29)]


def test_geocoding_payload_returns_locations() -> None:
    payload = {
        "results": [
            {
                "id": 112931,
                "name": "تهران",
                "latitude": 35.69439,
                "longitude": 51.42151,
                "timezone": "Asia/Tehran",
                "country": "ایران",
                "admin1": "تهران",
            },
            {"name": "", "latitude": 0, "longitude": 0},
        ]
    }
    locations = parse_geocoding_payload(payload)
    assert len(locations) == 1
    assert locations[0].name == "تهران"
    assert locations[0].country == "ایران"
    assert locations[0].timezone == "Asia/Tehran"


def test_geocoding_payload_handles_empty_and_invalid() -> None:
    assert parse_geocoding_payload({}) == ()
    with pytest.raises(WeatherDataError):
        parse_geocoding_payload({"results": "not-a-list"})


def test_conditions_cover_wmo_families() -> None:
    assert condition_text(0) == "صاف"
    assert condition_text(61) == "باران سبک"
    assert condition_text(999) == "نامشخص"
    assert condition_kind(0, True) == "clear"
    assert condition_kind(0, False) == "clear-night"
    assert condition_kind(61, True) == "rain"
    assert condition_kind(95, True) == "thunder"
    assert condition_kind(45, True) == "fog"


def test_cache_round_trip_and_key_validation(tmp_path: Path) -> None:
    cache = WeatherCache(tmp_path / "weather-cache.json")
    snapshot = parse_forecast_payload(
        _payload(), LOCATION, "celsius", "kmh", fetched_at=FETCHED_AT
    )
    assert cache.save(snapshot) is True

    loaded = cache.load(LOCATION, "celsius", "kmh")
    assert loaded is not None
    assert loaded.from_cache is True
    assert loaded.temperature == pytest.approx(snapshot.temperature)
    assert loaded.daily == snapshot.daily
    assert loaded.sunrise == snapshot.sunrise
    assert loaded.sunset == snapshot.sunset
    assert loaded.uv_index == pytest.approx(snapshot.uv_index)

    assert cache.load(LOCATION, "fahrenheit", "kmh") is None
    other = WeatherLocation("کرج", 35.8, 50.9)
    assert cache.load(other, "celsius", "kmh") is None


def test_cache_ignores_missing_or_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "weather-cache.json"
    cache = WeatherCache(path)
    assert cache.load(LOCATION) is None
    path.write_text("{not-json", encoding="utf-8")
    assert cache.load(LOCATION) is None
    path.write_text(json.dumps({"version": 999}), encoding="utf-8")
    assert cache.load(LOCATION) is None


def test_snapshot_serialization_round_trip() -> None:
    snapshot = WeatherSnapshot(
        location=LOCATION,
        temperature=18.4,
        humidity=46,
        wind_speed=8.2,
        weather_code=2,
        is_day=False,
        daily=(DailyForecast(dt.date(2026, 10, 28), 2, 22, 11),),
        fetched_at=FETCHED_AT,
        apparent_temperature=17.9,
        sunrise=dt.time(6, 12),
        sunset=dt.time(17, 10),
        uv_index=2.8,
    )
    restored = WeatherSnapshot.from_dict(snapshot.to_dict())
    assert restored is not None
    assert restored.location == snapshot.location
    assert restored.daily == snapshot.daily
    assert restored.temperature == pytest.approx(snapshot.temperature)
    assert restored.sunrise == snapshot.sunrise
    assert restored.sunset == snapshot.sunset
    assert restored.uv_index == pytest.approx(snapshot.uv_index)
    assert restored.from_cache is True
