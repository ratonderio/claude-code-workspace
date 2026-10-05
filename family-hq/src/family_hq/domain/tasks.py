from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from family_hq.domain.dates import local_date
from family_hq.domain.enums import Effort, Priority, Scope, Source, TaskStatus
from family_hq.errors import ConflictError

ACTIVE_STATUSES: frozenset[TaskStatus] = frozenset(
    {
        TaskStatus.INBOX,
        TaskStatus.OPEN,
        TaskStatus.PLANNED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.WAITING,
        TaskStatus.BLOCKED,
    }
)
TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset({TaskStatus.DONE, TaskStatus.CANCELLED})

TITLE_MAX = 200


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    status: TaskStatus
    visibility_scope: Scope
    priority: Priority
    source: Source
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    owner_id: str | None = None
    creator_id: str | None = None
    project_id: str | None = None
    category_id: str | None = None
    effort: Effort | None = None
    due_at: datetime | None = None
    due_all_day: bool = False
    completed_at: datetime | None = None
    completed_by_id: str | None = None
    cancelled_at: datetime | None = None
    snoozed_until: datetime | None = None
    postpone_count: int = 0
    blocked_reason: str | None = None  # the "status reason" for BLOCKED and WAITING
    parent_task_id: str | None = None
    recurrence_definition_id: str | None = None
    occurrence_key: str | None = None
    version: int = 1

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def is_overdue(self, now: datetime) -> bool:
        return self.is_active and self.due_at is not None and now > self.due_at

    def is_snoozed(self, now: datetime) -> bool:
        return self.snoozed_until is not None and self.snoozed_until > now

    def due_date(self, tz: ZoneInfo) -> date | None:
        return None if self.due_at is None else local_date(self.due_at, tz)


@dataclass(frozen=True)
class Due:
    """A deadline as supplied by a user: an instant plus whether only the date was given."""

    at: datetime
    all_day: bool = False


def check_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Lifecycle rules (decision D18).

    Active -> any other active status or DONE/CANCELLED. Terminal statuses leave only through
    reopen (-> OPEN), which is a separate operation.
    """
    if current == target:
        raise ConflictError(f"Task is already {current.value}")
    if current in TERMINAL_STATUSES:
        raise ConflictError(f"Task is {current.value}; reopen it first")


def check_reopen(current: TaskStatus) -> None:
    if current not in TERMINAL_STATUSES:
        raise ConflictError("Only DONE or CANCELLED tasks can be reopened")


@dataclass(frozen=True)
class TaskQuery:
    """Filter specification. Repositories always apply the viewer's visibility on top."""

    statuses: frozenset[TaskStatus] | None = None  # None = active statuses only
    include_closed: bool = False  # when statuses is None, also include DONE/CANCELLED
    owner_id: str | None = None
    unassigned: bool = False
    project_id: str | None = None
    category_id: str | None = None
    parent_task_id: str | None = None
    scopes: frozenset[Scope] | None = None
    priorities: frozenset[Priority] | None = None
    due_before: datetime | None = None  # due_at <= this
    due_after: datetime | None = None  # due_at >= this
    overdue_as_of: datetime | None = None  # active and due_at < this
    hide_snoozed_as_of: datetime | None = None  # exclude snoozed_until > this
    created_after: datetime | None = None
    completed_after: datetime | None = None
    completed_before: datetime | None = None
    text: str | None = None
    limit: int | None = None
