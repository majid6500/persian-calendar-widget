"""Calendar arithmetic and month-grid tests."""

from __future__ import annotations

import datetime as dt

import jdatetime
import pytest

from app.calendar import jalali


def test_known_jalali_gregorian_conversions() -> None:
    assert jalali.from_gregorian(dt.date(2024, 3, 20)) == jdatetime.date(1403, 1, 1)
    assert jalali.to_gregorian(jdatetime.date(1403, 1, 1)) == dt.date(2024, 3, 20)
    assert jalali.to_gregorian(jdatetime.date(1405, 8, 5)) == dt.date(2026, 10, 27)


def test_jalali_weekdays_start_on_saturday() -> None:
    # 1403-01-01 is a Wednesday; Saturday=0 ... Friday=6.
    assert jalali.weekday_index(jdatetime.date(1403, 1, 1)) == 4
    assert jalali.weekday_index(jdatetime.date(1403, 1, 4)) == 0
    assert jalali.is_friday(jdatetime.date(1405, 8, 8))
    assert not jalali.is_friday(jdatetime.date(1405, 8, 7))


@pytest.mark.parametrize(
    ("year", "month", "expected"),
    [
        (1403, 1, 31),
        (1403, 6, 31),
        (1403, 7, 30),
        (1403, 11, 30),
        (1403, 12, 30),  # 1403 is a leap year
        (1404, 12, 29),
        (1408, 12, 30),
    ],
)
def test_month_lengths(year: int, month: int, expected: int) -> None:
    assert jalali.month_length(year, month) == expected


@pytest.mark.parametrize("month", [0, 13, -1])
def test_month_length_rejects_invalid_month(month: int) -> None:
    with pytest.raises(ValueError):
        jalali.month_length(1403, month)


def test_add_months_across_year_boundaries() -> None:
    assert jalali.add_months(1403, 12, 1) == (1404, 1)
    assert jalali.add_months(1404, 1, -1) == (1403, 12)
    assert jalali.add_months(1403, 6, 6) == (1403, 12)
    assert jalali.add_months(1403, 1, 0) == (1403, 1)
    assert jalali.add_months(1403, 1, -13) == (1401, 12)


def test_add_days_crosses_month_and_year() -> None:
    assert jalali.add_days(jdatetime.date(1403, 12, 29), 1) == jdatetime.date(
        1403, 12, 30
    )
    assert jalali.add_days(jdatetime.date(1403, 12, 30), 1) == jdatetime.date(
        1404, 1, 1
    )
    assert jalali.add_days(jdatetime.date(1404, 1, 1), -1) == jdatetime.date(
        1403, 12, 30
    )
    assert jalali.add_days(jdatetime.date(1404, 1, 1), 0) == jdatetime.date(
        1404, 1, 1
    )


def test_iso_round_trip_and_validation() -> None:
    value = jdatetime.date(1405, 8, 5)
    assert jalali.to_iso(value) == "1405-08-05"
    assert jalali.parse_iso("1405-08-05") == value
    assert jalali.parse_iso(" 1405-8-5 ") == value
    with pytest.raises(ValueError):
        jalali.parse_iso("1405/08/05")
    with pytest.raises(ValueError):
        jalali.parse_iso("1404-12-30")  # 1404 is not a leap year
    with pytest.raises(ValueError):
        jalali.parse_iso("not-a-date")


def test_is_valid_bounds_and_leap_days() -> None:
    assert jalali.is_valid(1403, 1, 1)
    assert jalali.is_valid(1403, 12, 30)
    assert not jalali.is_valid(1404, 12, 30)
    assert not jalali.is_valid(1100, 1, 1)
    assert not jalali.is_valid(1700, 1, 1)
    assert not jalali.is_valid(1403, 13, 1)
    assert not jalali.is_valid(1403, 1, 0)
    assert not jalali.is_valid(1403, 1, 32)


def test_month_grid_starts_on_saturday_and_has_six_weeks() -> None:
    grid = jalali.month_grid(1403, 1)
    assert grid.year == 1403
    assert grid.month == 1
    assert len(grid.weeks) == 6
    assert len(grid.days) == 42
    assert all(len(week) == 7 for week in grid.weeks)
    assert grid.weeks[0][0].weekday() == jalali.SATURDAY
    assert grid.weeks[-1][-1].weekday() == jalali.FRIDAY
    assert len(grid.in_month) == 31
    assert grid.in_month[0] == jdatetime.date(1403, 1, 1)
    assert grid.in_month[-1] == jdatetime.date(1403, 1, 31)


def test_month_grid_leading_cells_belong_to_previous_month() -> None:
    grid = jalali.month_grid(1405, 8)
    # Aban 1405 starts on a Friday, so the grid starts on 25 Mehr.
    assert grid.first_weekday == jalali.FRIDAY
    assert grid.weeks[0][0] == jdatetime.date(1405, 7, 25)
    assert grid.weeks[0][6] == jdatetime.date(1405, 8, 1)
    assert len(grid.in_month) == 30
    # The fixed grid has six leading/trailing days around the 30-day month.
    assert grid.days[0] == jdatetime.date(1405, 7, 25)
    assert grid.days[-1] == jdatetime.date(1405, 9, 6)


def test_gregorian_span_for_month_and_cross_year() -> None:
    first, last = jalali.gregorian_span(1405, 8)
    assert first == dt.date(2026, 10, 23)
    assert last == dt.date(2026, 11, 21)

    first, last = jalali.gregorian_span(1403, 10)
    assert first == dt.date(2024, 12, 21)
    assert last == dt.date(2025, 1, 19)
    assert first.year != last.year


def test_clamp_day_for_esfand() -> None:
    assert jalali.clamp_day(1403, 12, 31) == 30
    assert jalali.clamp_day(1404, 12, 31) == 29
    assert jalali.clamp_day(1404, 1, 99) == 31
    assert jalali.clamp_day(1404, 1, 0) == 1


def test_iter_days_is_inclusive() -> None:
    days = list(
        jalali.iter_days(
            jdatetime.date(1404, 12, 28), jdatetime.date(1405, 1, 2)
        )
    )
    assert days == [
        jdatetime.date(1404, 12, 28),
        jdatetime.date(1404, 12, 29),
        jdatetime.date(1405, 1, 1),
        jdatetime.date(1405, 1, 2),
    ]
