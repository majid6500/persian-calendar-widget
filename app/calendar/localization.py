"""Persian labels, numerals and display formatting.

Presentation-only module: calendar math lives in :mod:`app.calendar.jalali`.
"""

from __future__ import annotations

import datetime as _dt

from app.calendar.jalali import JalaliDate, gregorian_span, weekday_index

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_LATIN_TO_PERSIAN = str.maketrans("0123456789", PERSIAN_DIGITS)
_PERSIAN_TO_LATIN = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
)

MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

WEEKDAY_NAMES = (
    "شنبه",
    "یک‌شنبه",
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
)

WEEKDAY_SHORT = ("ش", "ی", "د", "س", "چ", "پ", "ج")

GREGORIAN_MONTH_NAMES = (
    "ژانویه",
    "فوریه",
    "مارس",
    "آوریل",
    "مه",
    "ژوئن",
    "ژوئیه",
    "اوت",
    "سپتامبر",
    "اکتبر",
    "نوامبر",
    "دسامبر",
)

CATEGORY_LABELS = {
    "national": "ملی",
    "religious": "مذهبی",
    "cultural": "فرهنگی",
    "historical": "تاریخی",
    "ancient": "آیین کهن",
    "civic": "اجتماعی",
}


def to_persian_digits(value: object) -> str:
    return str(value).translate(_LATIN_TO_PERSIAN)


def to_latin_digits(value: object) -> str:
    return str(value).translate(_PERSIAN_TO_LATIN)


def number(value: int) -> str:
    return to_persian_digits(f"{int(value):d}")


def number_padded(value: int, width: int = 2) -> str:
    return to_persian_digits(f"{int(value):0{width}d}")


def month_name(month: int) -> str:
    return MONTH_NAMES[int(month) - 1]


def weekday_name(index: int) -> str:
    return WEEKDAY_NAMES[int(index) % 7]


def weekday_short(index: int) -> str:
    return WEEKDAY_SHORT[int(index) % 7]


def weekday_of(value: JalaliDate) -> str:
    return weekday_name(weekday_index(value))


def month_year(value: JalaliDate) -> str:
    return f"{month_name(value.month)} {number(value.year)}"


def day_number(value: JalaliDate) -> str:
    return number(value.day)


def jalali_text(value: JalaliDate, include_year: bool = True) -> str:
    if include_year:
        return f"{number(value.day)} {month_name(value.month)} {number(value.year)}"
    return f"{number(value.day)} {month_name(value.month)}"


def long_date(value: JalaliDate) -> str:
    return f"{weekday_of(value)} {number(value.day)} {month_name(value.month)} {number(value.year)}"


def gregorian_text(value: _dt.date, include_year: bool = True) -> str:
    month = GREGORIAN_MONTH_NAMES[value.month - 1]
    if include_year:
        return f"{number(value.day)} {month} {number(value.year)}"
    return f"{number(value.day)} {month}"


def gregorian_month_year(value: _dt.date) -> str:
    return f"{GREGORIAN_MONTH_NAMES[value.month - 1]} {number(value.year)}"


def gregorian_month_span(year: int, month: int) -> str:
    """The Gregorian month(s) covered by a Jalali month, in Persian."""
    first, last = gregorian_span(year, month)
    name_first = GREGORIAN_MONTH_NAMES[first.month - 1]
    name_last = GREGORIAN_MONTH_NAMES[last.month - 1]
    if first.year == last.year and first.month == last.month:
        return f"{name_first} {number(first.year)}"
    if first.year == last.year:
        return f"{name_first} – {name_last} {number(first.year)}"
    return (
        f"{name_first} {number(first.year)} – "
        f"{name_last} {number(last.year)}"
    )


def clock_text(value: _dt.datetime, seconds: bool = True) -> str:
    if seconds:
        raw = f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    else:
        raw = f"{value.hour:02d}:{value.minute:02d}"
    return to_persian_digits(raw)


def clock_parts(value: _dt.datetime) -> tuple[str, str]:
    """Return (HH:MM, SS) in Persian digits for the floating widget."""
    return (
        to_persian_digits(f"{value.hour:02d}:{value.minute:02d}"),
        to_persian_digits(f"{value.second:02d}"),
    )


def percent_text(value: int) -> str:
    return f"{number(value)}٪"


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, "مناسبت")


def day_progress(value: _dt.datetime) -> float:
    """Fraction of the current local day that has elapsed (0..1)."""
    seconds = value.hour * 3600 + value.minute * 60 + value.second
    return max(0.0, min(1.0, seconds / 86400.0))
