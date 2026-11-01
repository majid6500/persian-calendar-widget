"""Embedded calendar and settings navigation tests."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from app.core.application import CalendarApplication


def _wait_for_transition(qtbot, controller: CalendarApplication) -> None:
    qtbot.waitUntil(lambda: controller.widget._page_animation is None, timeout=1500)


def test_left_swipe_on_widget_opens_calendar(qtbot, qapp, tmp_path) -> None:
    controller = CalendarApplication(
        qapp,
        settings_path=tmp_path / "settings.json",
        weather_enabled=False,
    )
    widget = controller.widget
    qtbot.addWidget(widget)
    widget.show()
    initial_pos = widget.pos()

    start = QPoint(300, 200)
    global_start = widget.mapToGlobal(start)
    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(start),
        QPointF(global_start),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(press)

    for offset in (-15, -60):
        position = start + QPoint(offset, 0)
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(position),
            QPointF(widget.mapToGlobal(position)),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        widget.mouseMoveEvent(move)

    assert widget._swiping
    assert widget.pos() == initial_pos
    release_position = start + QPoint(-60, 0)
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(release_position),
        QPointF(widget.mapToGlobal(release_position)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseReleaseEvent(release)
    _wait_for_transition(qtbot, controller)
    assert controller.calendar is not None
    assert widget.active_page is controller.calendar

    controller.weather.stop()
    controller.clock.stop()


def test_calendar_and_settings_slide_inside_the_widget(qtbot, qapp, tmp_path) -> None:
    controller = CalendarApplication(
        qapp,
        settings_path=tmp_path / "settings.json",
        weather_enabled=False,
    )
    widget = controller.widget
    qtbot.addWidget(widget)
    widget.show()

    controller.open_calendar()
    _wait_for_transition(qtbot, controller)
    calendar = controller.calendar
    assert calendar is not None
    assert calendar.parentWidget() is widget
    assert not calendar.isWindow()
    assert calendar.geometry() == widget.rect()
    assert calendar.scroll.verticalScrollBar().maximum() == 0
    assert widget.active_page is calendar

    swipes: list[int] = []
    calendar.swipeRequested.connect(swipes.append)
    QTest.mousePress(
        calendar, Qt.MouseButton.LeftButton, pos=QPoint(500, 380)
    )
    assert calendar._swipe_origin is not None
    QTest.mouseRelease(
        calendar, Qt.MouseButton.LeftButton, pos=QPoint(380, 380)
    )
    assert swipes == [1]
    assert controller.settings_window is not None
    assert widget._page_target is controller.settings_window
    _wait_for_transition(qtbot, controller)
    settings = controller.settings_window
    assert settings is not None
    assert settings.parentWidget() is widget
    assert not settings.isWindow()
    assert settings.geometry() == widget.rect()
    assert widget.active_page is settings

    original_opacity = widget.windowOpacity()
    settings.opacity_slider.setValue(80)
    assert widget.windowOpacity() == 0.8
    QTest.mousePress(
        settings, Qt.MouseButton.LeftButton, pos=QPoint(100, 300)
    )
    QTest.mouseRelease(
        settings, Qt.MouseButton.LeftButton, pos=QPoint(220, 300)
    )
    _wait_for_transition(qtbot, controller)
    assert widget.active_page is calendar
    assert settings.isHidden()
    assert widget.windowOpacity() == original_opacity

    calendar.closeRequested.emit()
    _wait_for_transition(qtbot, controller)
    assert widget.active_page is None
    assert calendar.isHidden()

    controller.weather.stop()
    controller.clock.stop()
