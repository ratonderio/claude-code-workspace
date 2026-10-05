from __future__ import annotations

from enum import StrEnum
from typing import Self

from family_hq.errors import ValidationError


class _ParsableEnum(StrEnum):
    @classmethod
    def parse(cls, value: str | Self) -> Self:
        """Case-insensitive, accepts '-' and ' ' for '_' (friendly for CLI/Discord input)."""
        if isinstance(value, cls):
            return value
        key = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return cls(key)
        except ValueError:
            allowed = ", ".join(m.value for m in cls)
            raise ValidationError(
                f"Unknown {cls.__name__.lower()} '{value}'. Allowed: {allowed}"
            ) from None


class Role(_ParsableEnum):
    ADMIN = "ADMIN"
    ADULT = "ADULT"
    MEMBER = "MEMBER"


class Scope(_ParsableEnum):
    """Visibility scope. Declaration order is the restrictiveness rank (see domain.visibility)."""

    FAMILY = "FAMILY"
    PERSONAL = "PERSONAL"
    PRIVATE_WORK = "PRIVATE_WORK"


class Sink(_ParsableEnum):
    """An integration or surface that content may be sent to."""

    DISCORD_CHANNEL = "DISCORD_CHANNEL"  # broadcast to a shared channel
    DISCORD_EPHEMERAL = "DISCORD_EPHEMERAL"  # reply visible only to the invoker
    GOOGLE_FAMILY = "GOOGLE_FAMILY"  # shared family sheet/calendar
    GOOGLE_PRIVATE = "GOOGLE_PRIVATE"  # the owner's own Google account
    OBSIDIAN = "OBSIDIAN"
    AI = "AI"


class TaskStatus(_ParsableEnum):
    INBOX = "INBOX"
    OPEN = "OPEN"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class Priority(_ParsableEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Effort(_ParsableEnum):
    """Workload estimate bucket (not timekeeping). Points are configurable, see domain.workload."""

    XS = "XS"  # under 5 minutes
    S = "S"  # 5-15 minutes
    M = "M"  # 15-60 minutes
    L = "L"  # 1-3 hours
    XL = "XL"  # multi-session / project work


class ProjectStatus(_ParsableEnum):
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    DONE = "DONE"
    ARCHIVED = "ARCHIVED"


class Source(_ParsableEnum):
    CLI = "CLI"
    DISCORD = "DISCORD"
    OBSIDIAN = "OBSIDIAN"
    RECURRENCE = "RECURRENCE"
    AI = "AI"
    SYSTEM = "SYSTEM"


class EventType(_ParsableEnum):
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_UNASSIGNED = "TASK_UNASSIGNED"
    TASK_CLAIMED = "TASK_CLAIMED"
    TASK_STARTED = "TASK_STARTED"
    TASK_WAITING = "TASK_WAITING"
    TASK_BLOCKED = "TASK_BLOCKED"
    TASK_UNBLOCKED = "TASK_UNBLOCKED"
    TASK_SNOOZED = "TASK_SNOOZED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_CANCELLED = "TASK_CANCELLED"
    TASK_REOPENED = "TASK_REOPENED"
    TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED"
    TASK_NOTE_ADDED = "TASK_NOTE_ADDED"
    DEADLINE_CHANGED = "DEADLINE_CHANGED"
    SCOPE_CHANGED = "SCOPE_CHANGED"
    RECURRENCE_GENERATED = "RECURRENCE_GENERATED"  # reserved for Phase 3
    PROJECT_CREATED = "PROJECT_CREATED"
    PROJECT_UPDATED = "PROJECT_UPDATED"
