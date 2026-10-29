"""Monthly calendar UI tests (layout, selection, navigation, details)."""

from __future__ import annotations

import jdatetime
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel

from app.calendar.holidays import HolidayService
from app.calendar.jalali import today as jalali_today
from app.storage.settings import SettingsValues
from app.widgets.month_calendar import MonthCalendar


@pytest.fixture
def service() -> HolidayService:
    return HolidayService()


@pytest.fixture
def calendar(qtbot, service: HolidayService) -> MonthCalendar:
    widget = MonthCalendar(service, SettingsValues())
    qtbot.addWidget(widget)
    return widget


def _chip_texts(calendar: MonthCalendar) -> list[str]:
    result: list[str] = []
    for index in range(calendar.chips_row.count()):
        item = calendar.chips_row.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is not None:
            result.append(widget.text())
    return result


def _event_titles(calendar: MonthCalendar) -> list[str]:
    return [label.text() for label in calendar.findChildren(QLabel, "eventTitle")]


def _cell_for(calendar: MonthCalendar, value: jdatetime.date):
    return next(cell for cell in calendar._cells if cell.date == value)


def test_initial_view_is_today_and_has_42_cells(calendar: MonthCalendar) -> None:
    today = jalali_today()
    assert calendar._view_year == today.year
    assert calendar._view_month == today.month
    assert calendar._selected == today
    assert len(calendar._cells) == 42
    assert len(calendar._cells[0].date.isoformat()) == 10
    assert all(cell.date.weekday() >= 0 for cell in calendar._cells)


def test_fixed_view_has_correct_labels_and_selection(calendar: MonthCalendar) -> None:
    value = jdatetime.date(1403, 1, 1)
    calendar.set_view(1403, 1, value)

    assert calendar.month_label.text() == "فروردین ۱۴۰۳"
    assert calendar.gregorian_label.text() == "مارس – آوریل ۲۰۲۴"
    assert calendar.selected_label.text() == "چهارشنبه ۱ فروردین ۱۴۰۳"
    assert calendar.greg_label.text() == "میلادی: ۲۰ مارس ۲۰۲۴"
    assert len(calendar._cells) == 42
    assert calendar._cells[0].date == jdatetime.date(1402, 12, 26)
    assert calendar._cells[0].date.weekday() == 0
    assert not calendar._cells[0].in_month
    assert calendar._cells[4].date == value
    assert calendar._cells[4].in_month
    assert calendar._cells[4].is_selected
    assert calendar._cells[4].official_holiday
    assert sum(cell.in_month for cell in calendar._cells) == 31


def test_only_the_selected_day_is_marked_selected(calendar: MonthCalendar) -> None:
    calendar.set_view(1405, 8, jdatetime.date(1405, 8, 5))
    selected = [cell for cell in calendar._cells if cell.is_selected]
    assert len(selected) == 1
    assert selected[0].date == jdatetime.date(1405, 8, 5)
    # 1405-08-05 is Tuesday, not a holiday.
    assert not selected[0].official_holiday
    assert not selected[0].has_occasion


def test_official_holiday_details(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 1, jdatetime.date(1403, 1, 1))
    assert "نوروز" in _event_titles(calendar)
    assert "تعطیل رسمی" in _chip_texts(calendar)
    assert "امروز" not in _chip_texts(calendar)


def test_multiple_official_holidays_on_one_day(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 1, jdatetime.date(1403, 1, 13))
    titles = _event_titles(calendar)
    assert "روز طبیعت" in titles
    assert "شهادت امام علی (ع)" in titles
    assert "تعطیل رسمی" in _chip_texts(calendar)


def test_occasions_and_friday_are_shown(calendar: MonthCalendar) -> None:
    calendar.set_view(1405, 2, jdatetime.date(1405, 2, 25))
    titles = _event_titles(calendar)
    assert "بزرگداشت فردوسی" in titles
    assert "روز پاسداشت زبان فارسی" in titles
    chips = _chip_texts(calendar)
    assert "مناسبت" in chips
    assert "جمعه" in chips
    assert "تعطیل رسمی" not in chips


