"""SQLAlchemy models. Persistence shapes only: no business rules live here (see domain/).

Enum-like columns are plain strings by design (decision D17).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from family_hq.db.types import UTCDateTime


class Base(DeclarativeBase):
    pass


class PersonRow(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    discord_user_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(16))
    google_email: Mapped[str | None] = mapped_column(String(255))
    permissions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CategoryRow(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    visibility_scope: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    due_all_day: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_projects_scope_owner", "visibility_scope", "owner_id"),)


class RecurrenceDefinitionRow(Base):
    """Schema reserved for Phase 3 (no service yet). See docs/data-model.md."""

    __tablename__ = "recurrence_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    visibility_scope: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(16))
    effort: Mapped[str | None] = mapped_column(String(8))
    rrule: Mapped[str] = mapped_column(Text)
    dtstart: Mapped[str] = mapped_column(String(32))  # local wall time, ISO format
    timezone: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    generated_through: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    creator_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    visibility_scope: Mapped[str] = mapped_column(String(16))
    priority: Mapped[str] = mapped_column(String(16))
    effort: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    due_all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_by_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    snoozed_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    postpone_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    recurrence_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey("recurrence_definitions.id")
    )
    occurrence_key: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        # Database-level guarantee behind idempotent recurrence generation (Phase 3).
        UniqueConstraint(
            "recurrence_definition_id", "occurrence_key", name="uq_tasks_recurrence_occurrence"
        ),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_owner_status", "owner_id", "status"),
        Index("ix_tasks_due_at", "due_at"),
        Index("ix_tasks_scope", "visibility_scope"),
        Index("ix_tasks_project", "project_id"),
        Index("ix_tasks_completed_at", "completed_at"),
    )


class ActivityEventRow(Base):
    __tablename__ = "activity_events"

    # Integer PK gives a monotonic cursor for integrations ("changes since seq N").
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime())
    event_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("people.id"))
    source: Mapped[str] = mapped_column(String(16))
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    visibility_scope: Mapped[str] = mapped_column(String(16))
    scope_owner_id: Mapped[str | None] = mapped_column(String(36))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_events_task_seq", "task_id", "seq"),
        Index("ix_events_project_seq", "project_id", "seq"),
        Index("ix_events_occurred_at", "occurred_at"),
        {"sqlite_autoincrement": True},
    )


class ExternalRefRow(Base):
    __tablename__ = "external_refs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(36))
    system: Mapped[str] = mapped_column(String(32))
    ref_key: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime())

    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "system",
            "ref_key",
            name="uq_external_refs_entity_system_key",
        ),
        Index("ix_external_refs_lookup", "system", "external_id"),
    )
