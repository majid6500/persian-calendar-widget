"""Asynchronous Open-Meteo forecast and geocoding clients.

Parsing is kept in pure functions so it can be tested without a network.  The
Qt clients only perform non-blocking requests and translate HTTP/JSON failures
into user-facing signals.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from PySide6.QtCore import QObject, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)

from app.weather.models import (
    DailyForecast,
    WeatherLocation,
    WeatherSnapshot,
    normalize_temperature_unit,
    normalize_wind_speed_unit,
)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
USER_AGENT = "PersianCalendarWidget/0.2.0"

CURRENT_FIELDS = (
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "wind_speed_10m",
    "is_day",
    "uv_index",
)
DAILY_FIELDS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "sunrise",
    "sunset",
)


class WeatherDataError(ValueError):
    """Raised when an API response cannot be turned into a valid snapshot."""


def _as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _local_time(value: object) -> dt.datetime | None:
    """Parse an Open-Meteo local timestamp without applying a conversion.

    With ``timezone`` set in the request, both ``current.time`` and
    ``daily.sunrise``/``daily.sunset`` are already expressed in the selected
    city's local time.  The wall-clock values are therefore compared directly.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _sun_times_for_current_day(
    current: dict[str, object], daily_payload: object
) -> tuple[dt.datetime | None, dt.datetime | None]:
    """Return local sunrise and sunset for the current response date."""
    if not isinstance(daily_payload, dict):
        return None, None
    current_time = _local_time(current.get("time"))
    if current_time is None:
        return None, None

    times = daily_payload.get("time")
    sunrise_values = daily_payload.get("sunrise")
    sunset_values = daily_payload.get("sunset")
    if not (
        isinstance(times, list)
        and isinstance(sunrise_values, list)
        and isinstance(sunset_values, list)
    ):
        return None, None

    index: int | None = None
    for candidate, date_text in enumerate(times):
        try:
            if dt.date.fromisoformat(str(date_text)) == current_time.date():
                index = candidate
                break
        except (TypeError, ValueError):
            continue
    if index is None or index >= len(sunrise_values) or index >= len(sunset_values):
        return None, None

    sunrise = _local_time(sunrise_values[index])
    sunset = _local_time(sunset_values[index])
    if sunrise is None or sunset is None or sunset <= sunrise:
        return None, None
    return sunrise, sunset


def _is_day_from_sunrise_sunset(
    current: dict[str, object], daily_payload: object
) -> bool | None:
    """Use the same response's sunrise/sunset when ``is_day`` is absent."""
    sunrise, sunset = _sun_times_for_current_day(current, daily_payload)
    current_time = _local_time(current.get("time"))
    if sunrise is None or sunset is None or current_time is None:
        return None
    return sunrise <= current_time < sunset


def _resolve_is_day(
    current: dict[str, object], daily_payload: object
) -> bool:
    """Prefer the API's current.is_day, then fall back to sunrise/sunset."""
    value = current.get("is_day")
    parsed = _as_int(value)
    if parsed is not None:
        return bool(parsed)
    fallback = _is_day_from_sunrise_sunset(current, daily_payload)
    return True if fallback is None else fallback


def build_forecast_url(
    location: WeatherLocation,
    temperature_unit: str = "celsius",
    wind_speed_unit: str = "kmh",
    forecast_days: int = 5,
) -> str:
    query = QUrlQuery()
    query.addQueryItem("latitude", f"{location.latitude:.6f}")
    query.addQueryItem("longitude", f"{location.longitude:.6f}")
    query.addQueryItem("current", ",".join(CURRENT_FIELDS))
    query.addQueryItem("daily", ",".join(DAILY_FIELDS))
    query.addQueryItem("timezone", location.timezone or "auto")
    query.addQueryItem("forecast_days", str(max(1, min(16, int(forecast_days)))))
    query.addQueryItem(
        "temperature_unit", normalize_temperature_unit(temperature_unit)
    )
    query.addQueryItem(
        "wind_speed_unit", normalize_wind_speed_unit(wind_speed_unit)
    )
    query.addQueryItem("timeformat", "iso8601")

    url = QUrl(FORECAST_URL)
    url.setQuery(query)
    return url.toString()


