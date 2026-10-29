"""Floating widget geometry, painting state and interaction tests."""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QApplication

from app.calendar import localization as loc
from app.calendar.holidays import CalendarEvent
from app.storage.settings import SettingsValues
from app.weather.models import DailyForecast, WeatherLocation, WeatherSnapshot, WeatherState
from app.widgets.floating_widget import BASE_HEIGHT, BASE_WIDTH, FloatingWidget


def _event(index: int) -> CalendarEvent:
    return CalendarEvent(
        id=f"event-{index}",
        title=f"رویداد {loc.number(index)}",
        category="cultural",
        official=False,
    )


def test_default_size_and_settings_are_applied(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    assert widget.size().width() == BASE_WIDTH
    assert widget.size().height() == BASE_HEIGHT
    assert widget._scale == 1.0
    assert widget._show_gregorian is True
    assert widget._always_on_top is False


def test_apply_settings_scales_and_clamps(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)

    widget.apply_settings(
        SettingsValues(
            accent="#A78BFA",
            opacity=80,
            size_percent=130,
            show_gregorian=False,
            always_on_top=True,
        )
    )
    assert widget.width() == round(BASE_WIDTH * 1.3)
    assert widget.height() == round(BASE_HEIGHT * 1.3)
    assert widget._scale == 1.3
    assert widget.windowOpacity() == 0.8
    assert widget._show_gregorian is False
    assert widget._always_on_top is True
    assert widget._accent.name() == "#a78bfa"

    widget.apply_settings(SettingsValues(opacity=1, size_percent=1))
    assert widget.windowOpacity() == 0.6
    assert widget._scale == 0.8
    assert widget.width() == round(BASE_WIDTH * 0.8)
    assert widget.height() == round(BASE_HEIGHT * 0.8)


def test_default_position_is_inside_the_screen(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    area = screen.availableGeometry()
    position = widget.default_position()
    assert area.left() <= position.x() <= area.right() - widget.width()
    assert area.top() <= position.y() <= area.bottom() - widget.height()


def test_restore_position_clamps_invalid_coordinates(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    screen = QGuiApplication.primaryScreen()
    assert screen is not None
    area = screen.availableGeometry()

    widget.restore_position(999999, 999999)
    assert widget.x() == area.right() - widget.width() - 8
    assert widget.y() == area.bottom() - widget.height() - 8

    widget.restore_position(-500, -500)
    assert widget.x() == area.left() + 8
    assert widget.y() == area.top() + 8

    widget.restore_position(None, None)
    assert area.contains(widget.geometry())


def test_save_position_signal_contains_current_position(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.move(120, 140)
    with qtbot.waitSignal(widget.positionChanged, timeout=1000) as blocker:
        widget.save_position()
    assert blocker.args == [widget.x(), widget.y()]


def test_click_requests_calendar(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()
    with qtbot.waitSignal(widget.calendarRequested, timeout=1000):
        qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(30, 30))


def test_drag_moves_widget_and_saves_position(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.move(100, 100)
    start_global = widget.mapToGlobal(QPoint(20, 20))

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(20, 20),
        QPointF(start_global),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(press)

    move_global = start_global + QPoint(40, 30)
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(60, 50),
        QPointF(move_global),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(move)
    assert widget.pos() == QPoint(140, 130)
    assert widget._dragging is True

    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(60, 50),
        QPointF(move_global),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.waitSignal(widget.positionChanged, timeout=1000):
        widget.mouseReleaseEvent(release)
    assert widget.pos() == QPoint(140, 130)
    assert widget._dragging is False


def test_tooltip_includes_limited_events(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    events = tuple(_event(index) for index in range(1, 5))
    widget.update_now(dt.datetime(2026, 10, 27, 12, 0, 0), events)
    tooltip = widget.toolTip()
    assert "رویداد ۱" in tooltip
    assert "رویداد ۲" in tooltip
    assert "رویداد ۳" in tooltip
    assert "رویداد ۴" not in tooltip
    assert "و ۱ مناسبت دیگر" in tooltip


def test_set_events_updates_tooltip(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.set_events((_event(7),))
    assert "رویداد ۷" in widget.toolTip()


def test_close_saves_position(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()
    with qtbot.waitSignal(widget.positionChanged, timeout=1000):
        widget.close()
    assert not widget.isVisible()


def _weather_snapshot() -> tuple[WeatherState, WeatherLocation]:
    location = WeatherLocation(
        "تهران",
        35.7,
        51.4,
        "Asia/Tehran",
        "ایران",
        "تهران",
        112931,
    )
    snapshot = WeatherSnapshot(
        location=location,
        temperature=18.4,
        humidity=46,
        wind_speed=8.0,
        weather_code=2,
        is_day=False,
        daily=(
            DailyForecast(dt.date(2026, 10, 28), 2, 22, 11),
            DailyForecast(dt.date(2026, 10, 29), 61, 19, 10),
        ),
        fetched_at=dt.datetime.now().astimezone(),
    )
    return WeatherState("ready", snapshot=snapshot, location=location), location


def test_weather_state_paints_and_updates_tooltip(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()

    state, _location = _weather_snapshot()
    widget.set_weather_state(state)
    widget._weather_animation.stop()
    widget.set_weather_reveal(1.0)
    pixmap = widget.grab()
    assert not pixmap.isNull()
    assert not widget._attribution_rect.isEmpty()

    tooltip = widget.toolTip()
    assert "تهران" in tooltip
    assert "Open-Meteo" in tooltip
    assert "رطوبت" in tooltip


def test_idle_weather_state_still_paints(qtbot) -> None:
    widget = FloatingWidget(SettingsValues())
    qtbot.addWidget(widget)
    widget.show()
    QApplication.processEvents()
    widget.set_weather_state(WeatherState("idle"))
    assert not widget.grab().isNull()
    assert widget._attribution_rect.isEmpty()

