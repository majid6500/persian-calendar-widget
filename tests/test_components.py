"""Small custom controls and icon rendering tests."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.components import (
    Chip,
    ColorSwatch,
    FramelessWindow,
    IconButton,
    ToggleSwitch,
    make_icon,
)


def test_make_icon_renders_non_empty_pixmap(qtbot) -> None:
    icon = make_icon("calendar", "#EEF1F7", 48)
    assert not icon.isNull()
    pixmap = icon.pixmap(48, 48)
    assert not pixmap.isNull()
    assert pixmap.width() == 48


def test_toggle_switch_checks_without_emitting(qtbot) -> None:
    toggle = ToggleSwitch()
    qtbot.addWidget(toggle)
    emitted: list[bool] = []
    toggle.toggled.connect(emitted.append)
    toggle.set_checked(True, animate=False)
    assert toggle.isChecked() is True
    assert toggle.get_knob() == 1.0
    assert emitted == []
    toggle.set_checked(False, animate=False)
    assert toggle.isChecked() is False
    assert toggle.get_knob() == 0.0


def test_color_swatch_and_chip(qtbot) -> None:
    swatch = ColorSwatch("#6EA8FF", "آبی")
    qtbot.addWidget(swatch)
    assert swatch.toolTip() == "آبی"
    swatch.set_color("#F472B6")
    assert swatch.color.name() == "#f472b6"
    swatch.setChecked(True)
    assert swatch.isChecked()

    chip = Chip("امروز", "#6EA8FF")
    qtbot.addWidget(chip)
    assert chip.text() == "امروز"
    assert "#6EA8FF" in chip.styleSheet() or "#6ea8ff" in chip.styleSheet().lower()


def test_icon_button_accessible_name(qtbot) -> None:
    button = IconButton("settings", 30, "#FFFFFF", "تنظیمات")
    qtbot.addWidget(button)
    assert button.toolTip() == "تنظیمات"
    assert button.accessibleName() == "تنظیمات"
    assert button.size().width() == 30


def test_frameless_window_show_near_anchor_stays_on_screen(qtbot) -> None:
    anchor = QWidget()
    anchor.setGeometry(600, 400, 100, 80)
    qtbot.addWidget(anchor)
    anchor.show()
    window = FramelessWindow()
    qtbot.addWidget(window)
    window.resize(300, 200)
    window.show_near(anchor)
    screen = QApplication.primaryScreen()
    assert screen is not None
    area = screen.availableGeometry()
    assert area.contains(window.geometry())
    assert window.pos() != QPoint(0, 0)
