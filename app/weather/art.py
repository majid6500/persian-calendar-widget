"""Qt-only rendering helpers for bundled weather artwork.

Asset selection stays in :mod:`app.weather.visuals`; this module only turns
selected paths into reusable SVG renderers and background pixmaps.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QImage, QImageReader, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.weather.visuals import all_background_paths, all_icon_paths

logger = logging.getLogger(__name__)


class WeatherArt:
    """Small cache for SVG renderers and decoded/cropped backgrounds."""

    def __init__(self) -> None:
        self._svg: dict[str, QSvgRenderer | None] = {}
        self._backgrounds: dict[tuple[str, int, int, bool], QPixmap | None] = {}

    # ------------------------------------------------------------------ SVG
    def renderer(self, path: Path | str | None) -> QSvgRenderer | None:
        if path is None:
            return None
        key = str(path)
        if key in self._svg:
            return self._svg[key]
        renderer = QSvgRenderer(key)
        if not renderer.isValid():
            logger.warning("Weather SVG could not be loaded: %s", key)
            self._svg[key] = None
            return None
        self._svg[key] = renderer
        return renderer

    def draw_icon(
        self,
        painter: QPainter,
        rect: QRectF,
        path: Path | str | None,
    ) -> bool:
        renderer = self.renderer(path)
        if renderer is None:
            return False
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter, rect)
        painter.restore()
        return True

    # ------------------------------------------------------------ background
    def background(
        self,
        path: Path | str | None,
        target_size: QSize,
        *,
        anchor_right: bool = True,
    ) -> QPixmap | None:
        if path is None or target_size.width() <= 0 or target_size.height() <= 0:
            return None
        key = (str(path), target_size.width(), target_size.height(), anchor_right)
        if key in self._backgrounds:
            return self._backgrounds[key]

        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            logger.warning(
                "Weather background could not be loaded: %s (%s)",
                path,
                reader.errorString(),
            )
            self._backgrounds[key] = None
            return None

        scaled = image.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = 0
        if scaled.width() > target_size.width():
            x = (
                scaled.width() - target_size.width()
                if anchor_right
                else (scaled.width() - target_size.width()) // 2
            )
        y = max(0, (scaled.height() - target_size.height()) // 2)
        cropped = scaled.copy(x, y, target_size.width(), target_size.height())
        pixmap = QPixmap.fromImage(cropped)
        if pixmap.isNull():
            logger.warning("Weather background produced an empty pixmap: %s", path)
            self._backgrounds[key] = None
            return None
        self._backgrounds[key] = pixmap
        return pixmap

    # ------------------------------------------------------------ diagnostics
    def validate_files(self) -> tuple[str, ...]:
        """Decode every supplied asset; return human-readable failures."""
        failures: list[str] = []
        for path in all_icon_paths():
            if self.renderer(path) is None:
                failures.append(f"invalid SVG: {path}")
        for path in all_background_paths():
            if self.background(path, QSize(64, 64)) is None:
                failures.append(f"invalid background: {path}")
        return tuple(failures)
