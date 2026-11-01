"""Central mapping between weather data and bundled visual assets.

The mapping is deliberately independent from Qt and from the widget.  The UI
only receives a :class:`WeatherVisual` and never needs to know WMO codes or
asset filenames.  This keeps icon/background selection testable and prevents
the same condition logic from being repeated in different paint methods.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.paths import assets_path
from app.weather.models import WeatherSnapshot

logger = logging.getLogger(__name__)

CATEGORY_CLEAR = "clear"
CATEGORY_PARTLY = "partly"
CATEGORY_CLOUDY = "cloudy"
CATEGORY_FOG = "fog"
CATEGORY_RAIN = "rain"
CATEGORY_SNOW = "snow"
CATEGORY_STORM = "storm"

WEATHER_CATEGORIES = (
    CATEGORY_CLEAR,
    CATEGORY_PARTLY,
    CATEGORY_CLOUDY,
    CATEGORY_FOG,
    CATEGORY_RAIN,
    CATEGORY_SNOW,
    CATEGORY_STORM,
)

FALLBACK_CATEGORY = CATEGORY_CLOUDY
FALLBACK_ICON = "cloudy.svg"

ICON_DIR = "weather_icon_pack"
BACKGROUND_DIR = "weather_background_pack"
DETAIL_WIND_ICON = "wind.svg"
DETAIL_THERMOMETER_ICON = "thermometer.svg"
EXPECTED_ICON_COUNT = 24

# Exact names discovered in the supplied asset packs.  Keep the spaces and
# the .jpeg extension; Windows paths are case-insensitive but packaged Linux
# paths may not be, so the names are intentionally literal.
BACKGROUND_FILES: dict[tuple[str, bool], str] = {
    (CATEGORY_CLEAR, True): "Clear Day.jpeg",
    (CATEGORY_CLEAR, False): "Clear Night.jpeg",
    (CATEGORY_PARTLY, True): "Partly Cloudy Day.jpeg",
    (CATEGORY_PARTLY, False): "Partly Cloudy Night.jpeg",
    (CATEGORY_CLOUDY, True): "Cloudy Day.jpeg",
    (CATEGORY_CLOUDY, False): "Cloudy Night.jpeg",
    (CATEGORY_FOG, True): "Foggy Day.jpeg",
    (CATEGORY_FOG, False): "Foggy Night.jpeg",
    (CATEGORY_RAIN, True): "Rainy Day.jpeg",
    (CATEGORY_RAIN, False): "Rainy Night.jpeg",
    (CATEGORY_SNOW, True): "Snowy Day.jpeg",
    (CATEGORY_SNOW, False): "Snowy Night.jpeg",
    (CATEGORY_STORM, True): "Stormy Day.jpeg",
    (CATEGORY_STORM, False): "Stormy Night.jpeg",
}

# WMO codes in the ranges used by Open-Meteo.  Code 97 is not in the official
# WMO table but was already handled by the project and is kept for backwards
# compatibility with cached/legacy responses.
ICON_DAY_FILES: dict[int, str] = {
    0: "sunny.svg",
    1: "partly_cloudy_large.svg",
    2: "partly_cloudy.svg",
    3: "overcast.svg",
    45: "fog.svg",
    48: "fog.svg",
    51: "light_precipitation.svg",
    53: "light_precipitation.svg",
    55: "moderate_rain.svg",
    56: "sleet.svg",
    57: "sleet.svg",
    61: "light_rain.svg",
    63: "moderate_rain.svg",
    65: "heavy_rain.svg",
    66: "sleet.svg",
    67: "sleet.svg",
    71: "snow.svg",
    73: "snow.svg",
    75: "snow.svg",
    77: "snow.svg",
    80: "partly_cloudy_rain.svg",
    81: "moderate_rain.svg",
    82: "heavy_rain.svg",
    85: "partly_cloudy_snow.svg",
    86: "snow.svg",
    95: "thunderstorm.svg",
    96: "hail.svg",
    97: "thunderstorm_heavy.svg",
    99: "thunderstorm_heavy.svg",
}

# Only clear and partly-cloudy have dedicated night artwork in the icon pack.
# The remaining night indication is carried by the background, so those codes
# keep their daytime icon.
NIGHT_ICON_OVERRIDES: dict[int, str] = {
    0: "clear_night.svg",
    1: "partly_cloudy_night.svg",
    2: "partly_cloudy_night.svg",
}


@dataclass(frozen=True)
class WeatherVisual:
    """Resolved artwork for one weather observation."""

    category: str
    is_day: bool
    background_path: Path | None
    icon_path: Path | None
    background_name: str
    icon_name: str


@dataclass(frozen=True)
class AssetReport:
    """Result of the local asset validation used by tests and diagnostics."""

    background_count: int
    icon_count: int
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing


def normalize_code(value: object) -> int | None:
    """Return an integer WMO code, or ``None`` for missing/invalid input."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def weather_category(code: int | None) -> str:
    """Normalize a WMO code to one of the seven visual categories."""
    code = normalize_code(code)
    if code is None:
        return FALLBACK_CATEGORY
    if code == 0:
        return CATEGORY_CLEAR
    if code in (1, 2):
        return CATEGORY_PARTLY
    if code == 3:
        return CATEGORY_CLOUDY
    if code in (45, 48):
        return CATEGORY_FOG
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return CATEGORY_RAIN
    if code in (71, 73, 75, 77, 85, 86):
        return CATEGORY_SNOW
    if code in (95, 96, 97, 99):
        return CATEGORY_STORM
    return FALLBACK_CATEGORY


