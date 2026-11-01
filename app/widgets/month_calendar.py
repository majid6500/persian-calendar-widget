"""Monthly Jalali calendar window with holiday details."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.calendar import localization as loc
from app.calendar.holidays import CalendarEvent, HolidayService
from app.calendar.jalali import (
    JalaliDate,
    add_months,
    clamp_day,
    first_of_month,
    is_friday,
    month_grid,
    today as jalali_today,
)
from app.storage.settings import SettingsValues
from app.ui.components import Chip, FramelessWindow, IconButton, separator
from app.ui.styles import DANGER, MUTED, TEXT, font_family, rgba

CELL_WIDTH = 49
CELL_HEIGHT = 43
CELL_SPACING = 4
NATURAL_WIDTH = 454
NATURAL_HEIGHT = 686


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            # Hide and detach immediately: deleteLater() alone leaves the old
            # widget visible until the event loop runs, which can briefly show
            # stale day cells on top of a freshly rebuilt grid.
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            _clear_layout(child)


class DayCell(QWidget):
    clicked = Signal(object)

    def __init__(
        self,
        date: JalaliDate,
        *,
        in_month: bool,
        is_today: bool,
        is_selected: bool,
        official_holiday: bool,
        has_occasion: bool,
        accent: str,
        parent: QWidget | None = None,
        cell_height: int = CELL_HEIGHT,
    ) -> None:
        super().__init__(parent)
        self.date = date
        self.in_month = in_month
        self.is_today = is_today
        self.is_selected = is_selected
        self.official_holiday = official_holiday
        self.has_occasion = has_occasion
        self.accent = accent
        self._hover = False
        self.setProperty("swipeIgnore", True)
        self.setFixedSize(CELL_WIDTH, cell_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(loc.long_date(date))

    def set_selected(self, selected: bool) -> None:
        if selected != self.is_selected:
            self.is_selected = selected
            self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = QRectF(0.8, 0.8, self.width() - 1.6, self.height() - 1.6)
        accent = QColor(self.accent)
        radius = 10.0

        if self.is_selected:
            painter.setPen(Qt.PenStyle.NoPen)
            selected_fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
            selected_fill.setColorAt(0.0, accent.lighter(114))
            selected_fill.setColorAt(1.0, accent.darker(112))
            painter.setBrush(selected_fill)
            painter.drawRoundedRect(rect, radius, radius)
        else:
            if self.is_today:
                fill = QColor(accent)
                fill.setAlpha(28)
                painter.setBrush(fill)
                border = QColor(accent)
                border.setAlpha(160)
                painter.setPen(QPen(border, 1.2))
            elif self._hover:
                fill = QColor(accent)
                fill.setAlpha(18)
                painter.setBrush(fill)
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, radius, radius)

        text_color = QColor(TEXT)
        if self.is_selected:
            text_color = QColor("#0B0D11")
        elif self.official_holiday or (self.in_month and is_friday(self.date)):
            text_color = QColor(DANGER)
        elif self.is_today:
            text_color = QColor(accent)
        if not self.in_month:
            text_color.setAlpha(70)
        elif not self.is_selected and not self.official_holiday and not is_friday(self.date):
            text_color.setAlpha(225)

        font = QFont(font_family())
        font.setPixelSize(13)
        font.setWeight(
            QFont.Weight.DemiBold
            if (self.is_today or self.is_selected or self.official_holiday)
            else QFont.Weight.Medium
        )
        painter.setFont(font)
        painter.setPen(text_color)
        painter.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        painter.drawText(
            rect.adjusted(0, -3, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            loc.number(self.date.day),
        )

        if self.official_holiday or self.has_occasion:
            dot = QColor(DANGER if self.official_holiday else accent)
            if self.is_selected:
                dot = QColor("#0B0D11")
                dot.setAlpha(150)
            elif not self.in_month:
                dot.setAlpha(80)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot)
            painter.drawEllipse(QRectF(rect.center().x() - 1.4, rect.bottom() - 6.2, 2.8, 2.8))
        painter.end()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit(self.date)
        super().mouseReleaseEvent(event)


class MonthCalendar(FramelessWindow):
    settingsRequested = Signal()
    closeRequested = Signal()

    def __init__(
        self,
        service: HolidayService,
        values: SettingsValues,
        parent: QWidget | None = None,
        *,
        embedded: bool = False,
    ) -> None:
        super().__init__(parent, embedded=embedded)
        self.service = service
        self._accent = values.accent
        self._today: JalaliDate = jalali_today()
        self._selected: JalaliDate = self._today
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._cells: list[DayCell] = []
        self._cell_height = 30 if embedded else CELL_HEIGHT

        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        if not embedded:
            self.setFixedSize(NATURAL_WIDTH, NATURAL_HEIGHT)
        self.title_bar.set_title("تقویم شمسی")

        self.today_button = QPushButton("امروز")
        self.today_button.setObjectName("pill")
        self.today_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.today_button.setFixedHeight(26)
        self.today_button.clicked.connect(self.go_today)
        self.title_bar.add_action(self.today_button)

        self.settings_button = IconButton(
            "settings", 30, MUTED, "تنظیمات", self
        )
        self.settings_button.clicked.connect(self.settingsRequested.emit)
        self.title_bar.add_action(self.settings_button)

        self.close_button = IconButton("close", 30, MUTED, "بستن", self)
        self.close_button.clicked.connect(
            self.closeRequested.emit if embedded else self.hide
        )
        self.title_bar.add_action(self.close_button)

        # Scrollable body for small screens; on normal displays no scrollbar
        # appears because the content fits exactly.
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.body.addWidget(self.scroll, 1)

        self.content = QWidget()
        self.content.setObjectName("transparentRoot")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(3 if self._embedded else 8)
        self.scroll.setWidget(self.content)

        self._build_header()
        self._build_weekdays()
        self._build_grid()
        self._build_details()
        self.set_view(self._today.year, self._today.month, self._today)

    # ------------------------------------------------------------------ build
    def _build_header(self) -> None:
        header = QFrame()
        header.setObjectName("monthHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(8, 3 if self._embedded else 6, 8, 3 if self._embedded else 6)
        row.setSpacing(5 if self._embedded else 8)

        button_size = 28 if self._embedded else 34
        self.prev_button = IconButton("chevron-right", button_size, TEXT, "ماه قبل", self)
        self.prev_button.clicked.connect(self.go_previous)
        self.next_button = IconButton("chevron-left", button_size, TEXT, "ماه بعد", self)
        self.next_button.clicked.connect(self.go_next)

        month_box = QWidget()
        month_layout = QVBoxLayout(month_box)
        month_layout.setContentsMargins(0, 0, 0, 0)
        month_layout.setSpacing(1)
        month_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label = QLabel()
        self.month_label.setObjectName("monthTitle")
        if self._embedded:
            self.month_label.setStyleSheet("font-size: 15pt;")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gregorian_label = QLabel()
        self.gregorian_label.setObjectName("gregorian")
        if self._embedded:
            self.gregorian_label.setStyleSheet("font-size: 8pt;")
        self.gregorian_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        month_layout.addWidget(self.month_label)
        month_layout.addWidget(self.gregorian_label)

        row.addWidget(self.prev_button, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(month_box, 1)
        row.addWidget(self.next_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.content_layout.addWidget(header)

    def _build_weekdays(self) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2 if self._embedded else CELL_SPACING)
        for index in range(7):
            label = QLabel(loc.weekday_short(index))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(CELL_WIDTH)
            label.setStyleSheet(
                f"color: {DANGER if index == 6 else MUTED};"
                f"font-size: {'8pt' if self._embedded else '9pt'}; "
                "font-weight: 600; background: transparent;"
            )
            layout.addWidget(label)
        layout.addStretch(0)
        self.content_layout.addWidget(row)

    def _build_grid(self) -> None:
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(2 if self._embedded else CELL_SPACING)
        self.grid.setVerticalSpacing(1 if self._embedded else CELL_SPACING)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.content_layout.addWidget(self.grid_host)

    def _build_details(self) -> None:
        self.details = QFrame()
        self.details.setObjectName("details")
        self.details.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.details.setMinimumHeight(82 if self._embedded else 148)
        layout = QVBoxLayout(self.details)
        margins = 8 if self._embedded else 14
        layout.setContentsMargins(margins, 6 if self._embedded else 12, margins, 6 if self._embedded else 12)
        layout.setSpacing(3 if self._embedded else 5)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self.selected_label = QLabel()
        self.selected_label.setObjectName("selectedDate")
        top.addWidget(self.selected_label, 1)
        self.chips_row = QHBoxLayout()
        self.chips_row.setContentsMargins(0, 0, 0, 0)
        self.chips_row.setSpacing(5)
        top.addLayout(self.chips_row, 0)
        layout.addLayout(top)

        self.greg_label = QLabel()
        self.greg_label.setObjectName("muted")
        self.greg_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(self.greg_label)
        layout.addWidget(separator())

        self.events_scroll = QScrollArea()
        self.events_scroll.setWidgetResizable(True)
        self.events_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.events_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.events_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.events_host = QWidget()
        self.events_host.setObjectName("transparentRoot")
        self.events_layout = QVBoxLayout(self.events_host)
        self.events_layout.setContentsMargins(0, 2, 0, 0)
        self.events_layout.setSpacing(5)
        self.events_scroll.setWidget(self.events_host)
        layout.addWidget(self.events_scroll, 1)

        self.note_label = QLabel()
        self.note_label.setObjectName("dim")
        self.note_label.setStyleSheet("font-size: 8.5pt;")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)

        self.content_layout.addWidget(self.details, 1)

    # ------------------------------------------------------------------ state
    def _events_for(self, date: JalaliDate) -> tuple[CalendarEvent, ...]:
        return self.service.events_on(date)

    def set_view(
        self, year: int, month: int, select: JalaliDate | None = None
    ) -> None:
        year, month = int(year), int(month)
        if not 1 <= month <= 12:
            year, month = add_months(year, 12, 1)
        self._view_year, self._view_month = year, month
        grid = month_grid(year, month)

        if select is not None:
            self._selected = select
        elif (
            self._selected.year != year or self._selected.month != month
        ):
            self._selected = first_of_month(year, month)

        self._clear_grid()
        for row, week in enumerate(grid.weeks):
            for col, date in enumerate(week):
                events = self._events_for(date)
                official = any(event.official for event in events)
                occasion = any(not event.official for event in events)
                cell = DayCell(
                    date,
                    in_month=(date.year == year and date.month == month),
                    is_today=(date == self._today),
                    is_selected=(date == self._selected),
                    official_holiday=official,
                    has_occasion=occasion,
                    accent=self._accent,
                    parent=self.grid_host,
                    cell_height=self._cell_height,
                )
                cell.clicked.connect(self._on_day_clicked)
                titles = "، ".join(event.title for event in events)
                cell.setToolTip(
                    loc.long_date(date) + (f"\n{titles}" if titles else "")
                )
                self.grid.addWidget(cell, row, col)
                self._cells.append(cell)

        month_date = first_of_month(year, month)
        self.month_label.setText(loc.month_year(month_date))
        self.gregorian_label.setText(loc.gregorian_month_span(year, month))
        self._refresh_details()

    def _clear_grid(self) -> None:
        self._cells.clear()
        _clear_layout(self.grid)

    def _on_day_clicked(self, date: JalaliDate) -> None:
        if date.year != self._view_year or date.month != self._view_month:
            self.set_view(date.year, date.month, date)
            return
        self._selected = date
        for cell in self._cells:
            cell.set_selected(cell.date == date)
        self._refresh_details()

    def go_today(self) -> None:
        self._today = jalali_today()
        self.set_view(self._today.year, self._today.month, self._today)

    def go_previous(self) -> None:
        year, month = add_months(self._view_year, self._view_month, -1)
        day = clamp_day(year, month, self._selected.day)
        self.set_view(year, month, JalaliDate(year, month, day))

    def go_next(self) -> None:
        year, month = add_months(self._view_year, self._view_month, 1)
        day = clamp_day(year, month, self._selected.day)
        self.set_view(year, month, JalaliDate(year, month, day))

    def update_today(self) -> None:
        new_today = jalali_today()
        if new_today != self._today:
            self._today = new_today
            self.set_view(self._view_year, self._view_month, self._selected)

    # --------------------------------------------------------------- details
    def _refresh_details(self) -> None:
        selected = self._selected
        events = self._events_for(selected)
        official = any(event.official for event in events)
        occasion = any(not event.official for event in events)

        self.selected_label.setText(loc.long_date(selected))
        self.greg_label.setText(
            "میلادی: " + loc.gregorian_text(selected.togregorian())
        )

        _clear_layout(self.chips_row)
        if selected == self._today:
            self.chips_row.addWidget(Chip("امروز", self._accent))
        if official:
            self.chips_row.addWidget(Chip("تعطیل رسمی", DANGER))
        elif is_friday(selected):
            self.chips_row.addWidget(Chip("جمعه", MUTED))
        if occasion:
            self.chips_row.addWidget(Chip("مناسبت", self._accent))

        _clear_layout(self.events_layout)
        if events:
            for event in events:
                self.events_layout.addWidget(self._event_row(event))
        else:
            empty = QLabel("مناسبت ثبت‌شده‌ای برای این روز وجود ندارد.")
            empty.setObjectName("muted")
            empty.setStyleSheet("font-size: 9pt;")
            self.events_layout.addWidget(empty)
        self.events_layout.addStretch(1)

        if not self.service.has_coverage(selected.year):
            self.note_label.setText(
                "اطلاعات تعطیلات برای این سال در نسخهٔ فعلی موجود نیست."
            )
            self.note_label.setVisible(True)
        elif self.service.load_error:
            self.note_label.setText(self.service.load_error)
            self.note_label.setVisible(True)
        else:
            self.note_label.setVisible(False)

    def _event_row(self, event: CalendarEvent) -> QWidget:
        row = QWidget()
        row.setObjectName("transparentRoot")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        dot = QLabel("•")
        dot.setStyleSheet(
            f"color: {DANGER if event.official else self._accent}; font-size: 13pt;"
        )
        dot.setFixedWidth(10)
        dot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        head.addWidget(dot)
        title = QLabel(event.title)
        title.setObjectName("eventTitle")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        badge = Chip(loc.category_label(event.category), MUTED)
        badge.setStyleSheet(
            badge.styleSheet() + "font-size: 7.5pt; padding: 1px 6px;"
        )
        head.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)

        if event.description:
            description = QLabel(event.description)
            description.setObjectName("eventDescription")
            description.setWordWrap(True)
            description.setContentsMargins(16, 0, 0, 0)
            layout.addWidget(description)
        row.setToolTip(event.description or event.title)
        return row

    # ------------------------------------------------------------------ theme
    def set_accent(self, accent: str) -> None:
        self._accent = accent
        for cell in self._cells:
            cell.accent = accent
            cell.update()
        self._refresh_details()

    # ----------------------------------------------------------------- window
    def show_calendar(self, anchor: QWidget | None = None) -> None:
        self.update_today()
        if self._embedded:
            self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            return
        self.adjust_to_screen(anchor)
        self.show_near(anchor)
        self.show_with_fade()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def adjust_to_screen(self, anchor: QWidget | None = None) -> None:
        if self._embedded:
            return
        screen = anchor.screen() if anchor is not None and anchor.isVisible() else None
        if screen is None:
            screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        height = min(NATURAL_HEIGHT, max(440, available.height() - 16))
        self.setFixedSize(NATURAL_WIDTH, height)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Closing the calendar must never terminate the application.
        event.ignore()
        self.hide()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if self._embedded:
                self.closeRequested.emit()
            else:
                self.hide()
        elif key == Qt.Key.Key_PageUp:
            self.go_previous()
        elif key == Qt.Key.Key_PageDown:
            self.go_next()
        elif key == Qt.Key.Key_Home:
            self.go_today()
        else:
            super().keyPressEvent(event)
