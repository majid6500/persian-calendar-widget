"""Application controller: wires UI, services, persistence and OS integration."""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.calendar import localization as loc
from app.calendar.holidays import HolidayService
from app.calendar.jalali import today as jalali_today
from app.services.clock import Clock
from app.services.startup import StartupManager
from app.services.system_tray import SystemTray
from app.storage.settings import SettingsStore, SettingsValues
from app.ui.settings_window import SettingsWindow
from app.ui.styles import apply_theme
from app.weather.cache import WeatherCache
from app.weather.models import WeatherLocation
from app.weather.service import WeatherService
from app.widgets.floating_widget import FloatingWidget
from app.widgets.month_calendar import MonthCalendar

logger = logging.getLogger(__name__)


class CalendarApplication(QObject):
    def __init__(
        self,
        app: QApplication,
        *,
        settings_path: str | Path | None = None,
        holiday_path: str | Path | None = None,
        weather_enabled: bool = True,
    ) -> None:
        super().__init__()
        self.app = app
        self.store = SettingsStore(settings_path)
        self.values = self.store.load().normalized()
        self.saved_values = self.values
        self.service = HolidayService(holiday_path)
        self.clock = Clock(self)
        self.weather_enabled = bool(weather_enabled)
        self.weather = WeatherService(cache=WeatherCache(), parent=self)
        self.widget = FloatingWidget(self.values)
        self.calendar: MonthCalendar | None = None
        self.settings_window: SettingsWindow | None = None
        self.tray: SystemTray | None = None
        self.single_instance = None
        self._settings_original = self.values
        self._last_date = None
        self._last_minute = None
        self._quitting = False

        self._connect_widget()
        self.clock.tick.connect(self._on_tick)
        self.app.aboutToQuit.connect(self._cleanup)

    # ------------------------------------------------------------------ start
    def start(self) -> None:
        apply_theme(self.app, self.values.accent)
        self.widget.restore_position(self.values.widget_x, self.values.widget_y)
        self.widget.show()
        self._setup_tray()
        self._sync_startup()
        if self.weather_enabled:
            self._configure_weather(self.values)
            self.weather.start()
        self.clock.start()
        self._update_tray_state()

        if self.service.load_error:
            logger.warning("Holiday data: %s", self.service.load_error)
            if self.tray is not None:
                self.tray.show_message("داده تعطیلات", self.service.load_error)

    def _connect_widget(self) -> None:
        self.widget.calendarRequested.connect(self.open_calendar)
        self.widget.settingsRequested.connect(self.open_settings)
        self.widget.hideRequested.connect(self.hide_widget)
        self.widget.quitRequested.connect(self.quit)
        self.widget.weatherRefreshRequested.connect(self._refresh_weather)
        self.widget.positionChanged.connect(self._save_position)
        self.weather.stateChanged.connect(self.widget.set_weather_state)

    def _setup_tray(self) -> None:
        icon: QIcon = self.app.windowIcon()
        if icon.isNull():
            from app.ui.components import make_icon

            icon = make_icon("calendar", "#EEF1F7", 64)
            self.app.setWindowIcon(icon)
        self.tray = SystemTray(icon, self)
        self.tray.showWidget.connect(self.show_widget)
        self.tray.hideWidget.connect(self.hide_widget)
        self.tray.openCalendar.connect(self.open_calendar)
        self.tray.openSettings.connect(self.open_settings)
        self.tray.quitRequested.connect(self.quit)
        if not self.tray.show():
            logger.warning("System tray is not available; using the widget context menu.")
        self.tray.set_widget_visible(self.widget.isVisible())

    def _sync_startup(self) -> None:
        manager = StartupManager()
        if not manager.supported:
            return
        ok, message = manager.sync(self.values.start_with_windows)
        if not ok:
            logger.warning("Startup sync failed: %s", message)

    # ------------------------------------------------------------------- tick
    def _on_tick(self, now: dt.datetime) -> None:
        today = jalali_today()
        events = self.service.events_on(today)
        self.widget.update_now(now, events)

        minute = (now.date(), now.hour, now.minute)
        if minute != self._last_minute:
            self._last_minute = minute
            if self.tray is not None:
                self.tray.set_tooltip(
                    f"{loc.long_date(today)}\n{loc.clock_text(now, seconds=False)}"
                )
        if today != self._last_date:
            self._last_date = today
            if self.calendar is not None and self.calendar.isVisible():
                self.calendar.update_today()

    # ------------------------------------------------------------------- show
    def show_widget(self) -> None:
        self.widget.show()
        self.widget.clamp_to_screens()
        self.widget.raise_()
        self._update_tray_state()

    def hide_widget(self) -> None:
        self.widget.hide()
        self._update_tray_state()

    def toggle_widget(self) -> None:
        if self.widget.isVisible():
            self.hide_widget()
        else:
            self.show_widget()

    def _update_tray_state(self) -> None:
        if self.tray is not None:
            self.tray.set_widget_visible(self.widget.isVisible())

    # ---------------------------------------------------------------- calendar
    def open_calendar(self, anchor=None) -> None:
        if self.calendar is None:
            self.calendar = MonthCalendar(self.service, self.values)
            self.calendar.settingsRequested.connect(self.open_settings)
        self.calendar.set_accent(self.values.accent)
        self.calendar.go_today()
        self.calendar.show_calendar(anchor or self.widget)

    def hide_calendar(self) -> None:
        if self.calendar is not None:
            self.calendar.hide()

    # ---------------------------------------------------------------- settings
    def open_settings(self, anchor=None) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.values)
            self.settings_window.valuesChanged.connect(self._on_settings_preview)
            self.settings_window.saveRequested.connect(self._on_settings_save)
            self.settings_window.cancelled.connect(self._on_settings_cancel)
        if not self.settings_window.isVisible():
            self._settings_original = self.saved_values
        self.settings_window.show_window(self.values, anchor or self.widget)

    def _on_settings_preview(self, values: SettingsValues) -> None:
        self._apply_values(values, persist=False)

    def _on_settings_cancel(self) -> None:
        self._apply_values(self._settings_original, persist=False)

    def _on_settings_save(self, values: SettingsValues) -> None:
        values = values.normalized()
        old_weather_key = self.saved_values.weather_key
        manager = StartupManager()
        if manager.supported:
            ok, message = manager.set_enabled(values.start_with_windows)
            if not ok:
                if self.settings_window is not None:
                    self.settings_window.show_error(message)
                return
        try:
            self.saved_values = self.store.save(values)
        except OSError as exc:
            if self.settings_window is not None:
                self.settings_window.show_error(f"ذخیرهٔ تنظیمات ممکن نشد: {exc}")
            return
        self.values = self.saved_values
        self._apply_values(self.saved_values, persist=False)
        if (
            self.weather_enabled
            and self.saved_values.weather_key != old_weather_key
        ):
            self._configure_weather(self.saved_values)
        if self.settings_window is not None:
            self.settings_window.accept_and_close()
        if self.tray is not None:
            self.tray.set_tooltip(
                f"{loc.long_date(jalali_today())}"
            )

    def _apply_values(self, values: SettingsValues, *, persist: bool) -> None:
        values = values.normalized()
        accent_changed = values.accent != self.values.accent
        self.values = values
        if accent_changed:
            apply_theme(self.app, values.accent)
        self.widget.apply_settings(values)
        if self.calendar is not None and accent_changed:
            self.calendar.set_accent(values.accent)
        if persist:
            self.saved_values = self.store.save(values)

    # ------------------------------------------------------------------ weather
    @staticmethod
    def _weather_location(values: SettingsValues) -> WeatherLocation | None:
        if not values.has_weather_location:
            return None
        return WeatherLocation(
            name=values.weather_city,
            latitude=values.weather_latitude or 0.0,
            longitude=values.weather_longitude or 0.0,
            timezone=values.weather_timezone,
            country=values.weather_country,
            admin1=values.weather_admin1,
            location_id=values.weather_location_id,
        )

    def _configure_weather(self, values: SettingsValues) -> None:
        self.weather.configure(
            self._weather_location(values),
            values.weather_temperature_unit,
            values.weather_wind_speed_unit,
        )

    def _refresh_weather(self) -> None:
        if self.weather_enabled:
            self.weather.refresh(force=True)

    # ------------------------------------------------------------- activation
    def activate(self) -> None:
        self.show_widget()
        self.open_calendar()

    def _save_position(self, x: int, y: int) -> None:
        self.store.save_position(x, y)
        self.values = self.values.with_position(x, y)
        self.saved_values = self.saved_values.with_position(x, y)

    # ------------------------------------------------------------------- quit
    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self.store.save_position(self.widget.x(), self.widget.y())
        self.weather.stop()
        self.clock.stop()
        if self.tray is not None:
            self.tray.hide()
        if self.calendar is not None:
            self.calendar.hide()
        if self.settings_window is not None:
            self.settings_window.hide()
        self.widget.hide()
        self.app.quit()

    def _cleanup(self) -> None:
        self.weather.stop()
        self.clock.stop()
        if self.tray is not None:
            self.tray.hide()
