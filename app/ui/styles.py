"""Dark neon-glass theme, font loading and application-wide QSS."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.core.paths import assets_path

FONT_FAMILY_FALLBACK = "Segoe UI"

BG = "#070B10"
CARD = "#0F1620"
SURFACE = "#141E2A"
SURFACE_2 = "#1A2634"
BORDER = "#243244"
BORDER_STRONG = "#33465C"
TEXT = "#F2F7FF"
MUTED = "#9BADBF"
DIM = "#71849A"
DANGER = "#FF6B8A"
SUCCESS = "#5BE7C4"

_loaded_family: str | None = None


def rgba(hex_color: str, alpha: int) -> str:
    color = QColor(hex_color)
    return (
        f"rgba({color.red()}, {color.green()}, {color.blue()}, "
        f"{max(0, min(255, int(alpha)))})"
    )


def mix(color_a: str, color_b: str, ratio: float) -> str:
    a, b = QColor(color_a), QColor(color_b)
    ratio = max(0.0, min(1.0, ratio))
    return QColor(
        round(a.red() + (b.red() - a.red()) * ratio),
        round(a.green() + (b.green() - a.green()) * ratio),
        round(a.blue() + (b.blue() - a.blue()) * ratio),
    ).name()


def load_fonts(app: QApplication) -> str:
    """Load the bundled Vazirmatn weights; return the family actually used."""
    global _loaded_family
    if _loaded_family:
        app.setFont(QFont(_loaded_family, 10))
        return _loaded_family

    font_dir = assets_path("fonts")
    candidates = [
        font_dir / "Vazirmatn-Regular.ttf",
        font_dir / "Vazirmatn-Medium.ttf",
        font_dir / "Vazirmatn-SemiBold.ttf",
        font_dir / "Vazirmatn-Bold.ttf",
    ]
    families: set[str] = set()
    for candidate in candidates:
        if candidate.is_file():
            font_id = QFontDatabase.addApplicationFont(str(candidate))
            if font_id >= 0:
                families.update(QFontDatabase.applicationFontFamilies(font_id))

    family = "Vazirmatn" if "Vazirmatn" in families else (
        next(iter(families), FONT_FAMILY_FALLBACK)
    )
    _loaded_family = family
    font = QFont(family, 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    return family


def font_family() -> str:
    return _loaded_family or "Vazirmatn"


def build_stylesheet(accent: str) -> str:
    accent = accent or "#2DD4BF"
    accent_hover = mix(accent, "#FFFFFF", 0.14)
    accent_pressed = mix(accent, "#000000", 0.12)
    accent_soft = rgba(accent, 40)
    accent_softer = rgba(accent, 24)
    accent_border = rgba(accent, 92)

    return f"""
    * {{
        outline: none;
    }}
    QWidget {{
        font-family: "{font_family()}";
        font-size: 10pt;
    }}
    QWidget#card {{
        background: qlineargradient(
            x1: 0, y1: 0, x2: 0, y2: 1,
            stop: 0 #172332,
            stop: 0.55 #101923,
            stop: 1 #0B1119
        );
        border: 1px solid {BORDER};
        border-top: 1px solid {rgba(accent, 46)};
        border-radius: 22px;
    }}
    QWidget#embeddedCard {{
        background-color: rgba(8, 13, 20, 224);
        border: 1px solid rgba(255, 255, 255, 34);
        border-top: 1px solid {rgba(accent, 92)};
        border-radius: 20px;
    }}
    QWidget#transparentRoot {{
        background: transparent;
    }}
    QLabel {{
        color: {TEXT};
        background: transparent;
    }}
    QLabel#muted {{
        color: {MUTED};
    }}
    QLabel#dim {{
        color: {DIM};
    }}
    QLabel#title {{
        font-size: 12pt;
        font-weight: 600;
    }}
    QLabel#sectionTitle {{
        font-size: 10.5pt;
        font-weight: 600;
        color: {TEXT};
    }}
    QLabel#monthTitle {{
        font-size: 21pt;
        font-weight: 700;
        color: {TEXT};
    }}
    QLabel#gregorian {{
        font-size: 9.5pt;
        color: {MUTED};
    }}
    QLabel#selectedDate {{
        font-size: 12pt;
        font-weight: 600;
    }}
    QLabel#eventTitle {{
        font-size: 10pt;
        color: {TEXT};
    }}
    QLabel#eventDescription {{
        font-size: 9pt;
        color: {MUTED};
    }}
    QLabel#errorText {{
        font-size: 9pt;
        color: {DANGER};
    }}
    QLabel#weatherCity {{
        font-size: 11pt;
        font-weight: 600;
        color: {TEXT};
    }}
    QLabel#weatherAttribution {{
        font-size: 8pt;
        color: {MUTED};
    }}
    QLabel#weatherStatus {{
        font-size: 8.5pt;
        color: {MUTED};
    }}
    QFrame#section {{
        background-color: rgba(255, 255, 255, 5);
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}
    QFrame#details {{
        background-color: rgba(255, 255, 255, 4);
        border: 1px solid {BORDER};
        border-radius: 15px;
    }}
    QFrame#monthHeader {{
        background-color: rgba(255, 255, 255, 5);
        border: 1px solid {BORDER};
        border-radius: 15px;
    }}
    QFrame#weatherBox {{
        background-color: rgba(255, 255, 255, 4);
        border: 1px solid {BORDER};
        border-radius: 12px;
    }}
    QFrame#separator {{
        background-color: {BORDER};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}
    QPushButton {{
        background-color: {SURFACE_2};
        border: 1px solid {BORDER_STRONG};
        border-radius: 10px;
        padding: 8px 16px;
        color: {TEXT};
    }}
    QPushButton:hover {{
        background-color: #223246;
        border-color: #405873;
    }}
    QPushButton:pressed {{
        background-color: #101923;
    }}
    QPushButton:disabled {{
        color: {DIM};
        border-color: {BORDER};
    }}
    QPushButton#primary {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #071016;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{
        background-color: {accent_hover};
        border-color: {accent_hover};
    }}
    QPushButton#primary:pressed {{
        background-color: {accent_pressed};
    }}
    QPushButton#ghost {{
        background: transparent;
        border: none;
        color: {MUTED};
        padding: 6px 10px;
    }}
    QPushButton#ghost:hover {{
        background-color: rgba(255, 255, 255, 14);
        color: {TEXT};
    }}
    QPushButton#danger {{
        background: transparent;
        border: none;
        color: {DANGER};
        padding: 6px 10px;
    }}
    QPushButton#danger:hover {{
        background-color: rgba(255, 107, 138, 26);
    }}
    QPushButton#pill {{
        background-color: {accent_softer};
        border: 1px solid {accent_border};
        border-radius: 11px;
        color: {accent};
        padding: 4px 12px;
        font-size: 9pt;
        font-weight: 600;
    }}
    QPushButton#pill:hover {{
        background-color: {accent_soft};
    }}
    QPushButton#chip {{
        background-color: rgba(255, 255, 255, 10);
        border: 1px solid rgba(255, 255, 255, 18);
        border-radius: 8px;
        color: {MUTED};
        padding: 2px 8px;
        font-size: 8.5pt;
    }}
    QLineEdit, QComboBox {{
        background-color: rgba(255, 255, 255, 8);
        border: 1px solid {BORDER_STRONG};
        border-radius: 9px;
        padding: 7px 10px;
        color: {TEXT};
        selection-background-color: {accent_soft};
        selection-color: {TEXT};
    }}
    QLineEdit:focus, QComboBox:focus {{
        border-color: {accent};
        background-color: rgba(255, 255, 255, 11);
    }}
    QLineEdit:disabled, QComboBox:disabled {{
        color: {DIM};
        border-color: {BORDER};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 26px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {SURFACE};
        border: 1px solid {BORDER_STRONG};
        border-radius: 9px;
        padding: 4px;
        color: {TEXT};
        selection-background-color: {accent_softer};
        selection-color: {TEXT};
        outline: none;
    }}
    QListWidget {{
        background-color: rgba(255, 255, 255, 5);
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 4px;
        color: {TEXT};
    }}
    QListWidget::item {{
        padding: 7px 9px;
        border-radius: 7px;
        margin: 1px 2px;
    }}
    QListWidget::item:hover {{
        background-color: rgba(255, 255, 255, 10);
    }}
    QListWidget::item:selected {{
        background-color: {accent_softer};
        border: 1px solid {accent_border};
        color: {TEXT};
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER_STRONG};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {accent};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 7px;
        background: {TEXT};
        border: 2px solid {accent};
    }}
    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
    }}
    QMenu {{
        background-color: {SURFACE};
        border: 1px solid {BORDER_STRONG};
        border-radius: 10px;
        padding: 6px;
        color: {TEXT};
    }}
    QMenu::item {{
        padding: 7px 16px;
        border-radius: 7px;
        margin: 1px 3px;
    }}
    QMenu::item:selected {{
        background-color: {accent_softer};
        color: {TEXT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER};
        margin: 5px 10px;
    }}
    QToolTip {{
        background-color: {SURFACE_2};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        border-radius: 7px;
        padding: 6px 9px;
        opacity: 235;
    }}
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_STRONG};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {accent_border};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    """


def apply_theme(app: QApplication, accent: str) -> None:
    app.setStyleSheet(build_stylesheet(accent))
