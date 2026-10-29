"""Locally bundled Iranian holidays and occasions.

The data file is deliberately separate from application logic.  A missing or
malformed file must never crash the UI: the service exposes ``load_error`` and
simply returns no events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.calendar import jalali
from app.calendar.jalali import JalaliDate

DEFAULT_DATA_FILE = Path("data") / "holidays" / "holidays.json"


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    title: str
    category: str
    official: bool
    description: str = ""
    source: str = ""

    @property
    def kind_label(self) -> str:
        return "تعطیل رسمی" if self.official else "مناسبت"


@dataclass(frozen=True)
class Coverage:
    min_year: int
    max_year: int

    def contains(self, year: int) -> bool:
        return self.min_year <= int(year) <= self.max_year


class HolidayService:
    """Loads and queries the bundled dataset.

    ``holidays`` are year-specific official dates; ``occasions`` are fixed
    month/day events that recur every year.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from app.core.paths import data_path

            path = data_path("holidays", "holidays.json")
        self.path = Path(path)
        self.load_error: str | None = None
        self.coverage: Coverage | None = None
        self.skipped_entries = 0
        self._holidays: dict[str, tuple[CalendarEvent, ...]] = {}
        self._occasions: dict[tuple[int, int], tuple[CalendarEvent, ...]] = {}
        self._load()

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        if not self.path.is_file():
            self.load_error = f"فایل داده تعطیلات یافت نشد: {self.path}"
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.load_error = f"خواندن داده تعطیلات ممکن نشد: {exc}"
            return
        if not isinstance(payload, dict):
            self.load_error = "ساختار داده تعطیلات معتبر نیست."
            return

        coverage = payload.get("coverage")
        if isinstance(coverage, dict):
            try:
                self.coverage = Coverage(
                    int(coverage["min_year"]), int(coverage["max_year"])
                )
            except (KeyError, TypeError, ValueError):
                self.coverage = None

        holidays = payload.get("holidays", [])
        occasions = payload.get("occasions", [])
        if not isinstance(holidays, list) or not isinstance(occasions, list):
            self.load_error = "فهرست تعطیلات یا مناسبت‌ها معتبر نیست."
            return

        holiday_map: dict[str, list[CalendarEvent]] = {}
        for raw in holidays:
            parsed_holiday = self._parse_holiday(raw)
            if parsed_holiday is None:
                self.skipped_entries += 1
                continue
            date_text, event = parsed_holiday
            holiday_map.setdefault(date_text, []).append(event)

        occasion_map: dict[tuple[int, int], list[CalendarEvent]] = {}
        for raw in occasions:
            parsed = self._parse_occasion(raw)
            if parsed is None:
                self.skipped_entries += 1
                continue
            key, event = parsed
            occasion_map.setdefault(key, []).append(event)

        self._holidays = {
            key: self._dedupe(values) for key, values in holiday_map.items()
        }
        self._occasions = {
            key: self._dedupe(values) for key, values in occasion_map.items()
        }

        if self.coverage is None:
            years = [
                int(key[:4])
                for key in self._holidays
                if len(key) >= 4 and key[:4].isdigit()
            ]
            if years:
                self.coverage = Coverage(min(years), max(years))

    @staticmethod
    def _dedupe(events: list[CalendarEvent]) -> tuple[CalendarEvent, ...]:
        seen: set[tuple[str, str]] = set()
        result: list[CalendarEvent] = []
        for event in events:
            key = (event.id, event.title)
            if key in seen:
                continue
            seen.add(key)
            result.append(event)
        return tuple(result)

    @staticmethod
    def _base_event(raw: dict, *, official: bool) -> CalendarEvent | None:
        if not isinstance(raw, dict):
            return None
        title = str(raw.get("title", "")).strip()
        if not title:
            return None
        return CalendarEvent(
            id=str(raw.get("id", title)).strip(),
            title=title,
            category=str(raw.get("category", "national")).strip() or "national",
            official=official,
            description=str(raw.get("description", "")).strip(),
            source=str(raw.get("source", "")).strip(),
        )

    def _parse_holiday(
        self, raw: object
    ) -> tuple[str, CalendarEvent] | None:
        if not isinstance(raw, dict):
            return None
        try:
            date_text = str(raw["date"]).strip()
            jalali.parse_iso(date_text)
        except (KeyError, TypeError, ValueError):
            return None
        event = self._base_event(raw, official=True)
        if event is None:
            return None
        return date_text, event

    def _parse_occasion(
        self, raw: object
    ) -> tuple[tuple[int, int], CalendarEvent] | None:
        if not isinstance(raw, dict):
            return None
        event = self._base_event(raw, official=False)
        if event is None:
            return None
        try:
            month = int(raw["month"])
            day = int(raw["day"])
        except (KeyError, TypeError, ValueError):
            return None
        if not 1 <= month <= 12 or not 1 <= day <= jalali.month_length(1403, month):
            return None
        return (month, day), event

    # --------------------------------------------------------------- queries
    @property
    def is_loaded(self) -> bool:
        return self.load_error is None

    @property
    def event_count(self) -> int:
        return sum(len(v) for v in self._holidays.values()) + sum(
            len(v) for v in self._occasions.values()
        )

    @property
    def holiday_count(self) -> int:
        return sum(len(v) for v in self._holidays.values())

    @property
    def occasion_day_count(self) -> int:
        """Number of distinct month/day keys that carry occasions."""
        return len(self._occasions)

    @property
    def occasion_entry_count(self) -> int:
        return sum(len(v) for v in self._occasions.values())

    def has_coverage(self, year: int) -> bool:
        return self.coverage is not None and self.coverage.contains(year)

    def events_on(self, value: JalaliDate) -> tuple[CalendarEvent, ...]:
        official = self._holidays.get(jalali.to_iso(value), ())
        occasions = self._occasions.get((value.month, value.day), ())
        if not occasions:
            return official
        return self._dedupe([*official, *occasions])

    def holidays_on(self, value: JalaliDate) -> tuple[CalendarEvent, ...]:
        return self._holidays.get(jalali.to_iso(value), ())

    def occasions_on(self, value: JalaliDate) -> tuple[CalendarEvent, ...]:
        return self._occasions.get((value.month, value.day), ())

    def is_holiday(self, value: JalaliDate) -> bool:
        return bool(self.holidays_on(value))

    def is_weekly_holiday(self, value: JalaliDate) -> bool:
        return jalali.is_friday(value)

    def is_day_off(self, value: JalaliDate) -> bool:
        return self.is_holiday(value) or self.is_weekly_holiday(value)
