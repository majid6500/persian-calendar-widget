"""Weather visual mapping, asset discovery and widget integration tests."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from PySide6.QtCore import QSize

from app.storage.settings import SettingsValues
from app.weather import visuals
from app.weather.art import WeatherArt
from app.weather.models import DailyForecast, WeatherLocation, WeatherSnapshot, WeatherState
from app.weather.visuals import (
    BACKGROUND_FILES,
    CATEGORY_CLEAR,
    CATEGORY_CLOUDY,
    CATEGORY_FOG,
    CATEGORY_PARTLY,
    CATEGORY_RAIN,
    CATEGORY_SNOW,
    CATEGORY_STORM,
    ICON_DAY_FILES,
    WEATHER_CATEGORIES,
    background_filename,
    icon_filename,
    resolve_visual,
    validate_assets,
    weather_category,
)
from app.widgets.floating_widget import FloatingWidget

LOCATION = WeatherLocation(
    "تهران", 35.7, 51.4, "Asia/Tehran", "ایران", "تهران", 112931
)

EXPECTED_CATEGORIES = {
    0: CATEGORY_CLEAR,
    1: CATEGORY_PARTLY,
    2: CATEGORY_PARTLY,
    3: CATEGORY_CLOUDY,
    45: CATEGORY_FOG,
    48: CATEGORY_FOG,
    51: CATEGORY_RAIN,
    53: CATEGORY_RAIN,
    55: CATEGORY_RAIN,
    56: CATEGORY_RAIN,
    57: CATEGORY_RAIN,
    61: CATEGORY_RAIN,
    63: CATEGORY_RAIN,
    65: CATEGORY_RAIN,
    66: CATEGORY_RAIN,
    67: CATEGORY_RAIN,
    71: CATEGORY_SNOW,
    73: CATEGORY_SNOW,
    75: CATEGORY_SNOW,
    77: CATEGORY_SNOW,
    80: CATEGORY_RAIN,
    81: CATEGORY_RAIN,
    82: CATEGORY_RAIN,
    85: CATEGORY_SNOW,
    86: CATEGORY_SNOW,
    95: CATEGORY_STORM,
    96: CATEGORY_STORM,
    97: CATEGORY_STORM,
    99: CATEGORY_STORM,
}


@pytest.mark.parametrize("code,expected", sorted(EXPECTED_CATEGORIES.items()))
def test_every_supported_wmo_code_maps_to_expected_category(code, expected) -> None:
    assert weather_category(code) == expected


@pytest.mark.parametrize("code", [None, -1, 100, "not-a-code", "999"])
def test_unknown_or_missing_codes_use_safe_cloudy_fallback(code) -> None:
    assert weather_category(code) == CATEGORY_CLOUDY


@pytest.mark.parametrize("category", WEATHER_CATEGORIES)
@pytest.mark.parametrize("is_day", [True, False])
def test_all_fourteen_backgrounds_are_mapped_and_present(category, is_day) -> None:
    filename = background_filename(category, is_day)
    assert filename == BACKGROUND_FILES[(category, is_day)]
    path = visuals.assets_path(visuals.BACKGROUND_DIR, filename)
    assert path.is_file(), path


def test_all_24_icons_are_discovered_and_all_mapped_icons_exist() -> None:
    icons = visuals.all_icon_paths()
    assert len(icons) == visuals.EXPECTED_ICON_COUNT == 24
    assert len(icons) == len({path.name for path in icons})
    for code, filename in ICON_DAY_FILES.items():
        path = visuals.assets_path(visuals.ICON_DIR, filename)
        assert path.is_file(), (code, path)
    for filename in visuals.NIGHT_ICON_OVERRIDES.values():
        path = visuals.assets_path(visuals.ICON_DIR, filename)
        assert path.is_file(), path


def test_asset_report_is_complete() -> None:
    report = validate_assets()
    assert report.background_count == 14
    assert report.icon_count == 24
    assert report.missing == ()
    assert report.ok is True


def test_all_supplied_assets_actually_decode(qapp) -> None:
    art = WeatherArt()
    assert art.validate_files() == ()


def test_clear_and_partly_cloudy_have_day_night_icon_variants() -> None:
    assert icon_filename(0, True) == "sunny.svg"
    assert icon_filename(0, False) == "clear_night.svg"
    assert icon_filename(1, True) == "partly_cloudy_large.svg"
    assert icon_filename(1, False) == "partly_cloudy_night.svg"
    assert icon_filename(2, True) == "partly_cloudy.svg"
    assert icon_filename(2, False) == "partly_cloudy_night.svg"


@pytest.mark.parametrize("code", [3, 45, 61, 71, 95])
def test_non_clear_codes_keep_their_icon_at_night(code) -> None:
    assert icon_filename(code, False) == icon_filename(code, True)


@pytest.mark.parametrize("code,is_day", [(0, True), (0, False), (61, True), (61, False)])
def test_resolved_icon_and_background_share_the_same_category(code, is_day) -> None:
    visual = resolve_visual(code, is_day)
    assert visual.category == weather_category(code)
    assert visual.is_day is is_day
    assert visual.background_name == background_filename(visual.category, is_day)
    assert visual.background_path is not None
    assert visual.icon_path is not None
    assert visual.background_path.is_file()
    assert visual.icon_path.is_file()


def test_missing_selected_assets_fall_back_to_cloudy(monkeypatch) -> None:
    real_assets_path = visuals.assets_path

    def fake_assets_path(*parts: str) -> Path:
        if parts and parts[-1] in {"Clear Day.jpeg", "sunny.svg"}:
            return Path("C:/definitely-missing") / parts[-1]
        return real_assets_path(*parts)

    monkeypatch.setattr(visuals, "assets_path", fake_assets_path)
    visual = resolve_visual(0, True)
    assert visual.background_name == "Cloudy Day.jpeg"
    assert visual.icon_name == "cloudy.svg"
    assert visual.background_path is not None and visual.background_path.is_file()
    assert visual.icon_path is not None and visual.icon_path.is_file()


def test_invalid_assets_are_rejected_without_crashing(qapp, tmp_path) -> None:
    art = WeatherArt()
    bad_svg = tmp_path / "bad.svg"
    bad_svg.write_text("not an svg", encoding="utf-8")
    bad_jpeg = tmp_path / "bad.jpeg"
    bad_jpeg.write_bytes(b"not a jpeg")

    assert art.renderer(bad_svg) is None
    assert art.background(bad_jpeg, QSize(32, 32)) is None
    assert art.background(None, QSize(32, 32)) is None
    assert art.renderer(None) is None


def _snapshot(
    code: int,
    *,
    is_day: bool,
    temperature: float = 21.8,
) -> WeatherSnapshot:
    now = dt.datetime.now().astimezone()
    daily = tuple(
        DailyForecast(
            date=(now + dt.timedelta(days=offset)).date(),
            weather_code=forecast_code,
            temp_max=24 - offset,
            temp_min=12 - offset,
        )
        for offset, forecast_code in enumerate((3, 61, 1, 71, 95))
    )
    return WeatherSnapshot(
        location=LOCATION,
        temperature=temperature,
        humidity=33,
        wind_speed=7.7,
        weather_code=code,
        is_day=is_day,
        daily=daily,
        fetched_at=now,
    )


def _ready_widget(qtbot, snapshot: WeatherSnapshot) -> FloatingWidget:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.show()
    widget.update_now(dt.datetime.now())
    widget.set_weather_state(
        WeatherState("ready", snapshot=snapshot, location=LOCATION)
    )
    widget._weather_animation.stop()
    widget._background_animation.stop()
    widget.set_weather_reveal(1.0)
    widget.set_background_reveal(1.0)
    return widget


def test_widget_applies_day_visual_and_renders(qtbot) -> None:
    widget = _ready_widget(qtbot, _snapshot(3, is_day=True))
    assert widget._visual is not None
    assert widget._visual.category == CATEGORY_CLOUDY
    assert widget._visual.background_name == "Cloudy Day.jpeg"
    assert widget._visual.icon_name == "overcast.svg"
    assert widget._background_current is not None
    assert widget._background_blur is not None
    assert not widget.grab().isNull()


def test_widget_switches_to_night_visual(qtbot) -> None:
    widget = _ready_widget(qtbot, _snapshot(0, is_day=True))
    assert widget._visual is not None
    assert widget._visual.background_name == "Clear Day.jpeg"
    assert widget._visual.icon_name == "sunny.svg"
    day_background = widget._background_current

    widget.set_weather_state(
        WeatherState(
            "ready",
            snapshot=_snapshot(0, is_day=False, temperature=18.2),
            location=LOCATION,
        )
    )
    assert widget._visual is not None
    assert widget._visual.is_day is False
    assert widget._visual.background_name == "Clear Night.jpeg"
    assert widget._visual.icon_name == "clear_night.svg"
    assert widget._background_current is not day_background
    assert widget._background_previous is day_background
    assert not widget.grab().isNull()

    widget._background_animation.stop()
    widget.set_background_reveal(1.0)
    assert not widget.grab().isNull()


def test_background_change_keeps_previous_frame_for_crossfade(qtbot) -> None:
    widget = _ready_widget(qtbot, _snapshot(0, is_day=True))
    previous = widget._background_current

    widget.set_weather_state(
        WeatherState(
            "ready",
            snapshot=_snapshot(0, is_day=False),
            location=LOCATION,
        )
    )
    assert widget._background_previous is previous
    assert widget._background_current is not previous
    assert 0.0 <= widget._background_reveal < 1.0
    assert not widget.grab().isNull()
    widget._background_animation.stop()
    widget.set_background_reveal(1.0)


def test_widget_does_not_reload_unchanged_background(qtbot) -> None:
    widget = _ready_widget(qtbot, _snapshot(61, is_day=True))
    first_pixmap = widget._background_current
    first_path = widget._background_path
    first_blur = widget._background_blur
    assert first_pixmap is not None
    assert first_blur is not None

    widget.set_weather_state(
        WeatherState(
            "ready",
            snapshot=_snapshot(61, is_day=True, temperature=16.0),
            location=LOCATION,
        )
    )
    assert widget._background_current is first_pixmap
    assert widget._background_path == first_path
    assert widget._background_blur is first_blur
    assert widget._visual is not None
    assert widget._visual.background_name == "Rainy Day.jpeg"


def test_widget_unknown_code_is_safe(qtbot) -> None:
    widget = _ready_widget(qtbot, _snapshot(999, is_day=True))
    assert widget._visual is not None
    assert widget._visual.category == CATEGORY_CLOUDY
    assert widget._visual.background_name == "Cloudy Day.jpeg"
    assert widget._visual.icon_name == "cloudy.svg"
    assert not widget.grab().isNull()


def test_widget_clears_old_artwork_when_the_city_changes(qtbot) -> None:
    widget = _ready_widget(qtbot, _snapshot(0, is_day=True))
    assert widget._background_current is not None

    other = WeatherLocation("شیراز", 29.6, 52.5, "Asia/Tehran", "ایران", "فارس")
    widget.set_weather_state(
        WeatherState("loading", snapshot=None, location=other)
    )
    assert widget._visual is None
    assert widget._background_current is None
    assert widget._background_blur is None
    assert not widget.grab().isNull()


def test_widget_survives_a_failed_background_load(qtbot, monkeypatch) -> None:
    widget = _ready_widget(qtbot, _snapshot(3, is_day=True))

    def broken_background(*args, **kwargs):
        return None

    monkeypatch.setattr(widget._art, "background", broken_background)
    widget.set_weather_state(
        WeatherState(
            "ready",
            snapshot=_snapshot(61, is_day=True),
            location=LOCATION,
        )
    )
    assert widget._background_current is not None
    assert not widget.grab().isNull()
