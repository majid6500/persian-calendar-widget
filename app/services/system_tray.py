"""System tray icon and Persian menu."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.ui.components import make_icon
from app.ui.styles import MUTED, TEXT


class SystemTray(QObject):
    showWidget = Signal()
    hideWidget = Signal()
    openCalendar = Signal()
    openSettings = Signal()
    quitRequested = Signal()

    def __init__(self, icon: QIcon, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray: QSystemTrayIcon | None = None
        self.menu: QMenu | None = None
        self.show_action: QAction | None = None
        self.hide_action: QAction | None = None
        if not self.available:
            return

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("تقویم شمسی")
        self.menu = QMenu()
        self.menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.show_action = self.menu.addAction(
            make_icon("eye", TEXT), "نمایش ویجت"
        )
        self.hide_action = self.menu.addAction(
            make_icon("eye-off", TEXT), "مخفی کردن ویجت"
        )
        self.menu.addSeparator()
        self.open_calendar_action = self.menu.addAction(
            make_icon("calendar", TEXT), "باز کردن تقویم"
        )
        self.open_settings_action = self.menu.addAction(
            make_icon("settings", TEXT), "تنظیمات"
        )
        self.menu.addSeparator()
        self.quit_action = self.menu.addAction(
            make_icon("power", "#FF8A99"), "خروج"
        )

        self.show_action.triggered.connect(self.showWidget.emit)
        self.hide_action.triggered.connect(self.hideWidget.emit)
        self.open_calendar_action.triggered.connect(self.openCalendar.emit)
        self.open_settings_action.triggered.connect(self.openSettings.emit)
        self.quit_action.triggered.connect(self.quitRequested.emit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.openCalendar.emit()

    def show(self) -> bool:
        if self.tray is None:
            return False
        self.tray.show()
        return True

    def hide(self) -> None:
        if self.tray is not None:
            self.tray.hide()

    def set_widget_visible(self, visible: bool) -> None:
        if self.show_action is not None:
            self.show_action.setEnabled(not visible)
        if self.hide_action is not None:
            self.hide_action.setEnabled(visible)

    def set_tooltip(self, text: str) -> None:
        if self.tray is not None:
            self.tray.setToolTip(text)

    def show_message(self, title: str, message: str) -> None:
        if self.tray is not None and self.tray.isVisible():
            self.tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )
