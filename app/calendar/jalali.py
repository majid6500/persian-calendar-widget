"""Jalali (Persian) calendar arithmetic.

All date math is delegated to :mod:`jdatetime`; this module only wraps it with
explicit, testable helpers and the week layout used by the UI.  The internal
representation is ``jdatetime.date`` (a Jalali date), never a formatted string.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Iterable

import jdatetime

JalaliDate = jdatetime.date

# The widget is usable far beyond the bundled holiday data; these bounds only
# protect against nonsensical values coming from persistence or the UI.
MIN_YEAR = 1200
MAX_YEAR = 1600

SATURDAY = 0
FRIDAY = 6
WEEK_LENGTH = 7
WEEKS_IN_GRID = 6
DAYS_IN_GRID = WEEK_LENGTH * WEEKS_IN_GRID


def today() -> JalaliDate:
    """Today according to the operating system's local time."""
    return jdatetime.date.today()


def from_gregorian(value: _dt.date) -> JalaliDate:
    return jdatetime.date.fromgregorian(date=value)


def to_gregorian(value: JalaliDate) -> _dt.date:
    return value.togregorian()


def is_valid(year: int, month: int, day: int) -> bool:
    if not (MIN_YEAR <= int(year) <= MAX_YEAR):
        return False
    if not (1 <= int(month) <= 12):
        return False
    if not (1 <= int(day) <= month_length(int(year), int(month))):
        return False
    try:
        jdatetime.date(int(year), int(month), int(day))
    except (ValueError, TypeError):
        return False
    return True


def is_leap(year: int) -> bool:
    """True when the Jalali year has 366 days (Esfand has 30 days)."""
    return bool(jdatetime.date(int(year), 1, 1).isleap())


def month_length(year: int, month: int) -> int:
    month = int(month)
    if not 1 <= month <= 12:
        raise ValueError(f"month out of range: {month}")
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if is_leap(int(year)) else 29


def month_name_index(value: JalaliDate) -> int:
    return value.month


def weekday_index(value: JalaliDate) -> int:
    """Weekday index with Saturday = 0 ... Friday = 6."""
    return value.weekday()


def is_friday(value: JalaliDate) -> bool:
    return weekday_index(value) == FRIDAY


def add_days(value: JalaliDate, days: int) -> JalaliDate:
    if not days:
        return value
    return JalaliDate.fromordinal(value.toordinal() + int(days))


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    if not 1 <= int(month) <= 12:
        raise ValueError(f"month out of range: {month}")
    total = int(year) * 12 + (int(month) - 1) + int(delta)
    new_year, new_month0 = divmod(total, 12)
    return new_year, new_month0 + 1


def first_of_month(year: int, month: int) -> JalaliDate:
    return jdatetime.date(int(year), int(month), 1)


def last_of_month(year: int, month: int) -> JalaliDate:
    return jdatetime.date(int(year), int(month), month_length(year, month))


def to_iso(value: JalaliDate) -> str:
    return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"


def parse_iso(text: str) -> JalaliDate:
    parts = str(text).strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"invalid Jalali ISO date: {text!r}")
    year, month, day = (int(p) for p in parts)
    if not is_valid(year, month, day):
        raise ValueError(f"invalid Jalali date: {text!r}")
    return jdatetime.date(year, month, day)


@dataclass(frozen=True)
class MonthGrid:
    year: int
    month: int
    first_weekday: int
    weeks: tuple[tuple[JalaliDate, ...], ...]

    @property
    def days(self) -> tuple[JalaliDate, ...]:
        return tuple(day for week in self.weeks for day in week)

    @property
    def in_month(self) -> tuple[JalaliDate, ...]:
        return tuple(
            day
            for day in self.days
            if day.year == self.year and day.month == self.month
        )


def month_grid(year: int, month: int) -> MonthGrid:
    """Return a fixed 6x7 grid starting on Saturday.

    Leading/trailing cells belong to the previous/next month, mirroring the
    layout of an Iranian wall calendar.
    """
    first = first_of_month(year, month)
    offset = weekday_index(first)
    start = add_days(first, -offset)
    weeks: list[tuple[JalaliDate, ...]] = []
    for row in range(WEEKS_IN_GRID):
        weeks.append(
            tuple(add_days(start, row * WEEK_LENGTH + col) for col in range(WEEK_LENGTH))
        )
    return MonthGrid(int(year), int(month), offset, tuple(weeks))


def iter_days(start: JalaliDate, end: JalaliDate) -> Iterable[JalaliDate]:
    current = start
    while current <= end:
        yield current
        current = add_days(current, 1)


def clamp_day(year: int, month: int, day: int) -> int:
    return max(1, min(int(day), month_length(year, month)))


def gregorian_span(year: int, month: int) -> tuple[_dt.date, _dt.date]:
    """First and last Gregorian dates covered by a Jalali month."""
    return to_gregorian(first_of_month(year, month)), to_gregorian(
        last_of_month(year, month)
    )
