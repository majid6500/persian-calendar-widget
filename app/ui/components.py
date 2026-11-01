"""Small custom-painted controls shared by the widget and windows."""

from __future__ import annotations

from PySide6.QtCore import (
    QEvent,
    Property,
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Signal,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollBar,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.styles import BORDER, CARD, DANGER, MUTED, TEXT, font_family, rgba


def _glyph_path(kind: str, rect: QRectF) -> list[list[QPoint]]:
    """Line segments for the simple icon set, in logical coordinates."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cx, cy = x + w / 2, y + h / 2

    def p(fx: float, fy: float) -> QPoint:
        return QPoint(round(x + w * fx), round(y + h * fy))

    if kind == "close":
        return [[p(0.32, 0.32), p(0.68, 0.68)], [p(0.68, 0.32), p(0.32, 0.68)]]
    if kind == "chevron-right":
        return [[p(0.42, 0.30), p(0.60, 0.50), p(0.42, 0.70)]]
    if kind == "chevron-left":
        return [[p(0.58, 0.30), p(0.40, 0.50), p(0.58, 0.70)]]
    if kind == "chevron-down":
        return [[p(0.30, 0.42), p(0.50, 0.60), p(0.70, 0.42)]]
    if kind == "settings":
        return [
            [p(0.30, 0.35), p(0.70, 0.35)],
            [p(0.30, 0.50), p(0.70, 0.50)],
            [p(0.30, 0.65), p(0.70, 0.65)],
        ]
    if kind == "calendar":
        return [
            [p(0.27, 0.35), p(0.73, 0.35)],
            [p(0.35, 0.25), p(0.35, 0.38)],
            [p(0.65, 0.25), p(0.65, 0.38)],
        ]
    if kind == "today":
        return [[p(0.50, 0.28), p(0.50, 0.50), p(0.66, 0.50)]]
    if kind == "power":
        return [[p(0.50, 0.26), p(0.50, 0.50)]]
    if kind == "refresh":
        return []
    if kind == "globe":
        return []
    if kind == "eye":
        return []
    if kind == "eye-off":
        return [[p(0.30, 0.68), p(0.70, 0.32)]]
    return []


def paint_glyph(
    painter: QPainter, rect: QRectF, kind: str, color: QColor, width: float = 1.7
) -> None:
    painter.save()
    painter.setPen(
        QPen(
            color,
            width,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for segment in _glyph_path(kind, rect):
        painter.drawPolyline(segment)
    if kind == "calendar":
        painter.drawRoundedRect(
            QRectF(
                rect.x() + rect.width() * 0.24,
                rect.y() + rect.height() * 0.34,
                rect.width() * 0.52,
                rect.height() * 0.42,
            ),
            2.0,
            2.0,
        )
        painter.setBrush(color)
        for fx, fy in ((0.40, 0.55), (0.50, 0.55), (0.60, 0.55), (0.40, 0.66), (0.50, 0.66), (0.60, 0.66)):
            painter.drawEllipse(
                QRectF(
                    rect.x() + rect.width() * fx - 0.9,
                    rect.y() + rect.height() * fy - 0.9,
                    1.8,
                    1.8,
                )
            )
    elif kind == "today":
        painter.drawEllipse(rect.adjusted(rect.width() * 0.20, rect.height() * 0.20, -rect.width() * 0.20, -rect.height() * 0.20))
        painter.setBrush(color)
        painter.drawEllipse(rect.center(), 1.7, 1.7)
    elif kind == "power":
        path = QPainterPath()
        arc_rect = rect.adjusted(
            rect.width() * 0.22,
            rect.height() * 0.22,
            -rect.width() * 0.22,
            -rect.height() * 0.22,
        )
        path.arcMoveTo(arc_rect, 125)
        path.arcTo(arc_rect, 125, 290)
        painter.drawPath(path)
    elif kind == "refresh":
        arc_rect = rect.adjusted(
            rect.width() * 0.20,
            rect.height() * 0.20,
            -rect.width() * 0.20,
            -rect.height() * 0.20,
        )
        path = QPainterPath()
        path.arcMoveTo(arc_rect, 40)
        path.arcTo(arc_rect, 40, 285)
        painter.drawPath(path)
        arrow = QPointF(
            rect.x() + rect.width() * 0.74,
            rect.y() + rect.height() * 0.28,
        )
        painter.drawLine(arrow, arrow + QPointF(-rect.width() * 0.10, -rect.height() * 0.04))
        painter.drawLine(arrow, arrow + QPointF(-rect.width() * 0.08, rect.height() * 0.12))
    elif kind == "globe":
        circle = rect.adjusted(
            rect.width() * 0.17,
            rect.height() * 0.17,
            -rect.width() * 0.17,
            -rect.height() * 0.17,
        )
        painter.drawEllipse(circle)
        painter.drawEllipse(
            QRectF(
                circle.center().x() - circle.width() * 0.20,
                circle.top(),
                circle.width() * 0.40,
                circle.height(),
            )
        )
        painter.drawLine(
            QPointF(circle.left(), circle.center().y()),
            QPointF(circle.right(), circle.center().y()),
        )
        painter.drawArc(
            QRectF(
                circle.left(),
                circle.center().y() - circle.height() * 0.22,
                circle.width(),
                circle.height() * 0.44,
            ),
            0,
            180 * 16,
        )
        painter.drawArc(
            QRectF(
                circle.left(),
                circle.center().y() - circle.height() * 0.22,
                circle.width(),
                circle.height() * 0.44,
            ),
            180 * 16,
            180 * 16,
        )
    elif kind in {"eye", "eye-off"}:
        eye = QPainterPath()
        eye.moveTo(rect.x() + rect.width() * 0.22, rect.center().y())
        eye.quadTo(
            rect.center().x(),
            rect.y() + rect.height() * 0.28,
            rect.x() + rect.width() * 0.78,
            rect.center().y(),
        )
        eye.quadTo(
            rect.center().x(),
            rect.y() + rect.height() * 0.72,
            rect.x() + rect.width() * 0.22,
            rect.center().y(),
        )
        painter.drawPath(eye)
        painter.setBrush(color)
        painter.drawEllipse(rect.center(), rect.width() * 0.09, rect.width() * 0.09)
        if kind == "eye-off":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(
                QPoint(round(rect.x() + rect.width() * 0.30), round(rect.y() + rect.height() * 0.68)),
                QPoint(round(rect.x() + rect.width() * 0.70), round(rect.y() + rect.height() * 0.32)),
            )
    painter.restore()


def make_icon(kind: str, color: str = TEXT, size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    margin = size * 0.22
    paint_glyph(
        painter,
        QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
        kind,
        QColor(color),
        max(1.4, size / 30),
    )
    painter.end()
    return QIcon(pixmap)


class IconButton(QAbstractButton):
    def __init__(
        self,
        kind: str,
        size: int = 32,
        color: str = MUTED,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self._color = QColor(color)
        self._hover = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bounds = QRectF(self.rect())
        if self._hover and self.isEnabled():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 16 if not self.isDown() else 26))
            painter.drawRoundedRect(bounds.adjusted(1, 1, -1, -1), 9, 9)
        color = QColor(self._color)
        if not self.isEnabled():
            color.setAlpha(90)
        paint_glyph(
            painter,
            bounds.adjusted(
                self.width() * 0.27,
                self.height() * 0.27,
                -self.width() * 0.27,
                -self.height() * 0.27,
            ),
            self.kind,
            color,
            max(1.3, self.width() / 20),
        )
        painter.end()


class ToggleSwitch(QAbstractButton):
    def __init__(
        self, accent: str = "#6EA8FF", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._accent = QColor(accent)
        self._knob = 0.0
        self._animation = QPropertyAnimation(self, b"knob", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_accent(self, accent: str) -> None:
        self._accent = QColor(accent)
        self.update()

    def get_knob(self) -> float:
        return self._knob

    def set_knob(self, value: float) -> None:
        self._knob = max(0.0, min(1.0, float(value)))
        self.update()

    knob = Property(float, get_knob, set_knob)

    def set_checked(self, checked: bool, animate: bool = True) -> None:
        self.blockSignals(True)
        self.setChecked(bool(checked))
        self.blockSignals(False)
        target = 1.0 if checked else 0.0
        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._knob)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._animation.stop()
            self.set_knob(target)

    def nextCheckState(self) -> None:  # type: ignore[override]
        super().nextCheckState()
        target = 1.0 if self.isChecked() else 0.0
        self._animation.stop()
        self._animation.setStartValue(self._knob)
        self._animation.setEndValue(target)
        self._animation.start()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = QRectF(1, 2, self.width() - 2, self.height() - 4)
        off = QColor("#2B323D")
        on = self._accent
        color = QColor(
            round(off.red() + (on.red() - off.red()) * self._knob),
            round(off.green() + (on.green() - off.green()) * self._knob),
            round(off.blue() + (on.blue() - off.blue()) * self._knob),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        diameter = self.height() - 8
        left = 3 + (self.width() - diameter - 6) * self._knob
        painter.setBrush(QColor("#F4F6FA"))
        painter.drawEllipse(QRectF(left, 4, diameter, diameter))
        painter.end()


class ColorSwatch(QAbstractButton):
    def __init__(
        self, color: str, tooltip: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.color = QColor(color)
        self.setCheckable(True)
        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._hover = False

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        self.update()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        circle = QRectF(4, 4, self.width() - 8, self.height() - 8)
        if self.isChecked():
            painter.setPen(QPen(QColor(self.color).lighter(135), 2))
            painter.setBrush(QColor(self.color))
            painter.drawEllipse(circle)
            painter.setPen(
                QPen(
                    QColor("#0B0D11"),
                    2.2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPolyline(
                [
                    QPoint(round(self.width() * 0.34), round(self.height() * 0.52)),
                    QPoint(round(self.width() * 0.46), round(self.height() * 0.64)),
                    QPoint(round(self.width() * 0.68), round(self.height() * 0.38)),
                ]
            )
        else:
            painter.setPen(
                QPen(
                    QColor(255, 255, 255, 60 if self._hover else 28),
                    1.5,
                )
            )
            painter.setBrush(QColor(self.color))
            painter.drawEllipse(circle)
        painter.end()


class Chip(QLabel):
    def __init__(
        self,
        text: str = "",
        color: str = MUTED,
        background: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.apply_color(color, background)

    def apply_color(self, color: str, background: str | None = None) -> None:
        bg = background or rgba(color, 30)
        border = rgba(color, 70)
        self.setStyleSheet(
            f"color: {color}; background: {bg}; border: 1px solid {border};"
            "border-radius: 8px; padding: 2px 8px; font-size: 8.5pt;"
        )


class TitleBar(QWidget):
    """Draggable header for frameless windows."""

    def __init__(self, window: QWidget, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._drag_origin: QPoint | None = None
        self._window_origin: QPoint | None = None
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.icon = QLabel()
        self.icon.setFixedSize(20, 20)
        self.icon.setPixmap(make_icon("calendar", "#A9B4C6", 40).pixmap(18, 18))
        row.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        row.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)

        self.actions = row

    def add_action(self, widget: QWidget) -> None:
        self.actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._window_origin = self._window.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._drag_origin is not None
            and self._window_origin is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = event.globalPosition().toPoint() - self._drag_origin
            self._window.move(self._window_origin + delta)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_origin = None
        self._window_origin = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


class FramelessWindow(QWidget):
    """Rounded, shadowed, draggable window shell."""

    swipeRequested = Signal(int)
    backRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        shadow: bool = True,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._embedded = embedded
        self._swipe_origin: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.Widget
            if embedded
            else (
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Window
            )
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        outer = QVBoxLayout(self)
        margin = 0 if embedded else 22
        outer.setContentsMargins(margin, margin, margin, margin)
        outer.setSpacing(0)

        self.card = QWidget(self)
        self.card.setObjectName("embeddedCard" if embedded else "card")
        outer.addWidget(self.card)

        if shadow and not embedded:
            effect = QGraphicsDropShadowEffect(self.card)
            effect.setBlurRadius(38)
            effect.setOffset(0, 10)
            effect.setColor(QColor(0, 0, 0, 175))
            self.card.setGraphicsEffect(effect)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(
            18,
            12 if embedded else 14,
            18 if embedded else 18,
            12 if embedded else 18,
        )
        self.card_layout.setSpacing(10)

        self.title_bar = TitleBar(self)
        self.card_layout.addWidget(self.title_bar)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        self.card_layout.addLayout(self.body, 1)
        if embedded:
            self.setMouseTracking(True)
            self._install_swipe_filter()

    def _install_swipe_filter(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _remove_swipe_filter(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if not self._embedded or not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)
        if watched is not self and not self.isAncestorOf(watched):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.backRequested.emit()
            return True
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                if isinstance(
                    watched,
                    (
                        QAbstractButton,
                        QAbstractItemView,
                        QComboBox,
                        QLineEdit,
                        QSlider,
                        QScrollBar,
                    ),
                ) or watched.property("swipeIgnore"):
                    self._swipe_origin = None
                else:
                    self._swipe_origin = event.globalPosition().toPoint()
        elif (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and self._swipe_origin is not None
        ):
            delta = event.globalPosition().toPoint() - self._swipe_origin
            if (
                abs(delta.x()) >= QApplication.startDragDistance() * 2
                and abs(delta.x()) > abs(delta.y()) * 1.4
            ):
                self.swipeRequested.emit(1 if delta.x() < 0 else -1)
            self._swipe_origin = None
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # type: ignore[override]
        if self._embedded:
            self._install_swipe_filter()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        if self._embedded:
            self._remove_swipe_filter()
            self._swipe_origin = None
        super().hideEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._embedded:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._embedded:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def show_near(self, anchor: QWidget | None = None) -> None:
        target_screen = None
        if anchor is not None and anchor.isVisible():
            target_screen = anchor.screen()
        if target_screen is None:
            target_screen = self.screen()
            if target_screen is None:
                from PySide6.QtGui import QGuiApplication

                target_screen = QGuiApplication.primaryScreen()
        available = target_screen.availableGeometry() if target_screen else None

        if anchor is not None and anchor.isVisible():
            geo = anchor.frameGeometry()
            x = geo.right() - self.width() + 1
            y = geo.bottom() + 10
            if available and y + self.height() > available.bottom():
                y = geo.top() - self.height() - 10
        elif available:
            x = available.center().x() - self.width() // 2
            y = available.center().y() - self.height() // 2
        else:
            x, y = 100, 100

        if available:
            x = max(available.left() + 8, min(x, available.right() - self.width() - 8))
            y = max(available.top() + 8, min(y, available.bottom() - self.height() - 8))
        self.move(int(x), int(y))

    def show_with_fade(self) -> None:
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(130)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self.animation = animation  # keep a reference


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line
