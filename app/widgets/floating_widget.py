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
    QPropertyAnimation,
    QRectF,
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
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from app.calendar import localization as loc
from app.calendar.holidays import CalendarEvent
from app.calendar.jalali import JalaliDate, today as jalali_today
from app.storage.settings import SettingsValues
from app.ui.components import make_icon
from app.ui.styles import DANGER, DIM, MUTED, TEXT, font_family
from app.weather.conditions import condition_kind, condition_text
from app.weather.icons import paint_weather_glyph
from app.weather.models import WeatherState

BASE_WIDTH = 320
BASE_HEIGHT = 250
BASE_RADIUS = 22
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


class FloatingWidget(QWidget):
    calendarRequested = Signal()
    settingsRequested = Signal()
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
        self._attribution_rect = QRectF()
        self._press_on_attribution = False
        self._hover = False
        self._pressed = False
        self._dragging = False
        self._press_global: QPoint | None = None
        self._press_offset: QPoint | None = None
        self._moved = False

        self._weather_animation = QPropertyAnimation(self, b"weatherReveal", self)
        self._weather_animation.setDuration(220)
        self._weather_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

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
        self.setWindowOpacity(max(0.6, min(1.0, values.opacity / 100.0)))
        self._apply_topmost()
        if self.isVisible():
            self.move(
                old_center.x() - self.width() // 2,
                old_center.y() - self.height() // 2,
            )
            self.clamp_to_screens()
        self.update()

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
        if state.snapshot is not None and state.snapshot != previous.snapshot:
            self._weather_animation.stop()
            self._weather_animation.setStartValue(0.25)
            self._weather_animation.setEndValue(1.0)
            self._weather_animation.start()
        elif state.snapshot is None:
            self._weather_reveal = 1.0
        self._update_tooltip()
        self.update()

    def get_weather_reveal(self) -> float:
        return self._weather_reveal

    def set_weather_reveal(self, value: float) -> None:
        self._weather_reveal = max(0.0, min(1.0, float(value)))
        self.update()

    weatherReveal = Property(float, get_weather_reveal, set_weather_reveal)

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
        self._paint_card(painter, card, path)
        self._paint_contents(painter, w, h)
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

    def _paint_card(self, painter: QPainter, card: QRectF, path: QPainterPath) -> None:
        gradient = QLinearGradient(card.topLeft(), card.bottomLeft())
        gradient.setColorAt(0.0, QColor("#1B2634"))
        gradient.setColorAt(0.42, QColor("#111923"))
        gradient.setColorAt(1.0, QColor("#090E15"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        glow = QRadialGradient(
            QPointF(card.right() - 20, card.top() + 8), card.width() * 0.55
        )
        glow.setColorAt(
            0.0,
            QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 38),
        )
        glow.setColorAt(
            0.55,
            QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 10),
        )
        glow.setColorAt(
            1.0,
            QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 0),
        )
        painter.setBrush(glow)
        painter.drawRect(card)

        glass = QLinearGradient(card.topLeft(), card.bottomRight())
        glass.setColorAt(0.0, QColor(255, 255, 255, 14))
        glass.setColorAt(0.46, QColor(255, 255, 255, 3))
        glass.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(glass)
        painter.drawRect(card)
        painter.restore()

        if self._pressed and not self._dragging:
            painter.setBrush(QColor(255, 255, 255, 8))
            painter.drawPath(path)

        border_color = QColor(self._accent)
        border_color.setAlpha(112 if self._hover else 44)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 1.0))
        painter.drawPath(path)

        inner = QPainterPath()
        inner.addRoundedRect(card.adjusted(1.0, 1.0, -1.0, -1.0), BASE_RADIUS - 1, BASE_RADIUS - 1)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 0.8))
        painter.drawPath(inner)

        # A restrained accent rule on the RTL-leading edge.
        rule = QRectF(
            card.right() - 3.0,
            card.top() + 30.0,
            2.2,
            card.height() - 60.0,
        )
        rule_color = QColor(self._accent)
        rule_color.setAlpha(180)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(rule_color)
        painter.drawRoundedRect(rule, 1.1, 1.1)

    def _paint_contents(self, painter: QPainter, w: float, h: float) -> None:
        left = CARD_MARGIN + 12.0
        right = w - CARD_MARGIN - 12.0
        top = CARD_MARGIN + 10.0

        # "Today" pill, top-left.
        pill = QRectF(left, top, 50, 20)
        pill_color = QColor(self._accent)
        pill_color.setAlpha(30)
        painter.setPen(
            QPen(
                QColor(
                    self._accent.red(),
                    self._accent.green(),
                    self._accent.blue(),
                    78,
                ),
                0.8,
            )
        )
        painter.setBrush(pill_color)
        painter.drawRoundedRect(pill, 10, 10)
        painter.setFont(_font(8, QFont.Weight.DemiBold))
        painter.setPen(self._accent)
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, "امروز")

        # Weekday, top-right.
        painter.setFont(_font(11, QFont.Weight.Medium))
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRectF(right - 118, top, 118, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            loc.weekday_of(self._today),
        )

        # Big day number.
        painter.setFont(_font(40, QFont.Weight.Bold))
        painter.setPen(QColor(self._accent).lighter(120))
        painter.drawText(
            QRectF(right - 72, top + 18, 72, 48),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            loc.day_number(self._today),
        )

        # Month and year.
        painter.setFont(_font(11, QFont.Weight.Medium))
        painter.setPen(QColor(TEXT))
        painter.drawText(
            QRectF(right - 160, top + 68, 160, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{loc.month_name(self._today.month)} {loc.number(self._today.year)}",
        )

        # Clock, drawn LTR so the colon and seconds keep their order.
        hhmm, seconds = loc.clock_parts(self._now)
        painter.save()
        painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        time_font = _font(29, QFont.Weight.DemiBold)
        painter.setFont(time_font)
        painter.setPen(QColor(TEXT))
        painter.drawText(
            QRectF(left, top + 28, 140, 34),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            hhmm,
        )
        time_width = QFontMetricsF(time_font).horizontalAdvance(hhmm)
        painter.setFont(_font(9, QFont.Weight.Medium))
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRectF(left + time_width + 3, top + 41, 40, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            seconds,
        )
        painter.restore()

        # Gregorian date.
        if self._show_gregorian:
            painter.setFont(_font(9))
            painter.setPen(QColor(DIM))
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.drawText(
                QRectF(left, top + 68, 160, 18),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                loc.gregorian_text(self._now.date()),
            )
            painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        divider_y = top + 92.0
        painter.setPen(QPen(QColor(255, 255, 255, 14), 0.8))
        painter.drawLine(QPointF(left, divider_y), QPointF(right, divider_y))

        weather_top = divider_y + 6.0
        self._paint_weather_card(painter, left, right, weather_top)
        forecast_top = weather_top + 61.0
        self._paint_forecast(painter, left, right, forecast_top)
        self._paint_footer(painter, left, right, forecast_top + 47.0)

        # Day progress.
        track = QRectF(left, h - CARD_MARGIN - 10.0, right - left, 2.2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 16))
        painter.drawRoundedRect(track, 1.1, 1.1)
        fill_width = max(2.0, track.width() * loc.day_progress(self._now))
        fill = QColor(self._accent)
        fill.setAlpha(155)
        painter.setBrush(fill)
        painter.drawRoundedRect(
            QRectF(track.x(), track.y(), fill_width, track.height()), 1.1, 1.1
        )

    def _paint_weather_card(
        self, painter: QPainter, left: float, right: float, top: float
    ) -> None:
        card = QRectF(left, top, right - left, 56)
        painter.setPen(
            QPen(
                QColor(
                    self._accent.red(),
                    self._accent.green(),
                    self._accent.blue(),
                    26,
                ),
                0.8,
            )
        )
        painter.setBrush(QColor(255, 255, 255, 7))
        painter.drawRoundedRect(card, 13, 13)

        state = self._weather_state
        snapshot = state.snapshot
        location = snapshot.location if snapshot is not None else state.location
        data_color = QColor(TEXT)
        muted = QColor(MUTED)
        icon_color = QColor(self._accent if snapshot is not None else MUTED)
        if snapshot is None:
            icon_color.setAlpha(150)

        painter.save()
        painter.setOpacity(self._weather_reveal)
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        icon_rect = QRectF(left + 10, top + 10, 34, 34)
        if snapshot is not None:
            paint_weather_glyph(
                painter,
                icon_rect,
                condition_kind(snapshot.weather_code, snapshot.is_day),
                icon_color,
                width=2.4,
            )
        else:
            paint_weather_glyph(painter, icon_rect, "cloudy", icon_color, width=2.0)

        # City and status.
        city_rect = QRectF(right - 145, top + 3, 145, 18)
        painter.setFont(_font(10, QFont.Weight.DemiBold))
        painter.setPen(data_color)
        city_name = location.display_name if location is not None else "هوا"
        city_name = QFontMetricsF(painter.font()).elidedText(
            city_name, Qt.TextElideMode.ElideRight, int(city_rect.width())
        )
        painter.drawText(
            city_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            city_name,
        )

        # Large current temperature.
        temp_rect = QRectF(left + 50, top + 1, 86, 31)
        if snapshot is not None:
            painter.setFont(_font(25, QFont.Weight.DemiBold))
            painter.setPen(data_color)
            temp = _temperature_text(snapshot.temperature)
            painter.drawText(
                temp_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{temp}°",
            )
            temp_width = QFontMetricsF(painter.font()).horizontalAdvance(f"{temp}°")
            painter.save()
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.setFont(_font(8, QFont.Weight.Medium))
            painter.setPen(muted)
            painter.drawText(
                QRectF(temp_rect.x() + temp_width + 2, temp_rect.y() + 15, 24, 14),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                snapshot.temperature_symbol[-1],
            )
            painter.restore()
        else:
            painter.setFont(_font(25, QFont.Weight.DemiBold))
            painter.setPen(QColor(DIM))
            painter.drawText(
                temp_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "…",
            )

        # Condition line.
        condition_rect = QRectF(left + 50, top + 32, 86, 16)
        if snapshot is not None:
            condition = condition_text(snapshot.weather_code)
            condition_color = data_color
        elif state.status == "loading":
            condition = "در حال دریافت…"
            condition_color = muted
        elif state.status == "error":
            condition = "هوا در دسترس نیست"
            condition_color = QColor(DANGER)
        else:
            condition = "شهر را انتخاب کنید"
            condition_color = muted
        painter.setFont(_font(9, QFont.Weight.Medium))
        painter.setPen(condition_color)
        condition = QFontMetricsF(painter.font()).elidedText(
            condition, Qt.TextElideMode.ElideRight, int(condition_rect.width())
        )
        painter.drawText(
            condition_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            condition,
        )

        # Humidity, wind and today's high/low.
        detail_rect = QRectF(right - 145, top + 22, 145, 15)
        high_low_rect = QRectF(right - 145, top + 38, 145, 15)
        if snapshot is not None:
            details: list[str] = []
            if snapshot.humidity is not None:
                details.append(f"رطوبت {loc.percent_text(snapshot.humidity)}")
            if snapshot.wind_speed is not None:
                details.append(
                    f"باد {loc.number(round(snapshot.wind_speed))} "
                    f"{snapshot.wind_speed_label}"
                )
            painter.setFont(_font(8, QFont.Weight.Normal))
            painter.setPen(muted)
            detail_text = " • ".join(details) or "دادهٔ تکمیلی موجود نیست"
            detail_text = QFontMetricsF(painter.font()).elidedText(
                detail_text, Qt.TextElideMode.ElideRight, int(detail_rect.width())
            )
            painter.drawText(
                detail_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                detail_text,
            )
            if snapshot.daily:
                today_forecast = next(
                    (day for day in snapshot.daily if day.date == self._now.date()),
                    snapshot.daily[0],
                )
                high = loc.number(round(today_forecast.temp_max))
                low = loc.number(round(today_forecast.temp_min))
                painter.setPen(QColor(self._accent).lighter(112))
                painter.drawText(
                    high_low_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"بیشینه {high}° • کمینه {low}°",
                )
        painter.restore()

    def _paint_forecast(
        self, painter: QPainter, left: float, right: float, top: float
    ) -> None:
        painter.setPen(QPen(QColor(255, 255, 255, 12), 0.8))
        painter.drawLine(QPointF(left, top - 3), QPointF(right, top - 3))
        snapshot = self._weather_state.snapshot
        if snapshot is None or not snapshot.daily:
            return
        days = snapshot.daily[:5]
        if not days:
            return
        column_width = (right - left) / len(days)
        today = self._now.date()
        painter.save()
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        for index, day in enumerate(days):
            column = QRectF(
                left + (len(days) - 1 - index) * column_width, top, column_width, 42
            )
            is_today = day.date == today
            if is_today:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(
                    QColor(
                        self._accent.red(),
                        self._accent.green(),
                        self._accent.blue(),
                        18,
                    )
                )
                painter.drawRoundedRect(column.adjusted(1, 0, -1, 0), 9, 9)
            painter.setFont(_font(8, QFont.Weight.DemiBold if is_today else QFont.Weight.Medium))
            painter.setPen(QColor(self._accent if is_today else MUTED))
            painter.drawText(
                QRectF(column.x(), column.y() + 1, column.width(), 11),
                Qt.AlignmentFlag.AlignCenter,
                _persian_weekday_short(day.date),
            )
            icon_rect = QRectF(
                column.center().x() - 9,
                column.y() + 12,
                18,
                18,
            )
            paint_weather_glyph(
                painter,
                icon_rect,
                condition_kind(day.weather_code, True),
                QColor(self._accent if is_today else TEXT),
                width=1.7,
            )
            painter.setFont(_font(8, QFont.Weight.Normal))
            painter.setPen(QColor(TEXT if is_today else MUTED))
            high = loc.number(round(day.temp_max))
            low = loc.number(round(day.temp_min))
            painter.drawText(
                QRectF(column.x(), column.y() + 30, column.width(), 12),
                Qt.AlignmentFlag.AlignCenter,
                f"{high}° / {low}°",
            )
        painter.restore()

    def _paint_footer(
        self, painter: QPainter, left: float, right: float, top: float
    ) -> None:
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
            footer_color = QColor(DIM)
        elif state.status == "error":
            footer = state.message or "هوا در دسترس نیست"
            footer_color = QColor(DANGER)
        elif state.status == "loading":
            footer = "در حال دریافت هوا…"
            footer_color = QColor(MUTED)
        else:
            footer = "برای نمایش هوا، شهر را در تنظیمات انتخاب کنید"
            footer_color = QColor(DIM)

        text_width = max(40.0, right - left - 78)
        painter.setFont(_font(7.5))
        painter.setPen(footer_color)
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        footer = QFontMetricsF(painter.font()).elidedText(
            footer, Qt.TextElideMode.ElideRight, int(text_width)
        )
        painter.drawText(
            QRectF(left, top, text_width, 12),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            footer,
        )

        self._attribution_rect = QRectF()
        if snapshot is not None:
            attr = QRectF(right - 72, top, 72, 12)
            painter.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            painter.setFont(_font(7.5, QFont.Weight.DemiBold))
            attr_color = QColor(self._accent)
            attr_color.setAlpha(190)
            painter.setPen(attr_color)
            painter.drawText(
                attr,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Open-Meteo",
            )
            self._attribution_rect = attr

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
                self.clamp_to_screens()
                self.save_position()
            elif not self._moved:
                if on_attribution:
                    QDesktopServices.openUrl(QUrl(OPEN_METEO_URL))
                else:
                    self.calendarRequested.emit()
            self._press_global = None
            self._press_offset = None
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
