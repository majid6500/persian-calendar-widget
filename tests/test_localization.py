"""Persian display formatting tests."""

from __future__ import annotations

import datetime as dt

import jdatetime

from app.calendar import localization as loc


def test_digit_conversion() -> None:
    assert loc.to_persian_digits("1405-08-05") == "۱۴۰۵-۰۸-۰۵"
    assert loc.to_persian_digits(1405) == "۱۴۰۵"
    assert loc.to_latin_digits("۱۴۰۵/۰۸/۰۵") == "1405/08/05"
    # Arabic-Indic digits are accepted as well as Persian digits.
    assert loc.to_latin_digits("١٤٠٥") == "1405"
    assert loc.number(1405) == "۱۴۰۵"
    assert loc.number_padded(5) == "۰۵"
    assert loc.number_padded(5, 3) == "۰۰۵"


def test_month_and_weekday_names() -> None:
    assert loc.month_name(1) == "فروردین"
    assert loc.month_name(12) == "اسفند"
    assert loc.weekday_name(0) == "شنبه"
    assert loc.weekday_name(6) == "جمعه"
    assert loc.weekday_short(0) == "ش"
    assert loc.weekday_short(6) == "ج"
    assert loc.weekday_of(jdatetime.date(1405, 8, 5)) == "سه‌شنبه"
    assert loc.weekday_of(jdatetime.date(1405, 8, 8)) == "جمعه"


def test_jalali_labels() -> None:
    value = jdatetime.date(1405, 8, 5)
    assert loc.month_year(value) == "آبان ۱۴۰۵"
    assert loc.day_number(value) == "۵"
    assert loc.jalali_text(value) == "۵ آبان ۱۴۰۵"
    assert loc.jalali_text(value, include_year=False) == "۵ آبان"
    assert loc.long_date(value) == "سه‌شنبه ۵ آبان ۱۴۰۵"


def test_gregorian_labels() -> None:
    value = dt.date(2026, 10, 27)
    assert loc.gregorian_text(value) == "۲۷ اکتبر ۲۰۲۶"
    assert loc.gregorian_text(value, include_year=False) == "۲۷ اکتبر"
    assert loc.gregorian_month_year(value) == "اکتبر ۲۰۲۶"
    assert loc.gregorian_month_span(1405, 8) == "اکتبر – نوامبر ۲۰۲۶"
    assert (
        loc.gregorian_month_span(1403, 10)
        == "دسامبر ۲۰۲۴ – ژانویه ۲۰۲۵"
    )
    assert loc.gregorian_month_span(1404, 1) == "مارس – آوریل ۲۰۲۵"


def test_clock_and_percent_formatting() -> None:
    now = dt.datetime(2026, 10, 27, 9, 5, 3)
    assert loc.clock_text(now) == "۰۹:۰۵:۰۳"
    assert loc.clock_text(now, seconds=False) == "۰۹:۰۵"
    assert loc.clock_parts(now) == ("۰۹:۰۵", "۰۳")
    assert loc.percent_text(94) == "۹۴٪"


def test_category_labels() -> None:
    assert loc.category_label("national") == "ملی"
    assert loc.category_label("religious") == "مذهبی"
    assert loc.category_label("unknown-category") == "مناسبت"


def test_day_progress_is_clamped() -> None:
    assert loc.day_progress(dt.datetime(2026, 1, 1, 0, 0, 0)) == 0.0
    assert loc.day_progress(dt.datetime(2026, 1, 1, 12, 0, 0)) == 0.5
    assert 0.99 < loc.day_progress(dt.datetime(2026, 1, 1, 23, 59, 59)) < 1.0
    assert loc.day_progress(dt.datetime(2026, 1, 1, 23, 59, 59)) <= 1.0
