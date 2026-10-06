"""Date helpers and a tiny, deterministic natural-date parser.

All results are timezone-aware. Storage is UTC; the household zone is applied here, at the
edge. Date-only deadlines are stored as 23:59:59 local time on the due date (decision D10), so
the local date can always be recovered and a DST change cannot shift it to another day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from family_hq.errors import ValidationError

END_OF_DAY = time(23, 59, 59)


def to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return dt.astimezone(tz)


def local_date(dt: datetime, tz: ZoneInfo) -> date:
    return to_local(dt, tz).date()


def _local_to_utc(d: date, t: time, tz: ZoneInfo) -> datetime:
    """Local wall time to UTC. Nonexistent (spring-forward) times roll forward; ambiguous
    (fall-back) times use the first occurrence."""
    naive = datetime.combine(d, t)
    return naive.replace(tzinfo=tz, fold=0).astimezone(UTC)


def start_of_day(d: date, tz: ZoneInfo) -> datetime:
    return _local_to_utc(d, time.min, tz)


def end_of_day(d: date, tz: ZoneInfo) -> datetime:
    return _local_to_utc(d, END_OF_DAY, tz)


def day_bounds(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """[start, end) in UTC of a local calendar day (23, 24 or 25 hours long)."""
    return start_of_day(d, tz), start_of_day(d + timedelta(days=1), tz)


def week_start(d: date) -> date:
    """Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())


_WEEKDAYS = {
    "mon": 0, "monday": 0, "tue": 1, "tues": 1, "tuesday": 1, "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3, "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5, "sun": 6, "sunday": 6,
}  # fmt: skip

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_ISO_DATETIME = re.compile(r"^(\d{4}-\d{2}-\d{2})[t ](\d{1,2}:\d{2})$")  # input is lowercased
_RELATIVE = re.compile(r"^([+-])(\d{1,3})([dw])$")
_TIME_24 = re.compile(r"^(\d{1,2}):(\d{2})$")
_TIME_12 = re.compile(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$")


@dataclass(frozen=True)
class ParsedWhen:
    day: date
    time_of_day: time | None  # None means "date only"

    @property
    def all_day(self) -> bool:
        return self.time_of_day is None

    def deadline(self, tz: ZoneInfo) -> datetime:
        """Instant for use as a due date: date-only means end of that local day."""
        return _local_to_utc(self.day, self.time_of_day or END_OF_DAY, tz)

    def start(self, tz: ZoneInfo) -> datetime:
        """Instant for use as 'from then on': date-only means start of that local day."""
        return _local_to_utc(self.day, self.time_of_day or time.min, tz)


def _parse_time(token: str) -> time | None:
    m = _TIME_24.match(token)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        return time(h, mi) if h < 24 and mi < 60 else None
    m = _TIME_12.match(token)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if not (1 <= h <= 12 and mi < 60):
            return None
        if m.group(3) == "pm" and h != 12:
            h += 12
        if m.group(3) == "am" and h == 12:
            h = 0
        return time(h, mi)
    return None


def parse_when(text: str, now: datetime, tz: ZoneInfo, *, past: bool = False) -> ParsedWhen:
    """Parse: today, tomorrow, fri, friday 5pm, 2026-10-09, 2026-10-09 17:30, +3d, +2w.

    A bare weekday name means the next such day strictly after today ("tue" on a Tuesday is
    next week); with past=True (for "since ..." filters) it means the most recent one, today
    included. Also: yesterday, -3d, -1w. Times are 24h (17:30) or 12h (5pm, 5:30pm). Anything
    else raises ValidationError; this is deliberately not a general natural language parser.
    """
    raw = text.strip().lower()
    if not raw:
        raise ValidationError("Empty date")
    today = local_date(now, tz)

    m = _ISO_DATETIME.match(raw)
    if m:
        iso_time = _parse_time(m.group(2))
        if iso_time is None:
            raise ValidationError(f"Invalid time in '{text}'")
        return ParsedWhen(_parse_iso_date(m.group(1)), iso_time)

    tokens = raw.split()
    if len(tokens) > 2:
        raise ValidationError(f"Could not understand date '{text}'")
    tod: time | None = None
    if len(tokens) == 2:
        tod = _parse_time(tokens[1])
        if tod is None:
            raise ValidationError(f"Could not understand time '{tokens[1]}'")
    head = tokens[0]

    if head == "today":
        day = today
    elif head == "tomorrow":
        day = today + timedelta(days=1)
    elif head == "yesterday":
        day = today - timedelta(days=1)
    elif head in _WEEKDAYS:
        if past:
            day = today - timedelta(days=(today.weekday() - _WEEKDAYS[head]) % 7)
        else:
            day = today + timedelta(days=(_WEEKDAYS[head] - today.weekday()) % 7 or 7)
    elif (rel := _RELATIVE.match(head)) is not None:
        n = int(rel.group(2)) * (7 if rel.group(3) == "w" else 1)
        day = today + timedelta(days=-n if rel.group(1) == "-" else n)
    elif _ISO_DATE.match(head):
        day = _parse_iso_date(head)
    else:
        raise ValidationError(f"Could not understand date '{text}'")
    return ParsedWhen(day, tod)


def _parse_iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValidationError(f"Invalid date '{text}'") from None
