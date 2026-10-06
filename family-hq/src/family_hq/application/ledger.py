"""Appending to the activity ledger. Every service records events through this one function."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from family_hq.application.actor import Actor
from family_hq.clock import Clock
from family_hq.domain.enums import EventType, Scope
from family_hq.domain.events import ActivityEvent
from family_hq.domain.ids import new_id
from family_hq.domain.projects import Project
from family_hq.domain.tasks import Task
from family_hq.repositories.base import UnitOfWork


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def record(
    uow: UnitOfWork,
    clock: Clock,
    actor: Actor,
    event_type: EventType,
    *,
    task: Task | None = None,
    project: Project | None = None,
    data: dict[str, Any] | None = None,
    scope: Scope | None = None,
    scope_owner_id: str | None = None,
) -> ActivityEvent:
    """Append one event. The scope snapshot comes from the subject unless explicitly overridden
    (scope changes pass the stricter of old and new scope, decision D6)."""
    subject = task or project
    if subject is None:
        raise ValueError("an event needs a task or a project")
    snapshot_scope = scope if scope is not None else subject.visibility_scope
    if snapshot_scope is Scope.FAMILY:
        owner = None
    else:
        owner = scope_owner_id if scope_owner_id is not None else subject.owner_id
    event = ActivityEvent(
        id=new_id(),
        occurred_at=clock.now(),
        event_type=event_type,
        source=actor.source,
        visibility_scope=snapshot_scope,
        actor_id=actor.id,
        task_id=task.id if task else None,
        project_id=project.id if project else None,
        scope_owner_id=owner,
        data=data or {},
    )
    return uow.events.add(event)
