"""Bundled holiday data and graceful-degradation tests."""

from __future__ import annotations

import json
from pathlib import Path

import jdatetime
import pytest

from app.calendar.holidays import HolidayService
from app.calendar.jalali import today as jalali_today


@pytest.fixture(scope="module")
def service() -> HolidayService:
    return HolidayService()


def test_bundled_data_loads_with_expected_coverage(service: HolidayService) -> None:
    assert service.is_loaded
    assert service.load_error is None
    assert service.coverage is not None
    assert (service.coverage.min_year, service.coverage.max_year) == (1402, 1426)
    assert service.holiday_count >= 600
    assert service.occasion_day_count >= 40
    assert service.occasion_entry_count >= service.occasion_day_count
    assert service.event_count == (
        service.holiday_count + service.occasion_entry_count
    )
    assert service.skipped_entries == 0


def test_known_official_holidays(service: HolidayService) -> None:
    nowruz = service.holidays_on(jdatetime.date(1403, 1, 1))
    assert [event.title for event in nowruz] == ["نوروز"]
    assert nowruz[0].official is True
    assert nowruz[0].kind_label == "تعطیل رسمی"
    assert nowruz[0].source

    # Two official holidays on the same day, including a lunar date that moves
    # between years.
    sizdah = service.holidays_on(jdatetime.date(1403, 1, 13))
    titles = {event.title for event in sizdah}
    assert {"روز طبیعت", "شهادت امام علی (ع)"} <= titles
    assert service.is_holiday(jdatetime.date(1403, 1, 13))
    assert service.is_day_off(jdatetime.date(1403, 1, 13))


def test_lunar_holiday_spot_check_for_another_year(service: HolidayService) -> None:
    events = service.holidays_on(jdatetime.date(1404, 1, 2))
    titles = {event.title for event in events}
    assert "شهادت امام علی (ع)" in titles
    assert "نوروز" in titles


def test_recurring_occasions_are_not_official(service: HolidayService) -> None:
    events = service.occasions_on(jdatetime.date(1405, 2, 25))
    titles = {event.title for event in events}
    assert {"بزرگداشت فردوسی", "روز پاسداشت زبان فارسی"} <= titles
    assert all(not event.official for event in events)
    assert all(event.kind_label == "مناسبت" for event in events)
    assert service.holidays_on(jdatetime.date(1405, 2, 25)) == ()
    assert not service.is_holiday(jdatetime.date(1405, 2, 25))
    # 1405-02-25 is a Friday, so it is still a weekly day off.
    assert service.is_weekly_holiday(jdatetime.date(1405, 2, 25))
    assert service.is_day_off(jdatetime.date(1405, 2, 25))


def test_events_on_combines_official_and_occasion(service: HolidayService) -> None:
    events = service.events_on(jdatetime.date(1405, 2, 25))
    assert len(events) == 2
    assert service.events_on(jdatetime.date(1405, 8, 5)) == ()


def test_coverage_boundaries(service: HolidayService) -> None:
    assert service.has_coverage(1402)
    assert service.has_coverage(1426)
    assert not service.has_coverage(1401)
    assert not service.has_coverage(1427)
    assert service.coverage is not None
    assert service.coverage.contains(1410)
    assert not service.coverage.contains(1500)


def test_today_is_resolvable(service: HolidayService) -> None:
    today = jalali_today()
    # Must not raise even when there is no event for today.
    assert isinstance(service.events_on(today), tuple)
    assert isinstance(service.is_day_off(today), bool)


def _write_payload(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "holidays.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_malformed_entries_are_skipped(tmp_path: Path) -> None:
    path = _write_payload(
        tmp_path,
        {
            "coverage": {"min_year": "1402", "max_year": 1403},
            "holidays": [
                {"date": "1403-01-01", "title": "رویداد رسمی"},
                {"date": "bad-date", "title": "نامعتبر"},
                {"date": "1403-01-02", "title": "   "},
                "not-a-dictionary",
            ],
            "occasions": [
                {"month": 1, "day": 1, "title": "مناسبت"},
                {"month": 13, "day": 1, "title": "ماه نامعتبر"},
                {"month": 1, "day": 32, "title": "روز نامعتبر"},
                {"month": "x", "day": 1, "title": "ماه غیرعددی"},
                {"month": 1, "day": 2, "title": ""},
            ],
        },
    )
    service = HolidayService(path)
    assert service.is_loaded
    assert service.coverage is not None
    assert (service.coverage.min_year, service.coverage.max_year) == (1402, 1403)
    assert service.holiday_count == 1
    assert service.occasion_entry_count == 1
    assert service.skipped_entries == 7
    assert [e.title for e in service.holidays_on(jdatetime.date(1403, 1, 1))] == [
        "رویداد رسمی"
    ]
    assert [e.title for e in service.occasions_on(jdatetime.date(1403, 1, 1))] == [
        "مناسبت"
    ]


def test_invalid_coverage_is_inferred_from_holidays(tmp_path: Path) -> None:
    path = _write_payload(
        tmp_path,
        {
            "coverage": {"min_year": "invalid", "max_year": None},
            "holidays": [
                {"date": "1402-01-01", "title": "الف"},
                {"date": "1404-01-01", "title": "ب"},
            ],
            "occasions": [],
        },
    )
    service = HolidayService(path)
    assert service.is_loaded
    assert service.coverage is not None
    assert (service.coverage.min_year, service.coverage.max_year) == (1402, 1404)


def test_missing_file_is_a_controlled_error(tmp_path: Path) -> None:
    service = HolidayService(tmp_path / "does-not-exist.json")
    assert not service.is_loaded
    assert service.load_error
    assert "یافت نشد" in service.load_error
    assert service.holiday_count == 0
    assert service.events_on(jdatetime.date(1403, 1, 1)) == ()
    assert not service.has_coverage(1403)


def test_invalid_json_is_a_controlled_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    service = HolidayService(path)
    assert not service.is_loaded
    assert service.load_error
    assert service.events_on(jdatetime.date(1403, 1, 1)) == ()


def test_wrong_top_level_structure_is_rejected(tmp_path: Path) -> None:
    path = _write_payload(tmp_path, ["not", "an", "object"])
    service = HolidayService(path)
    assert not service.is_loaded
    assert service.load_error


def test_wrong_list_types_are_rejected(tmp_path: Path) -> None:
    path = _write_payload(
        tmp_path,
        {"coverage": {"min_year": 1402, "max_year": 1403}, "holidays": {}, "occasions": []},
    )
    service = HolidayService(path)
    assert not service.is_loaded
    assert service.load_error
