"""Render the application SVG icon to a PNG and a multi-size Windows ICO.

Run with the project virtual environment:
    python tools\\make_icon.py

Qt is used for rendering; the ICO container is assembled with the standard
library so Pillow is not required.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / "assets" / "icons" / "app.svg"
PNG_PATH = ROOT / "assets" / "icons" / "app.png"
ICO_PATH = ROOT / "assets" / "icons" / "app.ico"
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(svg: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    svg.render(painter)
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"could not encode {size}x{size} PNG")
    return bytes(buffer.data())


def write_ico(path: Path, frames: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries = bytearray()
    payload = bytearray()
    for size, data in frames:
        dimension = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII",
            dimension,
            dimension,
            0,  # colour count
            0,  # reserved
            1,  # planes
            32,  # bits per pixel
            len(data),
            offset,
        )
        payload += data
        offset += len(data)
    path.write_bytes(header + bytes(entries) + bytes(payload))


def main() -> int:
    if not SVG_PATH.is_file():
        print(f"missing SVG: {SVG_PATH}", file=sys.stderr)
        return 1
    app = QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(QByteArray(SVG_PATH.read_bytes()))
    if not renderer.isValid():
        print(f"invalid SVG: {SVG_PATH}", file=sys.stderr)
        return 1

    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PNG_PATH.write_bytes(render_png(renderer, 256))
    frames = [(size, render_png(renderer, size)) for size in ICO_SIZES]
    write_ico(ICO_PATH, frames)
    print(f"wrote {PNG_PATH} ({PNG_PATH.stat().st_size} bytes)")
    print(f"wrote {ICO_PATH} ({ICO_PATH.stat().st_size} bytes, {len(frames)} sizes)")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