def test_no_event_message(calendar: MonthCalendar) -> None:
    calendar.set_view(1405, 8, jdatetime.date(1405, 8, 5))
    assert _event_titles(calendar) == []
    texts: list[str] = []
    for index in range(calendar.events_layout.count()):
        item = calendar.events_layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if isinstance(widget, QLabel):
            texts.append(widget.text())
    assert any("مناسبت ثبت‌شده‌ای" in text for text in texts)


def test_out_of_coverage_note(calendar: MonthCalendar) -> None:
    calendar.set_view(1500, 1, jdatetime.date(1500, 1, 1))
    assert "موجود نیست" in calendar.note_label.text()
    assert not calendar.note_label.isHidden()


def test_month_navigation_across_year(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 12, jdatetime.date(1403, 12, 29))
    calendar.go_next()
    assert (calendar._view_year, calendar._view_month) == (1404, 1)
    assert calendar._selected == jdatetime.date(1404, 1, 29)
    assert calendar.month_label.text() == "فروردین ۱۴۰۴"

    calendar.go_previous()
    assert (calendar._view_year, calendar._view_month) == (1403, 12)
    assert calendar._selected == jdatetime.date(1403, 12, 29)


def test_navigation_clamps_invalid_month_day(calendar: MonthCalendar) -> None:
    calendar.set_view(1404, 1, jdatetime.date(1404, 1, 31))
    calendar.go_previous()
    assert calendar._selected == jdatetime.date(1403, 12, 30)
    assert calendar.month_label.text() == "اسفند ۱۴۰۳"


def test_go_today_returns_to_current_month(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 1, jdatetime.date(1403, 1, 1))
    calendar.go_today()
    today = jalali_today()
    assert calendar._selected == today
    assert (calendar._view_year, calendar._view_month) == (today.year, today.month)


def test_day_click_selects_and_navigates(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 1, jdatetime.date(1403, 1, 1))
    calendar.show()
    QApplication.processEvents()

    target = _cell_for(calendar, jdatetime.date(1403, 1, 5))
    from PySide6.QtTest import QTest

    QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=target.rect().center())
    QApplication.processEvents()
    assert calendar._selected == jdatetime.date(1403, 1, 5)
    assert "۵ فروردین ۱۴۰۳" in calendar.selected_label.text()

    # Clicking a trailing cell navigates to the next month.
    target = _cell_for(calendar, jdatetime.date(1403, 2, 1))
    QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=target.rect().center())
    QApplication.processEvents()
    assert (calendar._view_year, calendar._view_month) == (1403, 2)
    assert calendar._selected == jdatetime.date(1403, 2, 1)
    assert calendar.month_label.text() == "اردیبهشت ۱۴۰۳"


def test_click_handler_can_be_called_directly(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 1, jdatetime.date(1403, 1, 1))
    calendar._on_day_clicked(jdatetime.date(1403, 1, 10))
    assert calendar._selected == jdatetime.date(1403, 1, 10)
    calendar._on_day_clicked(jdatetime.date(1403, 2, 10))
    assert (calendar._view_year, calendar._view_month) == (1403, 2)
    assert calendar._selected == jdatetime.date(1403, 2, 10)


def test_set_accent_updates_cells_and_details(calendar: MonthCalendar) -> None:
    calendar.set_view(1403, 1, jdatetime.date(1403, 1, 1))
    calendar.set_accent("#F5C26B")
    assert QColor(calendar._accent).name() == "#f5c26b"
    assert all(cell.accent == calendar._accent for cell in calendar._cells)
    assert "تعطیل رسمی" in _chip_texts(calendar)


def test_calendar_close_hides_without_quitting(calendar: MonthCalendar) -> None:
    calendar.show()
    QApplication.processEvents()
    assert calendar.isVisible()
    calendar.close()
    QApplication.processEvents()
    assert not calendar.isVisible()
