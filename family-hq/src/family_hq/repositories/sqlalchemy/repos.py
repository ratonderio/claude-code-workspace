"""SQLAlchemy implementations of the repository protocols (SQLite today, Postgres later)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from family_hq.db.models import (
    ActivityEventRow,
    CategoryRow,
    ExternalRefRow,
    PersonRow,
    ProjectRow,
    TaskRow,
)
from family_hq.domain.enums import EventType, Priority, ProjectStatus
from family_hq.domain.events import ActivityEvent
from family_hq.domain.external_refs import ExternalRef
from family_hq.domain.people import Category, Person
from family_hq.domain.projects import Project
from family_hq.domain.tasks import ACTIVE_STATUSES, Task, TaskQuery
from family_hq.errors import ConflictError
from family_hq.repositories.sqlalchemy import mappers as m
from family_hq.repositories.sqlalchemy.visibility import visible_clause


class SqlPersonRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, person: Person) -> None:
        self._s.add(m.person_to_row(person))
        self._s.flush()

    def update(self, person: Person) -> None:
        row = self._s.get(PersonRow, person.id)
        if row is None:
            raise ConflictError("Person no longer exists")
        row.display_name = person.display_name
        row.discord_user_id = person.discord_user_id
        row.active = person.active
        row.role = person.role.value
        row.google_email = person.google_email
        row.permissions = dict(person.permissions)
        row.updated_at = person.updated_at
        self._s.flush()

    def get(self, person_id: str) -> Person | None:
        row = self._s.get(PersonRow, person_id)
        return m.person_from_row(row) if row else None

    def get_by_discord_id(self, discord_user_id: str) -> Person | None:
        row = self._s.scalar(select(PersonRow).where(PersonRow.discord_user_id == discord_user_id))
        return m.person_from_row(row) if row else None

    def get_by_name(self, name: str) -> Person | None:
        row = self._s.scalar(
            select(PersonRow).where(func.lower(PersonRow.display_name) == name.strip().lower())
        )
        return m.person_from_row(row) if row else None

    def list(self, *, active_only: bool = False) -> list[Person]:
        stmt = select(PersonRow).order_by(func.lower(PersonRow.display_name))
        if active_only:
            stmt = stmt.where(PersonRow.active.is_(True))
        return [m.person_from_row(r) for r in self._s.scalars(stmt)]

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(PersonRow)) or 0


class SqlCategoryRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, category: Category) -> None:
        self._s.add(
            CategoryRow(
                id=category.id,
                name=category.name,
                sort_order=category.sort_order,
                active=category.active,
                created_at=category.created_at,
            )
        )
        self._s.flush()

    def update(self, category: Category) -> None:
        row = self._s.get(CategoryRow, category.id)
        if row is None:
            raise ConflictError("Category no longer exists")
        row.name = category.name
        row.sort_order = category.sort_order
        row.active = category.active
        self._s.flush()

    def get(self, category_id: str) -> Category | None:
        row = self._s.get(CategoryRow, category_id)
        return m.category_from_row(row) if row else None

    def get_by_name(self, name: str) -> Category | None:
        row = self._s.scalar(
            select(CategoryRow).where(func.lower(CategoryRow.name) == name.strip().lower())
        )
        return m.category_from_row(row) if row else None

    def list(self, *, active_only: bool = False) -> list[Category]:
        stmt = select(CategoryRow).order_by(CategoryRow.sort_order, func.lower(CategoryRow.name))
        if active_only:
            stmt = stmt.where(CategoryRow.active.is_(True))
        return [m.category_from_row(r) for r in self._s.scalars(stmt)]

    def count(self) -> int:
        return self._s.scalar(select(func.count()).select_from(CategoryRow)) or 0


class SqlProjectRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    @staticmethod
    def _visible(viewer: Person):  # type: ignore[no-untyped-def]
        return visible_clause(ProjectRow.visibility_scope, ProjectRow.owner_id, viewer)

    def add(self, project: Project) -> None:
        self._s.add(ProjectRow(id=project.id, **m.project_values(project)))
        self._s.flush()

    def update(self, project: Project) -> None:
        row = self._s.get(ProjectRow, project.id)
        if row is None:
            raise ConflictError("Project no longer exists")
        for key, value in m.project_values(project).items():
            setattr(row, key, value)
        self._s.flush()

    def get_visible(self, project_id: str, viewer: Person) -> Project | None:
        row = self._s.scalar(
            select(ProjectRow).where(ProjectRow.id == project_id, self._visible(viewer))
        )
        return m.project_from_row(row) if row else None

    def find_visible_by_name(self, name: str, viewer: Person) -> list[Project]:
        stmt = select(ProjectRow).where(
            func.lower(ProjectRow.name) == name.strip().lower(), self._visible(viewer)
        )
        return [m.project_from_row(r) for r in self._s.scalars(stmt)]

    def list_visible(
        self, viewer: Person, *, statuses: frozenset[ProjectStatus] | None = None
    ) -> list[Project]:
        stmt = select(ProjectRow).where(self._visible(viewer)).order_by(func.lower(ProjectRow.name))
        if statuses is not None:
            stmt = stmt.where(ProjectRow.status.in_([s.value for s in statuses]))
        return [m.project_from_row(r) for r in self._s.scalars(stmt)]


_PRIORITY_ORDER = {
    Priority.URGENT.value: 0,
    Priority.HIGH.value: 1,
    Priority.NORMAL.value: 2,
    Priority.LOW.value: 3,
}


class SqlTaskRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    @staticmethod
    def _visible(viewer: Person):  # type: ignore[no-untyped-def]
        return visible_clause(TaskRow.visibility_scope, TaskRow.owner_id, viewer)

    def add(self, task: Task) -> None:
        self._s.add(TaskRow(id=task.id, version=task.version, **m.task_values(task)))
        self._s.flush()

    def update(self, task: Task) -> Task:
        values = m.task_values(task)
        values["version"] = task.version + 1
        result = self._s.execute(
            update(TaskRow)
            .where(TaskRow.id == task.id, TaskRow.version == task.version)
            .values(**values)
        )
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise ConflictError("This task was changed by someone else; please try again")
        self._s.expire_all()  # a Core UPDATE does not refresh ORM objects already in the session
        return replace(task, version=task.version + 1)

    def get_visible(self, task_id: str, viewer: Person) -> Task | None:
        row = self._s.scalar(select(TaskRow).where(TaskRow.id == task_id, self._visible(viewer)))
        return m.task_from_row(row) if row else None

    def find_visible_by_prefix(self, prefix: str, viewer: Person, limit: int = 3) -> list[Task]:
        stmt = (
            select(TaskRow)
            .where(TaskRow.id.startswith(prefix.lower(), autoescape=True), self._visible(viewer))
            .limit(limit)
        )
        return [m.task_from_row(r) for r in self._s.scalars(stmt)]

    def list(self, query: TaskQuery, viewer: Person) -> list[Task]:
        q = query
        conditions = [self._visible(viewer)]

        if q.statuses is not None:
            conditions.append(TaskRow.status.in_([s.value for s in q.statuses]))
        elif not q.include_closed:
            conditions.append(TaskRow.status.in_([s.value for s in ACTIVE_STATUSES]))

        if q.owner_id is not None:
            conditions.append(TaskRow.owner_id == q.owner_id)
        if q.unassigned:
            conditions.append(TaskRow.owner_id.is_(None))
        if q.project_id is not None:
            conditions.append(TaskRow.project_id == q.project_id)
        if q.category_id is not None:
            conditions.append(TaskRow.category_id == q.category_id)
        if q.parent_task_id is not None:
            conditions.append(TaskRow.parent_task_id == q.parent_task_id)
        if q.scopes is not None:
            conditions.append(TaskRow.visibility_scope.in_([s.value for s in q.scopes]))
        if q.priorities is not None:
            conditions.append(TaskRow.priority.in_([p.value for p in q.priorities]))
        if q.due_before is not None:
            conditions.append(and_(TaskRow.due_at.is_not(None), TaskRow.due_at <= q.due_before))
        if q.due_after is not None:
            conditions.append(and_(TaskRow.due_at.is_not(None), TaskRow.due_at >= q.due_after))
        if q.overdue_as_of is not None:
            conditions.append(
                and_(
                    TaskRow.status.in_([s.value for s in ACTIVE_STATUSES]),
                    TaskRow.due_at.is_not(None),
                    TaskRow.due_at < q.overdue_as_of,
                )
            )
        if q.hide_snoozed_as_of is not None:
            conditions.append(
                or_(TaskRow.snoozed_until.is_(None), TaskRow.snoozed_until <= q.hide_snoozed_as_of)
            )
        if q.created_after is not None:
            conditions.append(TaskRow.created_at >= q.created_after)
        if q.completed_after is not None:
            conditions.append(TaskRow.completed_at >= q.completed_after)
        if q.completed_before is not None:
            conditions.append(TaskRow.completed_at < q.completed_before)
        if q.text:
            needle = q.text.strip().lower()
            conditions.append(
                or_(
                    func.lower(TaskRow.title).contains(needle, autoescape=True),
                    func.lower(func.coalesce(TaskRow.description, "")).contains(
                        needle, autoescape=True
                    ),
                )
            )

        stmt = (
            select(TaskRow)
            .where(*conditions)
            .order_by(
                case(_PRIORITY_ORDER, value=TaskRow.priority, else_=9),
                TaskRow.due_at.is_(None),
                TaskRow.due_at,
                TaskRow.created_at,
                TaskRow.id,
            )
        )
        if q.limit is not None:
            stmt = stmt.limit(q.limit)
        return [m.task_from_row(r) for r in self._s.scalars(stmt)]


class SqlEventRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def add(self, event: ActivityEvent) -> ActivityEvent:
        row = ActivityEventRow(
            id=event.id,
            occurred_at=event.occurred_at,
            event_type=event.event_type.value,
            actor_id=event.actor_id,
            source=event.source.value,
            task_id=event.task_id,
            project_id=event.project_id,
            visibility_scope=event.visibility_scope.value,
            scope_owner_id=event.scope_owner_id,
            data=event.data,
        )
        self._s.add(row)
        self._s.flush()
        return replace(event, seq=row.seq)

    def list_visible(
        self,
        viewer: Person,
        *,
        task_id: str | None = None,
        project_id: str | None = None,
        after_seq: int | None = None,
        event_types: frozenset[EventType] | None = None,
        since: datetime | None = None,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[ActivityEvent]:
        # An event is visible only if BOTH its recorded snapshot and the subject's current
        # scope allow the viewer (decision D6). Outer joins keep events that have no task/project.
        stmt = (
            select(ActivityEventRow)
            .outerjoin(TaskRow, ActivityEventRow.task_id == TaskRow.id)
            .outerjoin(ProjectRow, ActivityEventRow.project_id == ProjectRow.id)
            .where(
                visible_clause(
                    ActivityEventRow.visibility_scope, ActivityEventRow.scope_owner_id, viewer
                ),
                or_(
                    ActivityEventRow.task_id.is_(None),
                    visible_clause(TaskRow.visibility_scope, TaskRow.owner_id, viewer),
                ),
                or_(
                    ActivityEventRow.project_id.is_(None),
                    visible_clause(ProjectRow.visibility_scope, ProjectRow.owner_id, viewer),
                ),
            )
        )
        if task_id is not None:
            stmt = stmt.where(ActivityEventRow.task_id == task_id)
        if project_id is not None:
            stmt = stmt.where(ActivityEventRow.project_id == project_id)
        if after_seq is not None:
            stmt = stmt.where(ActivityEventRow.seq > after_seq)
        if event_types is not None:
            stmt = stmt.where(ActivityEventRow.event_type.in_([t.value for t in event_types]))
        if since is not None:
            stmt = stmt.where(ActivityEventRow.occurred_at >= since)
        stmt = stmt.order_by(
            ActivityEventRow.seq.desc() if newest_first else ActivityEventRow.seq.asc()
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return [m.event_from_row(r) for r in self._s.scalars(stmt)]


class SqlExternalRefRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def _find(
        self, entity_type: str, entity_id: str, system: str, ref_key: str
    ) -> ExternalRefRow | None:
        return self._s.scalar(
            select(ExternalRefRow).where(
                ExternalRefRow.entity_type == entity_type,
                ExternalRefRow.entity_id == entity_id,
                ExternalRefRow.system == system,
                ExternalRefRow.ref_key == ref_key,
            )
        )

    def get(
        self, entity_type: str, entity_id: str, system: str, ref_key: str
    ) -> ExternalRef | None:
        row = self._find(entity_type, entity_id, system, ref_key)
        return m.external_ref_from_row(row) if row else None

    def upsert(self, ref: ExternalRef) -> None:
        row = self._find(ref.entity_type, ref.entity_id, ref.system, ref.ref_key)
        if row is None:
            row = ExternalRefRow(
                id=ref.id,
                entity_type=ref.entity_type,
                entity_id=ref.entity_id,
                system=ref.system,
                ref_key=ref.ref_key,
            )
            self._s.add(row)
        row.external_id = ref.external_id
        row.content_hash = ref.content_hash
        row.payload = dict(ref.payload)
        row.synced_at = ref.synced_at
        self._s.flush()

    def list_for_entity(self, entity_type: str, entity_id: str) -> list[ExternalRef]:
        stmt = select(ExternalRefRow).where(
            ExternalRefRow.entity_type == entity_type, ExternalRefRow.entity_id == entity_id
        )
        return [m.external_ref_from_row(r) for r in self._s.scalars(stmt)]