def build_geocoding_url(query_text: str, count: int = 8) -> str:
    query = QUrlQuery()
    query.addQueryItem("name", str(query_text).strip())
    query.addQueryItem("count", str(max(1, min(100, int(count)))))
    query.addQueryItem("language", "fa")
    query.addQueryItem("format", "json")
    url = QUrl(GEOCODING_URL)
    url.setQuery(query)
    return url.toString()


def parse_forecast_payload(
    payload: object,
    location: WeatherLocation,
    temperature_unit: str = "celsius",
    wind_speed_unit: str = "kmh",
    *,
    fetched_at: dt.datetime | None = None,
) -> WeatherSnapshot:
    if not isinstance(payload, dict):
        raise WeatherDataError("پاسخ سرویس هوا معتبر نیست.")
    if payload.get("error"):
        reason = str(payload.get("reason", "")).strip()
        raise WeatherDataError(reason or "سرویس هوا خطا برگرداند.")

    current = payload.get("current")
    if not isinstance(current, dict):
        raise WeatherDataError("دادهٔ هوای جاری در پاسخ وجود ندارد.")

    temperature = _as_float(current.get("temperature_2m"))
    if temperature is None:
        raise WeatherDataError("دمای هوای جاری در پاسخ وجود ندارد.")

    humidity = _as_int(current.get("relative_humidity_2m"))
    wind_speed = _as_float(current.get("wind_speed_10m"))
    apparent = _as_float(current.get("apparent_temperature"))
    uv_index = _as_float(current.get("uv_index"))
    weather_code = _as_int(current.get("weather_code"))
    daily_payload = payload.get("daily")
    is_day = _resolve_is_day(current, daily_payload)
    sunrise, sunset = _sun_times_for_current_day(current, daily_payload)

    daily: list[DailyForecast] = []
    if isinstance(daily_payload, dict):
        times = daily_payload.get("time")
        codes = daily_payload.get("weather_code")
        highs = daily_payload.get("temperature_2m_max")
        lows = daily_payload.get("temperature_2m_min")
        if isinstance(times, list):
            for index, date_text in enumerate(times):
                try:
                    code = _as_int(codes[index]) if isinstance(codes, list) else None
                    high = _as_float(highs[index]) if isinstance(highs, list) else None
                    low = _as_float(lows[index]) if isinstance(lows, list) else None
                    if code is None or high is None or low is None:
                        continue
                    daily.append(
                        DailyForecast(
                            date=dt.date.fromisoformat(str(date_text)),
                            weather_code=code,
                            temp_max=high,
                            temp_min=low,
                        )
                    )
                except (IndexError, TypeError, ValueError):
                    continue

    return WeatherSnapshot(
        location=location,
        temperature=temperature,
        humidity=humidity,
        wind_speed=wind_speed,
        weather_code=weather_code if weather_code is not None else 0,
        is_day=is_day,
        daily=tuple(daily),
        fetched_at=fetched_at or dt.datetime.now().astimezone(),
        temperature_unit=temperature_unit,
        wind_speed_unit=wind_speed_unit,
        apparent_temperature=apparent,
        from_cache=False,
        sunrise=sunrise.time() if sunrise is not None else None,
        sunset=sunset.time() if sunset is not None else None,
        uv_index=uv_index,
    )


def parse_geocoding_payload(payload: object) -> tuple[WeatherLocation, ...]:
    if not isinstance(payload, dict):
        raise WeatherDataError("پاسخ جستجوی شهر معتبر نیست.")
    if payload.get("error"):
        reason = str(payload.get("reason", "")).strip()
        raise WeatherDataError(reason or "جستجوی شهر خطا برگرداند.")
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise WeatherDataError("فهرست نتایج شهر معتبر نیست.")

    locations: list[WeatherLocation] = []
    for raw in results:
        if not isinstance(raw, dict):
            continue
        location = WeatherLocation.from_dict(
            {
                "name": raw.get("name", ""),
                "latitude": raw.get("latitude"),
                "longitude": raw.get("longitude"),
                "timezone": raw.get("timezone", "auto"),
                "country": raw.get("country", ""),
                "admin1": raw.get("admin1", ""),
                "location_id": raw.get("id"),
            }
        )
        if location is not None:
            locations.append(location)
    return tuple(locations)


