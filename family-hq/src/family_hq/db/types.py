from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetimes in, timezone-aware UTC datetimes out.

    SQLite has no real timestamp type and drops tzinfo; this type guarantees that what goes in
    is converted to UTC and that what comes out is always aware. Naive values are rejected
    rather than guessed at.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime passed to the database layer; use aware datetimes")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        aware: datetime = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC)