def background_filename(category: str, is_day: bool) -> str:
    """Return the exact background filename for a category and lighting."""
    key = (category, bool(is_day))
    return BACKGROUND_FILES.get(
        key, BACKGROUND_FILES[(FALLBACK_CATEGORY, bool(is_day))]
    )


def icon_filename(code: int | None, is_day: bool = True) -> str:
    """Return the most specific available SVG icon for a WMO code."""
    code = normalize_code(code)
    if code is None:
        return FALLBACK_ICON
    if not is_day and code in NIGHT_ICON_OVERRIDES:
        return NIGHT_ICON_OVERRIDES[code]
    return ICON_DAY_FILES.get(code, FALLBACK_ICON)


def background_path(category: str, is_day: bool) -> Path:
    return assets_path(BACKGROUND_DIR, background_filename(category, is_day))


def icon_path(code: int | None, is_day: bool = True) -> Path:
    return assets_path(ICON_DIR, icon_filename(code, is_day))


def detail_icon_path(filename: str) -> Path:
    """Path for a small metric icon (wind, thermometer) from the same pack."""
    return assets_path(ICON_DIR, filename)


def resolve_visual(code: int | None, is_day: bool = True) -> WeatherVisual:
    """Resolve a code/lighting pair, falling back for missing files.

    A missing requested asset is replaced with the cloudy fallback for the
    same lighting state.  If even the fallback is unavailable, the path is
    ``None`` so the widget can keep its previous valid artwork or paint its
    existing neutral background.
    """
    category = weather_category(code)
    day = bool(is_day)
    selected_background = background_filename(category, day)
    selected_icon = icon_filename(code, day)

    background = assets_path(BACKGROUND_DIR, selected_background)
    if not background.is_file():
        logger.warning("Weather background is missing: %s", background)
        selected_background = background_filename(FALLBACK_CATEGORY, day)
        background = assets_path(BACKGROUND_DIR, selected_background)

    icon = assets_path(ICON_DIR, selected_icon)
    if not icon.is_file():
        logger.warning("Weather icon is missing: %s", icon)
        selected_icon = FALLBACK_ICON
        icon = assets_path(ICON_DIR, selected_icon)

    return WeatherVisual(
        category=category,
        is_day=day,
        background_path=background if background.is_file() else None,
        icon_path=icon if icon.is_file() else None,
        background_name=selected_background,
        icon_name=selected_icon,
    )


def visual_from_snapshot(snapshot: WeatherSnapshot | None) -> WeatherVisual | None:
    if snapshot is None:
        return None
    return resolve_visual(snapshot.weather_code, snapshot.is_day)


def all_background_paths() -> tuple[Path, ...]:
    folder = assets_path(BACKGROUND_DIR)
    return tuple(sorted(folder.glob("*.jpeg")))


def all_icon_paths() -> tuple[Path, ...]:
    folder = assets_path(ICON_DIR)
    return tuple(sorted(folder.glob("*.svg")))


def validate_assets() -> AssetReport:
    """Check that every supplied asset is present and that mappings resolve."""
    backgrounds = all_background_paths()
    icons = all_icon_paths()
    missing: list[str] = []

    if len(backgrounds) != len(BACKGROUND_FILES):
        missing.append(
            f"background count {len(backgrounds)} != {len(BACKGROUND_FILES)}"
        )
    if len(icons) != EXPECTED_ICON_COUNT:
        missing.append(
            f"icon count {len(icons)} != {EXPECTED_ICON_COUNT}"
        )

    for filename in BACKGROUND_FILES.values():
        path = assets_path(BACKGROUND_DIR, filename)
        if not path.is_file():
            missing.append(str(path))

    for filename in set(ICON_DAY_FILES.values()) | set(NIGHT_ICON_OVERRIDES.values()):
        path = assets_path(ICON_DIR, filename)
        if not path.is_file():
            missing.append(str(path))

    return AssetReport(
        background_count=len(backgrounds),
        icon_count=len(icons),
        missing=tuple(missing),
    )