class _BaseClient(QObject):
    def __init__(
        self,
        manager: QNetworkAccessManager | None = None,
        *,
        timeout_ms: int = 10000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager or QNetworkAccessManager(self)
        self._timeout_ms = max(1000, int(timeout_ms))
        self._reply: QNetworkReply | None = None
        self._request_id = 0

    def _begin(self, url: str) -> tuple[QNetworkReply, int] | None:
        self.cancel()
        self._request_id += 1
        request_id = self._request_id
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", USER_AGENT.encode("ascii", "ignore"))
        request.setTransferTimeout(self._timeout_ms)
        reply = self._manager.get(request)
        self._reply = reply
        reply.finished.connect(lambda: self._finished(request_id, reply))
        return reply, request_id

    def cancel(self) -> None:
        self._request_id += 1
        reply = self._reply
        self._reply = None
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _finished(self, request_id: int, reply: QNetworkReply) -> None:
        if request_id != self._request_id:
            reply.deleteLater()
            return
        self._reply = None
        try:
            self._handle(reply)
        finally:
            reply.deleteLater()

    def _handle(self, reply: QNetworkReply) -> None:
        raise NotImplementedError

    @staticmethod
    def _read_json(reply: QNetworkReply) -> dict[str, Any]:
        raw = bytes(reply.readAll())
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WeatherDataError("پاسخ سرویس هوا قابل خواندن نیست.") from exc
        if not isinstance(payload, dict):
            raise WeatherDataError("ساختار پاسخ سرویس هوا معتبر نیست.")
        return payload

    @staticmethod
    def _http_error(reply: QNetworkReply) -> str | None:
        error = reply.error()
        if error == QNetworkReply.NetworkError.NoError:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if status is not None and int(status) >= 400:
                return f"سرویس هوا پاسخ {int(status)} داد."
            return None
        if error == QNetworkReply.NetworkError.OperationCanceledError:
            return ""
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status is not None and int(status) >= 400:
            return f"سرویس هوا پاسخ {int(status)} داد."
        return "اتصال به سرویس هوا ممکن نشد."


class OpenMeteoForecastClient(_BaseClient):
    finished = Signal(object)  # WeatherSnapshot
    failed = Signal(str)

    def __init__(
        self,
        manager: QNetworkAccessManager | None = None,
        *,
        timeout_ms: int = 10000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(manager, timeout_ms=timeout_ms, parent=parent)
        self._pending: tuple[WeatherLocation, str, str] | None = None

    def request(
        self,
        location: WeatherLocation,
        temperature_unit: str = "celsius",
        wind_speed_unit: str = "kmh",
        *,
        forecast_days: int = 5,
    ) -> None:
        if not location.is_valid:
            self.failed.emit("مختصات شهر انتخاب‌شده معتبر نیست.")
            return
        self._pending = (
            location,
            normalize_temperature_unit(temperature_unit),
            normalize_wind_speed_unit(wind_speed_unit),
        )
        self._begin(
            build_forecast_url(
                location,
                temperature_unit,
                wind_speed_unit,
                forecast_days=forecast_days,
            )
        )

    def _handle(self, reply: QNetworkReply) -> None:
        error = self._http_error(reply)
        if error:
            self.failed.emit(error)
            return
        if self._pending is None:
            self.failed.emit("درخواست هوا ناقص است.")
            return
        location, temperature_unit, wind_speed_unit = self._pending
        try:
            payload = self._read_json(reply)
            snapshot = parse_forecast_payload(
                payload,
                location,
                temperature_unit,
                wind_speed_unit,
            )
        except WeatherDataError as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(snapshot)


class OpenMeteoGeocodingClient(_BaseClient):
    resultsReady = Signal(object)  # tuple[WeatherLocation, ...]
    searchFailed = Signal(str)

    def search(self, query: str) -> None:
        text = str(query).strip()
        if len(text) < 2:
            self.cancel()
            self.resultsReady.emit(())
            return
        self._begin(build_geocoding_url(text))

    def _handle(self, reply: QNetworkReply) -> None:
        error = self._http_error(reply)
        if error:
            self.searchFailed.emit(error)
            return
        try:
            payload = self._read_json(reply)
            results = parse_geocoding_payload(payload)
        except WeatherDataError as exc:
            self.searchFailed.emit(str(exc))
            return
        self.resultsReady.emit(results)
