"""Settings window behavior and live-preview tests."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.storage.settings import ACCENT_PRESETS, DEFAULTS, SettingsValues
from app.ui.settings_window import SettingsWindow
from app.weather.models import WeatherLocation


class FakeCitySearch(QObject):
    resultsReady = Signal(object)
    searchFailed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.queries: list[str] = []
        self.cancelled = 0

    def search(self, query: str) -> None:
        self.queries.append(query)

    def cancel(self) -> None:
        self.cancelled += 1


@pytest.fixture
def window(qtbot) -> SettingsWindow:
    widget = SettingsWindow(SettingsValues())
    qtbot.addWidget(widget)
    return widget


def test_values_reflect_initial_settings(qtbot) -> None:
    values = SettingsValues(
        accent="#A78BFA",
        opacity=72,
        size_percent=125,
        show_gregorian=False,
        always_on_top=True,
        start_with_windows=True,
        widget_x=10,
        widget_y=20,
    )
    window = SettingsWindow(values)
    qtbot.addWidget(window)
    current = window.values()
    assert current.accent == "#a78bfa"
    assert current.opacity == 72
    assert current.size_percent == 125
    assert current.show_gregorian is False
    assert current.always_on_top is True
    assert current.start_with_windows is True
    assert (current.widget_x, current.widget_y) == (10, 20)
    assert window.opacity_value.text() == "۷۲٪"
    assert window.size_value.text() == "۱۲۵٪"


def test_all_presets_and_custom_swatch(window: SettingsWindow, qtbot) -> None:
    window.show()
    QApplication.processEvents()
    assert len(window.swatches) == len(ACCENT_PRESETS) == 7
    assert all(swatch.isVisible() for swatch in window.swatches)
    assert window.custom_swatch.isHidden()

    window.swatches[2].click()
    QApplication.processEvents()
    assert window.values().accent == ACCENT_PRESETS[2][1].lower()

    window._set_accent("#123456")
    QApplication.processEvents()
    assert window.values().accent == "#123456"
    assert not window.custom_swatch.isHidden()
    assert window.custom_swatch.isChecked()


def test_sliders_and_toggles_emit_live_preview(window: SettingsWindow) -> None:
    received: list[SettingsValues] = []
    window.valuesChanged.connect(received.append)

    window.opacity_slider.setValue(80)
    window.size_slider.setValue(115)
    window.gregorian_toggle.click()
    window.topmost_toggle.click()
    window.startup_toggle.click()
    QApplication.processEvents()

    assert received
    last = received[-1]
    assert last.opacity == 80
    assert last.size_percent == 115
    assert last.show_gregorian is False
    assert last.always_on_top is True
    assert last.start_with_windows is True
    assert window.opacity_value.text() == "۸۰٪"
    assert window.size_value.text() == "۱۱۵٪"


def test_reset_restores_defaults_but_keeps_position(
    window: SettingsWindow,
) -> None:
    window.load_values(
        SettingsValues(
            accent="#F472B6",
            opacity=70,
            size_percent=90,
            show_gregorian=False,
            always_on_top=True,
            start_with_windows=True,
            widget_x=33,
            widget_y=44,
        )
    )
    received: list[SettingsValues] = []
    window.valuesChanged.connect(received.append)

    window.reset_values()
    current = window.values()
    assert current.accent == DEFAULTS.accent.lower()
    assert current.opacity == DEFAULTS.opacity
    assert current.size_percent == DEFAULTS.size_percent
    assert current.show_gregorian is DEFAULTS.show_gregorian
    assert current.always_on_top is DEFAULTS.always_on_top
    assert current.start_with_windows is DEFAULTS.start_with_windows
    assert (current.widget_x, current.widget_y) == (33, 44)
    assert received


def test_save_and_cancel_signals(window: SettingsWindow, qtbot) -> None:
    saved: list[SettingsValues] = []
    cancelled: list[bool] = []
    window.saveRequested.connect(saved.append)
    window.cancelled.connect(lambda: cancelled.append(True))

    window.show()
    QApplication.processEvents()
    window.opacity_slider.setValue(88)
    window.save_button.click()
    assert saved and saved[0].opacity == 88
    # The window submits the request; the controller is responsible for
    # accepting and closing it.
    assert window.isVisible()

    window.cancel_button.click()
    assert cancelled == [True]
    assert not window.isVisible()


def test_escape_cancels(window: SettingsWindow) -> None:
    cancelled: list[bool] = []
    window.cancelled.connect(lambda: cancelled.append(True))
    window.show()
    QApplication.processEvents()
    QTest.keyClick(window, Qt.Key.Key_Escape)
    assert cancelled == [True]
    assert not window.isVisible()


def test_close_after_save_does_not_emit_cancel(window: SettingsWindow) -> None:
    cancelled: list[bool] = []
    window.cancelled.connect(lambda: cancelled.append(True))
    window.show()
    QApplication.processEvents()
    window.accept_and_close()
    assert not window.isVisible()
    window.close()
    assert cancelled == []


def test_error_message(window: SettingsWindow) -> None:
    window.show_error("خطای آزمایشی")
    assert window.error_label.text() == "خطای آزمایشی"
    assert not window.error_label.isHidden()
    window.load_values(SettingsValues())
    assert window.error_label.isHidden()


def test_invalid_settings_are_normalized_on_load(window: SettingsWindow) -> None:
    window.load_values(
        SettingsValues(
            accent="bad",
            opacity=1,
            size_percent=999,
            show_gregorian=False,
            always_on_top=True,
            start_with_windows=True,
        )
    )
    current = window.values()
    assert current.accent == DEFAULTS.accent.lower()
    assert current.opacity == 60
    assert current.size_percent == 130
    assert current.show_gregorian is False
    assert current.always_on_top is True
    assert current.start_with_windows is True


def test_weather_controls_reflect_saved_city_and_units(qtbot) -> None:
    values = SettingsValues(
        weather_city="تهران",
        weather_latitude=35.7,
        weather_longitude=51.4,
        weather_timezone="Asia/Tehran",
        weather_country="ایران",
        weather_admin1="تهران",
        weather_location_id=112931,
        weather_temperature_unit="fahrenheit",
        weather_wind_speed_unit="mph",
    )
    window = SettingsWindow(values)
    qtbot.addWidget(window)
    assert window.weather_city_label.text() == "تهران"
    assert window.weather_subtitle_label.text() == "تهران، ایران"
    assert window.city_input.text() == "تهران"
    assert window.clear_city_button.isEnabled()
    current = window.values()
    assert current.weather_city == "تهران"
    assert current.weather_latitude == pytest.approx(35.7)
    assert current.weather_longitude == pytest.approx(51.4)
    assert current.weather_location_id == 112931
    assert current.weather_temperature_unit == "fahrenheit"
    assert current.weather_wind_speed_unit == "mph"


def test_city_search_selects_and_clears_city(qtbot) -> None:
    fake = FakeCitySearch()
    window = SettingsWindow(SettingsValues(), city_search=fake)
    qtbot.addWidget(window)
    received: list[SettingsValues] = []
    window.valuesChanged.connect(received.append)

    window.city_input.setText("ت")
    window.city_search_button.click()
    assert fake.queries == []
    assert "دو حرف" in window.city_status.text()

    window.city_input.setText("تهران")
    window.city_search_button.click()
    assert fake.queries == ["تهران"]
    assert not window.city_search_button.isEnabled()

    location = WeatherLocation(
        "تهران",
        35.7,
        51.4,
        "Asia/Tehran",
        "ایران",
        "تهران",
        112931,
    )
    fake.resultsReady.emit((location,))
    QApplication.processEvents()
    assert window.city_results.count() == 1
    assert not window.city_results.isHidden()
    assert window.city_search_button.isEnabled()

    window._choose_city(window.city_results.item(0))
    current = window.values()
    assert current.weather_city == "تهران"
    assert current.weather_timezone == "Asia/Tehran"
    assert current.weather_country == "ایران"
    assert current.weather_admin1 == "تهران"
    assert current.weather_location_id == 112931
    assert window.clear_city_button.isEnabled()
    assert received

    window.clear_city_button.click()
    cleared = window.values()
    assert cleared.weather_city == ""
    assert cleared.weather_latitude is None
    assert cleared.weather_longitude is None
    assert cleared.weather_timezone == "auto"
    assert cleared.weather_location_id is None
    assert not window.clear_city_button.isEnabled()


def test_city_search_failure_is_reported(qtbot) -> None:
    fake = FakeCitySearch()
    window = SettingsWindow(SettingsValues(), city_search=fake)
    qtbot.addWidget(window)
    window.city_input.setText("تهران")
    window.city_search_button.click()
    fake.searchFailed.emit("اتصال قطع است")
    QApplication.processEvents()
    assert window.city_status.text() == "اتصال قطع است"
    assert window.city_search_button.isEnabled()
    assert window.city_results.isHidden()


def test_weather_units_and_reset_preserve_city(qtbot) -> None:
    values = SettingsValues(
        weather_city="تهران",
        weather_latitude=35.7,
        weather_longitude=51.4,
        weather_timezone="Asia/Tehran",
        weather_country="ایران",
        weather_admin1="تهران",
        weather_location_id=112931,
        weather_temperature_unit="celsius",
        weather_wind_speed_unit="kmh",
        opacity=70,
    )
    window = SettingsWindow(values)
    qtbot.addWidget(window)

    temperature_index = window.temperature_combo.findData("fahrenheit")
    wind_index = window.wind_combo.findData("mph")
    assert temperature_index >= 0 and wind_index >= 0
    window.temperature_combo.setCurrentIndex(temperature_index)
    window.wind_combo.setCurrentIndex(wind_index)
    changed = window.values()
    assert changed.weather_temperature_unit == "fahrenheit"
    assert changed.weather_wind_speed_unit == "mph"

    window.reset_values()
    reset = window.values()
    assert reset.opacity == DEFAULTS.opacity
    assert reset.weather_city == "تهران"
    assert reset.weather_latitude == pytest.approx(35.7)
    assert reset.weather_location_id == 112931
    assert reset.weather_temperature_unit == "fahrenheit"
    assert reset.weather_wind_speed_unit == "mph"
    assert window.weather_city_label.text() == "تهران"

