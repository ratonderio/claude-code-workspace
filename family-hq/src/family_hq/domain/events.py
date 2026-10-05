from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from family_hq.domain.enums import EventType, Scope, Source


@dataclass(frozen=True)
class ActivityEvent:
    """One row of the append-oriented ledger.

    visibility_scope / scope_owner_id are a snapshot taken when the event happened. Viewing an
    event requires passing the check against the snapshot AND the subject's current scope.
    """

    id: str
    occurred_at: datetime
    event_type: EventType
    source: Source
    visibility_scope: Scope
    actor_id: str | None = None
    task_id: str | None = None
    project_id: str | None = None
    scope_owner_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    seq: int | None = None  # assigned by the database on insert
