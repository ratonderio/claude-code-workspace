from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from family_hq.domain.dates import (
    day_bounds,
    end_of_day,
    local_date,
    parse_when,
    start_of_day,
    week_start,
)
from family_hq.errors import ValidationError

NY = ZoneInfo("America/New_York")
# Wednesday 2026-10-07 11:00 New York
NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


def test_end_of_day_is_local_2359_and_roundtrips_to_same_date():
    due = end_of_day(date(2026, 10, 9), NY)
    assert due == datetime(2026, 10, 10, 3, 59, 59, tzinfo=UTC)  # EDT is UTC-4
    assert local_date(due, NY) == date(2026, 10, 9)


@pytest.mark.parametrize("day", [date(2026, 3, 8), date(2026, 11, 1)])  # DST start and end in US
def test_all_day_deadline_keeps_its_date_across_dst_changes(day):
    assert local_date(end_of_day(day, NY), NY) == day


def test_day_bounds_are_23_and_25_hours_on_dst_days():
    start, end = day_bounds(date(2026, 3, 8), NY)
    assert (end - start).total_seconds() == 23 * 3600
    start, end = day_bounds(date(2026, 11, 1), NY)
    assert (end - start).total_seconds() == 25 * 3600


def test_start_of_day_utc_offset_follows_local_rules():
    assert start_of_day(date(2026, 1, 15), NY) == datetime(2026, 1, 15, 5, 0, tzinfo=UTC)
    assert start_of_day(date(2026, 7, 15), NY) == datetime(2026, 7, 15, 4, 0, tzinfo=UTC)


def test_week_start_is_monday():
    assert week_start(date(2026, 10, 7)) == date(2026, 10, 5)
    assert week_start(date(2026, 10, 11)) == date(2026, 10, 5)
    assert week_start(date(2026, 10, 12)) == date(2026, 10, 12)


@pytest.mark.parametrize(
    ("text", "day", "tod"),
    [
        ("today", date(2026, 10, 7), None),
        ("tomorrow", date(2026, 10, 8), None),
        ("fri", date(2026, 10, 9), None),
        ("Friday 5pm", date(2026, 10, 9), time(17, 0)),
        ("wed", date(2026, 10, 14), None),  # a bare weekday is strictly after today
        ("2026-12-25", date(2026, 12, 25), None),
        ("2026-12-25 17:30", date(2026, 12, 25), time(17, 30)),
        ("2026-12-25T07:05", date(2026, 12, 25), time(7, 5)),
        ("+3d", date(2026, 10, 10), None),
        ("+2w", date(2026, 10, 21), None),
        ("today 9:30am", date(2026, 10, 7), time(9, 30)),
        ("today 12am", date(2026, 10, 7), time(0, 0)),
        ("today 12pm", date(2026, 10, 7), time(12, 0)),
    ],
)
def test_parse_when(text, day, tod):
    parsed = parse_when(text, NOW, NY)
    assert (parsed.day, parsed.time_of_day) == (day, tod)
    assert parsed.all_day == (tod is None)


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("wed", date(2026, 10, 7)),  # today is Wednesday: "since wed" starts today
        ("mon", date(2026, 10, 5)),
        ("thu", date(2026, 10, 1)),  # last Thursday
        ("yesterday", date(2026, 10, 6)),
        ("-3d", date(2026, 10, 4)),
        ("-1w", date(2026, 9, 30)),
        ("today", date(2026, 10, 7)),
    ],
)
def test_parse_when_in_past_mode_looks_backwards(text, day):
    assert parse_when(text, NOW, NY, past=True).day == day


@pytest.mark.parametrize(
    "bad", ["", "someday", "2026-13-01", "fri 25:00", "1 2 3", "tomorrow noon"]
)
def test_parse_when_rejects_garbage(bad):
    with pytest.raises(ValidationError):
        parse_when(bad, NOW, NY)


def test_parse_when_uses_local_date_not_utc_date():
    # 02:00 UTC on Oct 8 is still the evening of Oct 7 in New York
    late = datetime(2026, 10, 8, 2, 0, tzinfo=UTC)
    assert parse_when("today", late, NY).day == date(2026, 10, 7)


def test_deadline_vs_start_for_date_only():
    parsed = parse_when("2026-10-09", NOW, NY)
    assert parsed.deadline(NY) == datetime(2026, 10, 10, 3, 59, 59, tzinfo=UTC)
    assert parsed.start(NY) == datetime(2026, 10, 9, 4, 0, tzinfo=UTC)


def test_nonexistent_spring_forward_time_does_not_crash():
    # 02:30 on 2026-03-08 does not exist in New York
    parsed = parse_when("2026-03-08 02:30", NOW, NY)
    result = parsed.deadline(NY)
    assert result.tzinfo is not None
