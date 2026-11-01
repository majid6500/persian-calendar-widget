"""The compact glass clock, date and weather widget."""

from __future__ import annotations

import ctypes
import datetime as dt
import sys

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPoint,
    QPointF,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from app.calendar import localization as loc
from app.calendar.holidays import CalendarEvent
from app.calendar.jalali import JalaliDate, today as jalali_today
from app.storage.settings import SettingsValues
from app.ui.components import make_icon
from app.ui.styles import DANGER, DIM, MUTED, TEXT, font_family
from app.weather.art import WeatherArt
from app.weather.conditions import condition_kind, condition_text
from app.weather.icons import paint_weather_glyph
from app.weather.models import WeatherState
from app.weather.visuals import (
    DETAIL_THERMOMETER_ICON,
    DETAIL_WIND_ICON,
    WeatherVisual,
    detail_icon_path,
    resolve_visual,
)

BASE_WIDTH = 560
BASE_HEIGHT = 430
BASE_RADIUS = 24
CARD_MARGIN = 6.0
OPEN_METEO_URL = "https://open-meteo.com/"


def _font(size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont(font_family())
    font.setPixelSize(max(1, round(size)))
    font.setWeight(weight)
    return font


def _persian_weekday_short(value: dt.date) -> str:
    # Python Monday=0; the calendar UI starts its week on Saturday.
    return loc.weekday_short((value.weekday() + 2) % 7)


def _temperature_text(value: float) -> str:
    rounded = round(value)
    return loc.number(rounded)


def _time_text(value: object) -> str:
    if not isinstance(value, dt.time):
        return "—"
    return f"{loc.number_padded(value.hour)}:{loc.number_padded(value.minute)}"


def _uv_text(value: float | None) -> str:
    if value is None:
        return "شاخص UV —"
    rounded = round(value, 1)
    number = loc.to_persian_digits(f"{rounded:g}").replace(".", "٫")
    if value < 3:
        level = "کم"
    elif value < 6:
        level = "متوسط"
    elif value < 8:
        level = "زیاد"
    elif value < 11:
        level = "خیلی زیاد"
    else:
        level = "شدید"
    return f"شاخص UV {number} • {level}"


class FloatingWidget(QWidget):
    calendarRequested = Signal()
    settingsRequested = Signal()
    pageSwipeRequested = Signal(int)
    hideRequested = Signal()
    quitRequested = Signal()
    positionChanged = Signal(int, int)
    weatherRefreshRequested = Signal()

    def __init__(self, values: SettingsValues, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAccessibleName("ویجت تاریخ شمسی و هوا")

        self._accent = QColor(values.accent)
        self._scale = 1.0
        self._show_gregorian = values.show_gregorian
        self._always_on_top = values.always_on_top
        self._now = dt.datetime.now()
        self._today: JalaliDate = jalali_today()
        self._events: tuple[CalendarEvent, ...] = ()
        self._weather_state = WeatherState()
        self._weather_reveal = 1.0
        self._art = WeatherArt()
        self._visual: WeatherVisual | None = None
        self._background_current = None
        self._background_previous = None
        self._background_blur = None
        self._background_path: str | None = None
        self._background_reveal = 1.0
        self._attribution_rect = QRectF()
        self._press_on_attribution = False
        self._hover = False
        self._pressed = False
        self._dragging = False
        self._press_global: QPoint | None = None
        self._press_offset: QPoint | None = None
        self._moved = False
        self._swiping = False
        self._active_page: QWidget | None = None
        self._page_target: QWidget | None = None
        self._page_animation: QParallelAnimationGroup | None = None

        self._weather_animation = QPropertyAnimation(self, b"weatherReveal", self)
        self._weather_animation.setDuration(220)
        self._weather_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._background_animation = QPropertyAnimation(
            self, b"backgroundReveal", self
        )
        self._background_animation.setDuration(420)
        self._background_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.apply_settings(values)
        self.setToolTip("")

    # -------------------------------------------------------------- settings
    def apply_settings(self, values: SettingsValues) -> None:
        self._accent = QColor(values.accent)
        self._show_gregorian = bool(values.show_gregorian)
        self._always_on_top = bool(values.always_on_top)
        self._scale = max(0.8, min(1.3, values.size_percent / 100.0))
        old_center = self.geometry().center()
        self.setFixedSize(
            round(BASE_WIDTH * self._scale), round(BASE_HEIGHT * self._scale)
        )
        for page in {self._active_page, self._page_target} - {None}:
            page.resize(self.size())
        self.setWindowOpacity(max(0.6, min(1.0, values.opacity / 100.0)))
        self._apply_topmost()
        if self.isVisible():
            self.move(
                old_center.x() - self.width() // 2,
                old_center.y() - self.height() // 2,
            )
            self.clamp_to_screens()
        self.update()

    @property
    def active_page(self) -> QWidget | None:
        return (
            self._page_target
            if self._page_animation is not None
            else self._active_page
        )

    def show_page(self, page: QWidget | None, direction: int = 1) -> None:
        if self._page_animation is not None:
            self._settle_page_transition()
        if page is self._active_page:
            if page is not None:
                page.show()
                page.raise_()
            return

        old_page = self._active_page
        self._page_target = page
        width = self.width()
        height = self.height()
        self._page_animation = QParallelAnimationGroup(self)
        if old_page is not None:
            old_page.setGeometry(0, 0, width, height)
            exit_animation = QPropertyAnimation(old_page, b"pos", self._page_animation)
            exit_animation.setDuration(240)
            exit_animation.setStartValue(QPoint(0, 0))
            exit_animation.setEndValue(QPoint(-direction * width, 0))
            self._page_animation.addAnimation(exit_animation)
        if page is not None:
            page.setGeometry(0, 0, width, height)
            page.move(QPoint(direction * width, 0))
            page.show()
            if old_page is not None:
                old_page.raise_()
            page.raise_()
            enter_animation = QPropertyAnimation(page, b"pos", self._page_animation)
            enter_animation.setDuration(240)
            enter_animation.setStartValue(QPoint(direction * width, 0))
            enter_animation.setEndValue(QPoint(0, 0))
            self._page_animation.addAnimation(enter_animation)
        self._page_animation.finished.connect(self._complete_page_transition)
        self._page_animation.start()

    def _complete_page_transition(self) -> None:
        old_page = self._active_page
        new_page = self._page_target
        if old_page is not None and old_page is not new_page:
            old_page.hide()
            old_page.move(0, 0)
        if new_page is not None:
            new_page.setGeometry(self.rect())
            new_page.show()
            new_page.raise_()
        animation = self._page_animation
        self._active_page = new_page
        self._page_target = None
        self._page_animation = None
        if animation is not None:
            animation.deleteLater()

    def _settle_page_transition(self) -> None:
        animation = self._page_animation
        if animation is None:
            return
        animation.stop()
        self._complete_page_transition()

    def _apply_topmost(self) -> None:
        if sys.platform == "win32":
            try:
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND,
                    wintypes.HWND,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                    wintypes.UINT,
                ]
                user32.SetWindowPos.restype = wintypes.BOOL
                hwnd = wintypes.HWND(int(self.winId()))
                insert_after = wintypes.HWND(-1 if self._always_on_top else -2)
                flags = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
                if user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags):
                    return
                raise ctypes.WinError(ctypes.get_last_error())
            except Exception:
                pass
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._always_on_top)
        if visible:
            self.show()

    # ------------------------------------------------------------------ data
    def update_now(
        self, now: dt.datetime, events: tuple[CalendarEvent, ...] = ()
    ) -> None:
        date_changed = now.date() != self._now.date()
        self._now = now
        self._today = jalali_today()
        self._events = events
        if date_changed or not self.toolTip():
            self._update_tooltip()
        self.update()

    def _update_tooltip(self) -> None:
        lines = [loc.long_date(self._today)]
        state = self._weather_state
        snapshot = state.snapshot
        if snapshot is not None:
            lines.append(
                f"{snapshot.location.display_name}: "
                f"{_temperature_text(snapshot.temperature)}{snapshot.temperature_symbol}، "
                f"{condition_text(snapshot.weather_code)}"
            )
            if snapshot.humidity is not None or snapshot.wind_speed is not None:
                details: list[str] = []
                if snapshot.humidity is not None:
                    details.append(f"رطوبت {loc.percent_text(snapshot.humidity)}")
                if snapshot.wind_speed is not None:
                    details.append(
                        f"باد {loc.number(round(snapshot.wind_speed))} "
                        f"{snapshot.wind_speed_label}"
                    )
                lines.append(" • ".join(details))
            lines.append("دادهٔ هوا: Open-Meteo")
        elif state.status == "error" and state.message:
            lines.append(state.message)
        elif state.status == "loading":
            lines.append("در حال دریافت هوا…")
        for event in self._events[:3]:
            lines.append(f"• {event.title}")
        if len(self._events) > 3:
            lines.append(f"و {loc.number(len(self._events) - 3)} مناسبت دیگر")
        self.setToolTip("\n".join(lines))

    def set_events(self, events: tuple[CalendarEvent, ...]) -> None:
        self._events = events
        self._update_tooltip()
        self.update()

    def set_weather_state(self, state: WeatherState) -> None:
        previous = self._weather_state
        self._weather_state = state

        snapshot = state.snapshot
        if snapshot is not None:
            self._apply_weather_visual(
                resolve_visual(snapshot.weather_code, snapshot.is_day)
            )
        elif state.location is None or state.location != previous.location:
            # A cleared or changed city should not leave the previous city's
            # artwork visible while the new location is loading.
            self._apply_weather_visual(None)

        if snapshot is not None and snapshot != previous.snapshot:
            self._weather_animation.stop()
            self._weather_animation.setStartValue(0.25)
            self._weather_animation.setEndValue(1.0)
            self._weather_animation.start()
        elif snapshot is None:
            self._weather_reveal = 1.0
        self._update_tooltip()
        self.update()

    def _background_target_size(self) -> QSize:
        # Render at 2x the logical card size so the artwork stays sharp when
        # the widget is scaled up to 130%.
        card_width = BASE_WIDTH - CARD_MARGIN * 2
        card_height = BASE_HEIGHT - CARD_MARGIN * 2
        return QSize(round(card_width * 2), round(card_height * 2))

    def _apply_weather_visual(self, visual: WeatherVisual | None) -> None:
        previous_visual = self._visual
        self._visual = visual
        if visual is None or visual.background_path is None:
            self._clear_background()
            return

        path_key = str(visual.background_path)
        if self._background_path == path_key:
            return

        pixmap = self._art.background(
            visual.background_path,
            self._background_target_size(),
            anchor_right=True,
        )
        if pixmap is None:
            # Keep the last valid artwork rather than showing a half-updated
            # icon over a missing/broken background.
            self._visual = previous_visual
            return

        if self._background_current is None:
            self._background_previous = None
            self._background_current = pixmap
            self._background_blur = self._make_blurred_background(pixmap)
            self._background_path = path_key
            self._background_reveal = 1.0
            return

        self._background_previous = self._background_current
        self._background_current = pixmap
        self._background_blur = self._make_blurred_background(pixmap)
        self._background_path = path_key
        self._background_reveal = 0.0
        self._background_animation.stop()
        self._background_animation.setStartValue(0.0)
        self._background_animation.setEndValue(1.0)
        self._background_animation.start()

    def _clear_background(self) -> None:
        self._background_animation.stop()
        self._background_current = None
        self._background_previous = None
        self._background_blur = None
        self._background_path = None
        self._background_reveal = 1.0

    def get_weather_reveal(self) -> float:
        return self._weather_reveal

    def set_weather_reveal(self, value: float) -> None:
        self._weather_reveal = max(0.0, min(1.0, float(value)))
        self.update()

    weatherReveal = Property(float, get_weather_reveal, set_weather_reveal)

    def get_background_reveal(self) -> float:
        return self._background_reveal

    def set_background_reveal(self, value: float) -> None:
        self._background_reveal = max(0.0, min(1.0, float(value)))
        self.update()

    backgroundReveal = Property(
        float, get_background_reveal, set_background_reveal
    )

    # -------------------------------------------------------------- geometry
    def default_position(self) -> QPoint:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QPoint(80, 80)
        area = screen.availableGeometry()
        return QPoint(
            area.right() - self.width() - 26,
            area.bottom() - self.height() - 34,
        )

    def restore_position(self, x: int | None, y: int | None) -> None:
        if x is None or y is None:
            self.move(self.default_position())
        else:
            self.move(int(x), int(y))
        self.clamp_to_screens()

    @staticmethod
    def _best_screen(rect):
        screens = QGuiApplication.screens()
        if not screens:
            return None
        best = None
        best_area = 0
        for screen in screens:
            inter = screen.availableGeometry().intersected(rect)
            area = max(0, inter.width()) * max(0, inter.height())
            if area > best_area:
                best_area = area
                best = screen
        if best is not None:
            return best
        center = rect.center()
        return min(
            screens,
            key=lambda s: (
                s.availableGeometry().center().x() - center.x()
            )
            ** 2
            + (s.availableGeometry().center().y() - center.y()) ** 2,
        )

    def clamp_to_screens(self) -> None:
        screen = self._best_screen(self.frameGeometry())
        if screen is None:
            return
        area = screen.availableGeometry()
        margin = 8
        x = max(
            area.left() + margin,
            min(self.x(), area.right() - self.width() - margin),
        )
        y = max(
            area.top() + margin,
            min(self.y(), area.bottom() - self.height() - margin),
        )
        if x != self.x() or y != self.y():
            self.move(x, y)

    def save_position(self) -> None:
        self.positionChanged.emit(self.x(), self.y())

    # --------------------------------------------------------------- painting
    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.scale(self._scale, self._scale)

        w, h = BASE_WIDTH, BASE_HEIGHT
        card = QRectF(
            CARD_MARGIN,
            CARD_MARGIN,
            w - CARD_MARGIN * 2,
            h - CARD_MARGIN * 2,
        )
        path = QPainterPath()
        path.addRoundedRect(card, BASE_RADIUS, BASE_RADIUS)

        self._paint_shadow(painter, card)
        self._paint_background(painter, card, path)
        self._paint_card_surface(painter, card, path)
        self._paint_contents(painter, card)
        painter.end()

    def _paint_shadow(self, painter: QPainter, card: QRectF) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for index, alpha in ((0, 22), (2, 16), (4, 11), (6, 7)):
            shadow = card.adjusted(-index, index * 0.6 + 1, index, index + 2)
            painter.setBrush(QColor(0, 0, 0, alpha))
            radius = BASE_RADIUS + index
            painter.drawRoundedRect(shadow, radius, radius)
        painter.restore()

    def _paint_background(
        self, painter: QPainter, card: QRectF, path: QPainterPath
    ) -> None:
        painter.save()
        painter.setClipPath(path)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._background_current is None:
            gradient = QLinearGradient(card.topLeft(), card.bottomLeft())
            gradient.setColorAt(0.0, QColor("#1B2634"))
            gradient.setColorAt(0.42, QColor("#111923"))
            gradient.setColorAt(1.0, QColor("#090E15"))
            painter.fillRect(card, gradient)
        else:
            if (
                self._background_previous is not None
                and self._background_reveal < 1.0
            ):
                painter.setOpacity(1.0 - self._background_reveal)
                self._draw_background_pixmap(
                    painter, card, self._background_previous
                )
            painter.setOpacity(
                self._background_reveal
                if self._background_previous is not None
                else 1.0
            )
            self._draw_background_pixmap(painter, card, self._background_current)

        painter.restore()

    @staticmethod
    def _draw_background_pixmap(painter: QPainter, card: QRectF, pixmap) -> None:
        source = QRectF(0, 0, pixmap.width(), pixmap.height())
        painter.drawPixmap(card, pixmap, source)

    @staticmethod
    def _make_blurred_background(pixmap):
        """Return a tiny downscaled/upscaled copy used as backdrop blur."""
        image = pixmap.toImage()
        if image.isNull():
            return None
        width = max(1, image.width() // 18)
        height = max(1, image.height() // 18)
        small = image.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return small.scaled(
            image.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _paint_glass_panel(
        self,
        painter: QPainter,
        card: QRectF,
        panel: QRectF,
        radius: float,
    ) -> None:
        """Paint a restrained frosted-glass surface over the artwork."""
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(panel, radius, radius)
        painter.setClipPath(path)

        # Qt's raster painter has no live backdrop blur.  A heavily blurred
        # copy of the current background provides the same quiet, frosted
        # effect without adding a second rendering system.
        if self._background_blur is not None and self._background_reveal >= 1.0:
            painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform, True
            )
            painter.drawImage(
                card,
                self._background_blur,
                QRectF(
                    0.0,
                    0.0,
                    float(self._background_blur.width()),
                    float(self._background_blur.height()),
                ),
            )

        glass = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        glass.setColorAt(0.0, QColor(13, 19, 28, 132))
        glass.setColorAt(0.58, QColor(9, 14, 22, 144))
        glass.setColorAt(1.0, QColor(6, 10, 17, 154))
        painter.fillRect(panel, glass)

        highlight = QLinearGradient(
            panel.topLeft(),
            QPointF(panel.left(), panel.top() + panel.height() * 0.56),
        )
        highlight.setColorAt(0.0, QColor(255, 255, 255, 18))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillRect(panel, highlight)

        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        painter.drawPath(path)
        painter.restore()

    def _paint_card_surface(
        self, painter: QPainter, card: QRectF, path: QPainterPath
    ) -> None:
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border_color = QColor(255, 255, 255, 34 if self._hover else 18)
        painter.setPen(QPen(border_color, 1.0))
        painter.drawPath(path)

        if self._pressed and not self._dragging:
            painter.setClipPath(path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 7))
            painter.drawRect(card)
        painter.restore()

    def _paint_contents(self, painter: QPainter, card: QRectF) -> None:
        date_panel = QRectF(18.0, 16.0, 430.0, 112.0)
        weather_panel = QRectF(18.0, 138.0, 430.0, 174.0)
        strip = QRectF(18.0, 322.0, 430.0, 92.0)
        self._paint_glass_panel(painter, card, date_panel, 18.0)
        self._paint_glass_panel(painter, card, weather_panel, 18.0)
        self._paint_glass_panel(painter, card, strip, 16.0)

        left = date_panel.left() + 18.0
        top = date_panel.top() + 14.0

        painter.save()
        # Qt mirrors AlignLeft in RTL.  AlignRight therefore anchors the
        # Persian text to the visual left while preserving bidi ordering.
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        pill = QRectF(left, top, 58.0, 22.0)
        pill_color = QColor(self._accent)
        pill_color.setAlpha(34)
        painter.setPen(
            QPen(
                QColor(
                    self._accent.red(),
                    self._accent.green(),
                    self._accent.blue(),
                    86,
                ),
                0.8,
            )
        )
        painter.setBrush(pill_color)
        painter.drawRoundedRect(pill, 10.0, 10.0)
        painter.setFont(_font(9, QFont.Weight.DemiBold))
        painter.setPen(self._accent)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, "امروز")

        painter.setFont(_font(12, QFont.Weight.Medium))
        painter.setPen(QColor("#D0DBE6"))
        painter.drawText(
            QRectF(left + 70.0, top, 120.0, 22.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            loc.weekday_of(self._today),
        )

        # Keep the clock secondary to the date and temperature.
        hhmm, seconds = loc.clock_parts(self._now)
        painter.save()
        painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        time_font = _font(21, QFont.Weight.Medium)
        painter.setFont(time_font)
        painter.setPen(QColor("#D7E1EA"))
        painter.drawText(
            QRectF(date_panel.right() - 108.0, top + 23.0, 88.0, 28.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            hhmm,
        )
        painter.setFont(_font(9.5, QFont.Weight.Medium))
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRectF(date_panel.right() - 108.0, top + 51.0, 88.0, 16.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            seconds,
        )
        painter.restore()

        painter.setPen(QPen(QColor(255, 255, 255, 30), 0.8))
        painter.drawLine(
            QPointF(date_panel.right() - 126.0, top + 27.0),
            QPointF(date_panel.right() - 126.0, date_panel.bottom() - 16.0),
        )

        painter.setFont(_font(42, QFont.Weight.Bold))
        painter.setPen(QColor(TEXT))
        painter.drawText(
            QRectF(left, top + 25.0, 66.0, 50.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            loc.day_number(self._today),
        )
        painter.setFont(_font(15, QFont.Weight.DemiBold))
        painter.setPen(QColor(TEXT))
        painter.drawText(
            QRectF(left + 76.0, top + 34.0, 170.0, 24.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{loc.month_name(self._today.month)} {loc.number(self._today.year)}",
        )

        if self._show_gregorian:
            painter.save()
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.setFont(_font(10))
            painter.setPen(QColor("#AEBBC9"))
            painter.drawText(
                QRectF(left + 76.0, top + 59.0, 180.0, 18.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                loc.gregorian_text(self._now.date()),
            )
            painter.restore()

        painter.restore()

        self._paint_weather(painter, weather_panel)
        self._paint_forecast(painter, strip)
        self._paint_footer(painter, strip)

    def _paint_weather(self, painter: QPainter, panel: QRectF) -> None:
        state = self._weather_state
        snapshot = state.snapshot
        location = snapshot.location if snapshot is not None else state.location
        data_color = QColor(TEXT)
        muted = QColor(MUTED)
        icon_color = QColor(self._accent if snapshot is not None else MUTED)
        if snapshot is None:
            icon_color.setAlpha(150)

        left = panel.left() + 18.0
        right = panel.right() - 18.0

        painter.save()
        painter.setOpacity(self._weather_reveal)
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        backing = QRectF(left, panel.top() + 16.0, 80.0, 80.0)
        painter.setBrush(QColor(255, 255, 255, 12))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(backing)

        ring = backing.adjusted(0.6, 0.6, -0.6, -0.6)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        painter.drawEllipse(ring)
        progress = loc.day_progress(self._now)
        if progress > 0.0:
            progress_pen = QPen(
                QColor(
                    self._accent.red(),
                    self._accent.green(),
                    self._accent.blue(),
                    150,
                ),
                1.4,
            )
            progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)
            painter.drawArc(ring, 90 * 16, -int(progress * 360.0 * 16.0))
        painter.setPen(Qt.PenStyle.NoPen)

        icon_rect = QRectF(left + 8.0, panel.top() + 20.0, 64.0, 64.0)
        if snapshot is not None:
            visual = self._visual
            drew = (
                visual is not None
                and self._art.draw_icon(
                    painter, icon_rect, visual.icon_path
                )
            )
            if not drew:
                paint_weather_glyph(
                    painter,
                    icon_rect,
                    condition_kind(snapshot.weather_code, snapshot.is_day),
                    icon_color,
                    width=2.3,
                )
        else:
            paint_weather_glyph(
                painter, icon_rect, "cloudy", icon_color, width=2.0
            )

        text_left = left + 98.0
        text_width = right - text_left
        city_rect = QRectF(text_left, panel.top() + 15.0, text_width, 20.0)
        painter.setFont(_font(13, QFont.Weight.DemiBold))
        painter.setPen(data_color)
        city_name = location.display_name if location is not None else "هوا"
        city_name = QFontMetricsF(painter.font()).elidedText(
            city_name, Qt.TextElideMode.ElideRight, int(city_rect.width())
        )
        painter.drawText(
            city_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            city_name,
        )

        condition_rect = QRectF(text_left, panel.top() + 37.0, text_width, 17.0)
        if snapshot is not None:
            condition = condition_text(snapshot.weather_code)
            condition_color = QColor("#D4DFEA")
        elif state.status == "loading":
            condition = "در حال دریافت…"
            condition_color = muted
        elif state.status == "error":
            condition = "هوا در دسترس نیست"
            condition_color = QColor(DANGER)
        else:
            condition = "شهر را انتخاب کنید"
            condition_color = muted
        painter.setFont(_font(10.5, QFont.Weight.Medium))
        painter.setPen(condition_color)
        condition = QFontMetricsF(painter.font()).elidedText(
            condition, Qt.TextElideMode.ElideRight, int(condition_rect.width())
        )
        painter.drawText(
            condition_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            condition,
        )

        temp_rect = QRectF(text_left, panel.top() + 51.0, text_width, 46.0)
        if snapshot is not None:
            painter.save()
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.setFont(_font(40, QFont.Weight.DemiBold))
            painter.setPen(data_color)
            temp = _temperature_text(snapshot.temperature)
            painter.drawText(
                temp_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{temp}°",
            )
            temp_width = QFontMetricsF(painter.font()).horizontalAdvance(
                f"{temp}°"
            )
            painter.setFont(_font(8, QFont.Weight.Medium))
            painter.setPen(muted)
            painter.drawText(
                QRectF(
                    temp_rect.x() + temp_width + 2.0,
                    temp_rect.y() + 12.0,
                    30.0,
                    16.0,
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                snapshot.temperature_symbol[-1],
            )
            painter.restore()
        else:
            painter.setFont(_font(40, QFont.Weight.DemiBold))
            painter.setPen(QColor(DIM))
            painter.drawText(
                temp_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "…",
            )

        # Larger metric rows make secondary weather data readable at a glance.
        if snapshot is not None:
            separator_y = panel.top() + 93.0
            painter.setPen(QPen(QColor(255, 255, 255, 30), 0.8))
            painter.drawLine(
                QPointF(left, separator_y),
                QPointF(right, separator_y),
            )

            today_forecast = next(
                (day for day in snapshot.daily if day.date == self._now.date()),
                snapshot.daily[0] if snapshot.daily else None,
            )
            high_low = "بیشینه — • کمینه —"
            if today_forecast is not None:
                high_low = (
                    f"بیشینه {loc.number(round(today_forecast.temp_max))}°"
                    f" • کمینه {loc.number(round(today_forecast.temp_min))}°"
                )

            feels_like = (
                f"دمای احساسی {loc.number(round(snapshot.apparent_temperature))}°"
                if snapshot.apparent_temperature is not None
                else "دمای احساسی —"
            )
            humidity = (
                f"رطوبت {loc.percent_text(snapshot.humidity)}"
                if snapshot.humidity is not None
                else "رطوبت —"
            )
            wind = (
                f"باد {loc.number(round(snapshot.wind_speed))} "
                f"{snapshot.wind_speed_label}"
                if snapshot.wind_speed is not None
                else "باد —"
            )
            metrics = (
                (humidity, "humidity"),
                (wind, DETAIL_WIND_ICON),
                (high_low, DETAIL_THERMOMETER_ICON),
                (feels_like, DETAIL_THERMOMETER_ICON),
                (f"طلوع {_time_text(snapshot.sunrise)}", "sunrise.svg"),
                (f"غروب {_time_text(snapshot.sunset)}", "sunset.svg"),
                (_uv_text(snapshot.uv_index), "sun_bright.svg"),
            )
            cell_width = (right - left - 18.0) / 2.0
            for index, (text, icon_name) in enumerate(metrics):
                row, column = divmod(index, 2)
                x = left + column * (cell_width + 18.0)
                y = separator_y + 8.0 + row * 18.0
                icon_rect = QRectF(x, y + 1.0, 16.0, 16.0)
                if icon_name == "humidity":
                    painter.save()
                    drop = QPainterPath()
                    drop.moveTo(icon_rect.center().x(), icon_rect.top())
                    drop.cubicTo(
                        icon_rect.right(),
                        icon_rect.top() + 5.0,
                        icon_rect.right() - 1.0,
                        icon_rect.bottom(),
                        icon_rect.center().x(),
                        icon_rect.bottom(),
                    )
                    drop.cubicTo(
                        icon_rect.left() + 1.0,
                        icon_rect.bottom(),
                        icon_rect.left(),
                        icon_rect.top() + 5.0,
                        icon_rect.center().x(),
                        icon_rect.top(),
                    )
                    painter.setPen(QPen(QColor("#74C8FF"), 1.5))
                    painter.setBrush(QColor(116, 200, 255, 30))
                    painter.drawPath(drop)
                    painter.restore()
                else:
                    self._art.draw_icon(
                        painter,
                        icon_rect,
                        detail_icon_path(icon_name),
                    )

                text_rect = QRectF(x + 22.0, y, cell_width - 22.0, 18.0)
                painter.setFont(_font(9.5, QFont.Weight.Medium))
                painter.setPen(QColor("#E0E8F0"))
                text = QFontMetricsF(painter.font()).elidedText(
                    text, Qt.TextElideMode.ElideRight, int(text_rect.width())
                )
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    text,
                )
        painter.restore()

    def _paint_forecast(self, painter: QPainter, strip: QRectF) -> None:
        snapshot = self._weather_state.snapshot
        if snapshot is None or not snapshot.daily:
            return
        days = snapshot.daily[:5]
        if not days:
            return

        left = strip.left() + 10.0
        right = strip.right() - 10.0
        top = strip.top() + 8.0
        column_width = (right - left) / len(days)
        today = self._now.date()

        painter.save()
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        for index, day in enumerate(days):
            column = QRectF(
                left + (len(days) - 1 - index) * column_width,
                top,
                column_width,
                54.0,
            )
            is_today = day.date == today
            if is_today:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(
                    QColor(
                        self._accent.red(),
                        self._accent.green(),
                        self._accent.blue(),
                        20,
                    )
                )
                painter.drawRoundedRect(column.adjusted(3.0, 0.0, -3.0, 0.0), 9.0, 9.0)

            painter.setFont(
                _font(
                    8.0,
                    QFont.Weight.DemiBold
                    if is_today
                    else QFont.Weight.Medium,
                )
            )
            painter.setPen(
                QColor(self._accent if is_today else "#CDD8E2")
            )
            painter.drawText(
                QRectF(column.x(), column.y(), column.width(), 12.0),
                Qt.AlignmentFlag.AlignCenter,
                _persian_weekday_short(day.date),
            )

            icon_rect = QRectF(
                column.center().x() - 12.0,
                column.y() + 13.0,
                24.0,
                24.0,
            )
            visual = resolve_visual(day.weather_code, True)
            if not self._art.draw_icon(painter, icon_rect, visual.icon_path):
                paint_weather_glyph(
                    painter,
                    icon_rect,
                    condition_kind(day.weather_code, True),
                    QColor(self._accent if is_today else TEXT),
                    width=1.4,
                )

            painter.save()
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.setFont(_font(9.2, QFont.Weight.Normal))
            painter.setPen(
                QColor(TEXT if is_today else "#C5D2DF")
            )
            high = loc.number(round(day.temp_max))
            low = loc.number(round(day.temp_min))
            painter.drawText(
                QRectF(column.x(), column.y() + 39.0, column.width(), 14.0),
                Qt.AlignmentFlag.AlignCenter,
                f"{high}° / {low}°",
            )
            painter.restore()
        painter.restore()

    def _paint_footer(self, painter: QPainter, strip: QRectF) -> None:
        state = self._weather_state
        snapshot = state.snapshot
        if snapshot is not None:
            time_text = loc.clock_text(
                snapshot.fetched_at.astimezone(), seconds=False
            )
            if state.status == "loading":
                footer = "در حال به‌روزرسانی…"
            elif state.status == "stale":
                footer = f"ذخیره‌شده • {time_text}"
            else:
                footer = f"آخرین به‌روزرسانی: {time_text}"
            footer_color = QColor("#B9C7D4")
        elif state.status == "error":
            footer = state.message or "هوا در دسترس نیست"
            footer_color = QColor(DANGER)
        elif state.status == "loading":
            footer = "در حال دریافت هوا…"
            footer_color = QColor("#B9C7D4")
        else:
            footer = "برای نمایش هوا، شهر را در تنظیمات انتخاب کنید"
            footer_color = QColor("#B9C7D4")

        left = strip.left() + 10.0
        right = strip.right() - 10.0
        top = strip.bottom() - 13.0
        text_width = max(40.0, right - left - 84.0)
        painter.save()
        painter.setFont(_font(8.0))
        painter.setPen(footer_color)
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        footer = QFontMetricsF(painter.font()).elidedText(
            footer, Qt.TextElideMode.ElideRight, int(text_width)
        )
        painter.drawText(
            QRectF(left, top, text_width, 10.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            footer,
        )

        self._attribution_rect = QRectF()
        if snapshot is not None:
            attr = QRectF(right - 72.0, top, 72.0, 10.0)
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.setFont(_font(7.6, QFont.Weight.Medium))
            attr_color = QColor("#B9C7D4")
            attr_color.setAlpha(178)
            painter.setPen(attr_color)
            painter.drawText(
                attr,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Open-Meteo",
            )
            self._attribution_rect = attr
        painter.restore()

    # ---------------------------------------------------------------- events
    def _base_point(self, position: QPointF) -> QPointF:
        return QPointF(position.x() / self._scale, position.y() / self._scale)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._dragging = False
            self._moved = False
            self._swiping = False
            self._press_global = event.globalPosition().toPoint()
            self._press_offset = self._press_global - self.pos()
            self._press_on_attribution = self._attribution_rect.contains(
                self._base_point(event.position())
            )
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._pressed
            and self._press_global is not None
            and self._press_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            current = event.globalPosition().toPoint()
            delta = current - self._press_global
            if not self._dragging:
                if delta.manhattanLength() >= QApplication.startDragDistance():
                    self._dragging = True
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._dragging:
                horizontal = (
                    abs(delta.x()) >= QApplication.startDragDistance() * 2
                    and abs(delta.x()) > abs(delta.y()) * 1.4
                )
                if horizontal:
                    self._swiping = True
                if not self._swiping:
                    horizontal_candidate = (
                        abs(delta.x()) > abs(delta.y()) * 1.4
                    )
                    if not horizontal_candidate:
                        self.move(current - self._press_offset)
                self._moved = True
        elif not self._pressed:
            over_link = self._attribution_rect.contains(
                self._base_point(event.position())
            )
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
                if over_link
                else Qt.CursorShape.OpenHandCursor
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._dragging
            on_attribution = self._press_on_attribution
            self._pressed = False
            self._dragging = False
            self._press_on_attribution = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()
            if was_dragging:
                if self._swiping:
                    delta = event.globalPosition().toPoint() - (
                        self._press_global or event.globalPosition().toPoint()
                    )
                    self.pageSwipeRequested.emit(1 if delta.x() < 0 else -1)
                else:
                    self.clamp_to_screens()
                    self.save_position()
            elif not self._moved:
                if on_attribution:
                    QDesktopServices.openUrl(QUrl(OPEN_METEO_URL))
                else:
                    self.calendarRequested.emit()
            self._press_global = None
            self._press_offset = None
            self._swiping = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        menu = QMenu(self)
        menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        open_calendar = menu.addAction(make_icon("calendar", TEXT), "باز کردن تقویم")
        settings = menu.addAction(make_icon("settings", TEXT), "تنظیمات")
        refresh = None
        source = None
        if (
            self._weather_state.location is not None
            or self._weather_state.snapshot is not None
        ):
            menu.addSeparator()
            refresh = menu.addAction(
                make_icon("refresh", TEXT), "به‌روزرسانی هوا"
            )
            source = menu.addAction(
                make_icon("globe", TEXT), "منبع دادهٔ هوا: Open-Meteo"
            )
        menu.addSeparator()
        hide = menu.addAction(make_icon("eye-off", TEXT), "مخفی کردن ویجت")
        menu.addSeparator()
        quit_action = menu.addAction(make_icon("power", "#FF8A99"), "خروج")
        chosen = menu.exec(event.globalPos())
        if chosen is open_calendar:
            self.calendarRequested.emit()
        elif chosen is settings:
            self.settingsRequested.emit()
        elif refresh is not None and chosen is refresh:
            self.weatherRefreshRequested.emit()
        elif source is not None and chosen is source:
            QDesktopServices.openUrl(QUrl(OPEN_METEO_URL))
        elif chosen is hide:
            self.hideRequested.emit()
        elif chosen is quit_action:
            self.quitRequested.emit()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.save_position()
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # type: ignore[override]
        self.clamp_to_screens()
        super().showEvent(event)
