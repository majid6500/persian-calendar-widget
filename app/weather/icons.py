"""Small custom-painted weather glyphs, matching the widget's line style."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


def _point(rect: QRectF, fx: float, fy: float) -> QPointF:
    return QPointF(rect.x() + rect.width() * fx, rect.y() + rect.height() * fy)


def _pen(color: QColor, width: float) -> QPen:
    return QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )


def _cloud_path(rect: QRectF) -> QPainterPath:
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    path = QPainterPath()
    path.addEllipse(QRectF(x + 0.08 * w, y + 0.40 * h, 0.50 * w, 0.42 * h))
    path.addEllipse(QRectF(x + 0.30 * w, y + 0.18 * h, 0.48 * w, 0.56 * h))
    path.addEllipse(QRectF(x + 0.56 * w, y + 0.40 * h, 0.36 * w, 0.38 * h))
    path.addRoundedRect(
        QRectF(x + 0.10 * w, y + 0.53 * h, 0.80 * w, 0.27 * h),
        0.13 * w,
        0.13 * w,
    )
    return path.simplified()


def _draw_sun(painter: QPainter, rect: QRectF, color: QColor, width: float) -> None:
    center = rect.center()
    radius = min(rect.width(), rect.height()) * 0.19
    painter.setPen(_pen(color, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center, radius, radius)
    for index in range(8):
        angle = index * 45
        painter.save()
        painter.translate(center)
        painter.rotate(angle)
        painter.drawLine(QPointF(0, -radius * 1.45), QPointF(0, -radius * 2.05))
        painter.restore()


def _draw_moon(painter: QPainter, rect: QRectF, color: QColor) -> None:
    outer = QPainterPath()
    outer.addEllipse(rect.adjusted(rect.width() * 0.25, rect.height() * 0.16, -rect.width() * 0.20, -rect.height() * 0.16))
    cut = QPainterPath()
    cut.addEllipse(rect.adjusted(rect.width() * 0.47, rect.height() * 0.06, -rect.width() * 0.02, -rect.height() * 0.28))
    moon = outer.subtracted(cut)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPath(moon)


def _draw_cloud(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    width: float,
) -> None:
    path = _cloud_path(rect)
    fill = QColor(color)
    fill.setAlpha(34)
    painter.setPen(_pen(color, width))
    painter.setBrush(fill)
    painter.drawPath(path)


def _draw_rain(painter: QPainter, rect: QRectF, color: QColor, width: float, count: int = 3) -> None:
    painter.setPen(_pen(color, width))
    for index in range(count):
        fx = 0.32 + index * 0.18
        painter.drawLine(_point(rect, fx, 0.82), _point(rect, fx - 0.06, 0.97))


def _draw_snow(painter: QPainter, rect: QRectF, color: QColor, width: float) -> None:
    painter.setPen(_pen(color, max(1.0, width * 0.82)))
    for index in range(3):
        center = _point(rect, 0.34 + index * 0.18, 0.89)
        size = rect.width() * 0.045
        painter.drawLine(center + QPointF(-size, 0), center + QPointF(size, 0))
        painter.drawLine(center + QPointF(0, -size), center + QPointF(0, size))
        painter.drawLine(center + QPointF(-size * 0.7, -size * 0.7), center + QPointF(size * 0.7, size * 0.7))
        painter.drawLine(center + QPointF(-size * 0.7, size * 0.7), center + QPointF(size * 0.7, -size * 0.7))


def _draw_thunder(painter: QPainter, rect: QRectF, color: QColor, width: float) -> None:
    painter.setPen(_pen(color, width))
    bolt = QPainterPath()
    bolt.moveTo(_point(rect, 0.53, 0.78))
    bolt.lineTo(_point(rect, 0.42, 0.92))
    bolt.lineTo(_point(rect, 0.54, 0.92))
    bolt.lineTo(_point(rect, 0.48, 1.02))
    bolt.lineTo(_point(rect, 0.70, 0.86))
    bolt.lineTo(_point(rect, 0.58, 0.86))
    bolt.lineTo(_point(rect, 0.64, 0.78))
    painter.setBrush(color)
    painter.drawPath(bolt)


def paint_weather_glyph(
    painter: QPainter,
    rect: QRectF,
    kind: str,
    color: str | QColor,
    width: float | None = None,
) -> None:
    """Paint a weather icon inside ``rect`` without external image assets."""
    glyph_color = QColor(color)
    stroke = width if width is not None else max(1.2, rect.width() * 0.065)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if kind == "clear":
        _draw_sun(painter, rect, glyph_color, stroke)
        painter.restore()
        return
    if kind == "clear-night":
        _draw_moon(painter, rect, glyph_color)
        painter.restore()
        return

    if kind in {"partly", "partly-night"}:
        small = QRectF(
            rect.x() + rect.width() * 0.08,
            rect.y() + rect.height() * 0.02,
            rect.width() * 0.62,
            rect.height() * 0.62,
        )
        if kind == "partly":
            _draw_sun(painter, small, glyph_color, stroke * 0.85)
        else:
            _draw_moon(painter, small, glyph_color)
        cloud = QRectF(
            rect.x() + rect.width() * 0.18,
            rect.y() + rect.height() * 0.32,
            rect.width() * 0.80,
            rect.height() * 0.58,
        )
        _draw_cloud(painter, cloud, glyph_color, stroke)
        painter.restore()
        return

    cloud = QRectF(
        rect.x() + rect.width() * 0.05,
        rect.y() + rect.height() * 0.10,
        rect.width() * 0.90,
        rect.height() * 0.70,
    )
    _draw_cloud(painter, cloud, glyph_color, stroke)

    if kind == "fog":
        painter.setPen(_pen(glyph_color, stroke))
        painter.drawLine(_point(rect, 0.18, 0.86), _point(rect, 0.82, 0.86))
        painter.drawLine(_point(rect, 0.27, 0.98), _point(rect, 0.73, 0.98))
    elif kind in {"drizzle", "rain", "showers"}:
        _draw_rain(painter, rect, glyph_color, stroke, 3 if kind != "showers" else 4)
    elif kind == "snow":
        _draw_snow(painter, rect, glyph_color, stroke)
    elif kind == "thunder":
        _draw_thunder(painter, rect, glyph_color, stroke)

    painter.restore()
