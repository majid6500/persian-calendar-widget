"""Persian descriptions and icon families for WMO weather codes."""

from __future__ import annotations

WMO_DESCRIPTIONS = {
    0: "صاف",
    1: "عمدتاً صاف",
    2: "نیمه‌ابری",
    3: "ابری",
    45: "مه",
    48: "مه یخ‌زده",
    51: "نم‌نم باران سبک",
    53: "نم‌نم باران",
    55: "نم‌نم باران شدید",
    56: "نم‌نم باران یخ‌زده",
    57: "نم‌نم باران یخ‌زده شدید",
    61: "باران سبک",
    63: "باران",
    65: "باران شدید",
    66: "باران یخ‌زده",
    67: "باران یخ‌زده شدید",
    71: "برف سبک",
    73: "برف",
    75: "برف سنگین",
    77: "دانه‌های برف",
    80: "رگبار سبک",
    81: "رگبار",
    82: "رگبار شدید",
    85: "رگبار برف سبک",
    86: "رگبار برف سنگین",
    95: "رعد و برق",
    96: "رعد و برق با تگرگ",
    97: "رعد و برق شدید",
    99: "رعد و برق شدید با تگرگ",
}


def condition_text(code: int | None) -> str:
    if code is None:
        return "نامشخص"
    return WMO_DESCRIPTIONS.get(int(code), "نامشخص")


def condition_kind(code: int | None, is_day: bool = True) -> str:
    """Return a small, paint-friendly icon family."""
    if code is None:
        return "cloudy"
    code = int(code)
    if code == 0:
        return "clear" if is_day else "clear-night"
    if code in (1, 2):
        return "partly" if is_day else "partly-night"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (80, 81, 82):
        return "showers"
    if code in (95, 96, 97, 99):
        return "thunder"
    return "cloudy"
