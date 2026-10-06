"""Row <-> domain conversion. The only place that knows both shapes."""

from __future__ import annotations

from typing import Any

from family_hq.db.models import (
    ActivityEventRow,
    CategoryRow,
    ExternalRefRow,
    PersonRow,
    ProjectRow,
    TaskRow,
)
from family_hq.domain.enums import (
    Effort,
    EventType,
    Priority,
    ProjectStatus,
    Role,
    Scope,
    Source,
    TaskStatus,
)
from family_hq.domain.events import ActivityEvent
from family_hq.domain.external_refs import ExternalRef
from family_hq.domain.people import Category, Person
from family_hq.domain.projects import Project
from family_hq.domain.tasks import Task


def person_from_row(r: PersonRow) -> Person:
    return Person(
        id=r.id,
        display_name=r.display_name,
        role=Role(r.role),
        active=r.active,
        created_at=r.created_at,
        updated_at=r.updated_at,
        discord_user_id=r.discord_user_id,
        google_email=r.google_email,
        permissions=dict(r.permissions or {}),
    )


def person_to_row(p: Person) -> PersonRow:
    return PersonRow(
        id=p.id,
        display_name=p.display_name,
        discord_user_id=p.discord_user_id,
        active=p.active,
        role=p.role.value,
        google_email=p.google_email,
        permissions=dict(p.permissions),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def category_from_row(r: CategoryRow) -> Category:
    return Category(
        id=r.id, name=r.name, sort_order=r.sort_order, active=r.active, created_at=r.created_at
    )


def project_from_row(r: ProjectRow) -> Project:
    return Project(
        id=r.id,
        name=r.name,
        status=ProjectStatus(r.status),
        visibility_scope=Scope(r.visibility_scope),
        created_at=r.created_at,
        updated_at=r.updated_at,
        description=r.description,
        owner_id=r.owner_id,
        due_at=r.due_at,
        due_all_day=r.due_all_day,
    )


def project_values(p: Project) -> dict[str, Any]:
    return {
        "name": p.name,
        "description": p.description,
        "status": p.status.value,
        "visibility_scope": p.visibility_scope.value,
        "owner_id": p.owner_id,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "due_at": p.due_at,
        "due_all_day": p.due_all_day,
    }


def task_from_row(r: TaskRow) -> Task:
    return Task(
        id=r.id,
        title=r.title,
        description=r.description,
        status=TaskStatus(r.status),
        owner_id=r.owner_id,
        creator_id=r.creator_id,
        project_id=r.project_id,
        category_id=r.category_id,
        visibility_scope=Scope(r.visibility_scope),
        priority=Priority(r.priority),
        effort=Effort(r.effort) if r.effort else None,
        created_at=r.created_at,
        updated_at=r.updated_at,
        due_at=r.due_at,
        due_all_day=r.due_all_day,
        completed_at=r.completed_at,
        completed_by_id=r.completed_by_id,
        cancelled_at=r.cancelled_at,
        snoozed_until=r.snoozed_until,
        postpone_count=r.postpone_count,
        blocked_reason=r.blocked_reason,
        source=Source(r.source),
        parent_task_id=r.parent_task_id,
        recurrence_definition_id=r.recurrence_definition_id,
        occurrence_key=r.occurrence_key,
        version=r.version,
    )


def task_values(t: Task) -> dict[str, Any]:
    """All mutable columns (everything except id and version)."""
    return {
        "title": t.title,
        "description": t.description,
        "status": t.status.value,
        "owner_id": t.owner_id,
        "creator_id": t.creator_id,
        "project_id": t.project_id,
        "category_id": t.category_id,
        "visibility_scope": t.visibility_scope.value,
        "priority": t.priority.value,
        "effort": t.effort.value if t.effort else None,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "due_at": t.due_at,
        "due_all_day": t.due_all_day,
        "completed_at": t.completed_at,
        "completed_by_id": t.completed_by_id,
        "cancelled_at": t.cancelled_at,
        "snoozed_until": t.snoozed_until,
        "postpone_count": t.postpone_count,
        "blocked_reason": t.blocked_reason,
        "source": t.source.value,
        "parent_task_id": t.parent_task_id,
        "recurrence_definition_id": t.recurrence_definition_id,
        "occurrence_key": t.occurrence_key,
    }


def event_from_row(r: ActivityEventRow) -> ActivityEvent:
    return ActivityEvent(
        id=r.id,
        seq=r.seq,
        occurred_at=r.occurred_at,
        event_type=EventType(r.event_type),
        source=Source(r.source),
        visibility_scope=Scope(r.visibility_scope),
        actor_id=r.actor_id,
        task_id=r.task_id,
        project_id=r.project_id,
        scope_owner_id=r.scope_owner_id,
        data=dict(r.data or {}),
    )


def external_ref_from_row(r: ExternalRefRow) -> ExternalRef:
    return ExternalRef(
        id=r.id,
        entity_type=r.entity_type,
        entity_id=r.entity_id,
        system=r.system,
        ref_key=r.ref_key,
        external_id=r.external_id,
        synced_at=r.synced_at,
        content_hash=r.content_hash,
        payload=dict(r.payload or {}),
    )
