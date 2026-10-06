"""TaskService: every task mutation goes through here (see docs/architecture.md).

Pipeline for each operation: resolve through a viewer-scoped lookup (invisible == missing),
authorize, apply a pure change, write with optimistic concurrency, append events, commit once.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from family_hq.application.actor import Actor, reload_actor
from family_hq.application.authz import Authorizer
from family_hq.application.ledger import iso, record
from family_hq.application.patch import UNSET, Unset
from family_hq.clock import Clock
from family_hq.domain.enums import (
    Effort,
    EventType,
    Priority,
    ProjectStatus,
    Scope,
    TaskStatus,
)
from family_hq.domain.events import ActivityEvent
from family_hq.domain.ids import looks_like_id_prefix, new_id
from family_hq.domain.people import Person
from family_hq.domain.projects import Project
from family_hq.domain.tasks import (
    TITLE_MAX,
    Due,
    Task,
    TaskQuery,
    check_reopen,
    check_transition,
)
from family_hq.domain.visibility import is_at_least_as_restrictive, stricter
from family_hq.errors import ConflictError, NotFoundError, ValidationError
from family_hq.repositories.base import UnitOfWork

log = logging.getLogger(__name__)

DESCRIPTION_MAX = 4000
REASON_MAX = 500
NOTE_MAX = 4000
MIN_PREFIX = 4

EventSpec = tuple[EventType, dict[str, Any]]


@dataclass(frozen=True)
class NewTask:
    title: str
    description: str | None = None
    scope: Scope = Scope.FAMILY
    owner_id: str | None = None  # FAMILY: None = unassigned. Private scopes: always the actor.
    project_id: str | None = None
    category_id: str | None = None
    priority: Priority = Priority.NORMAL
    effort: Effort | None = None
    due: Due | None = None
    parent_task_id: str | None = None
    status: TaskStatus = TaskStatus.OPEN  # OPEN or INBOX


@dataclass(frozen=True)
class TaskPatch:
    """Fields left as UNSET are untouched; None clears (where clearing makes sense)."""

    title: str | Unset = UNSET
    description: str | Unset | None = UNSET
    priority: Priority | Unset = UNSET
    effort: Effort | Unset | None = UNSET
    category_id: str | Unset | None = UNSET
    project_id: str | Unset | None = UNSET
    due: Due | Unset | None = UNSET
    scope: Scope | Unset = UNSET


@dataclass(frozen=True)
class _Change:
    task: Task
    events: list[EventSpec]
    scope_kwargs: dict[str, Any]


def _clean_title(title: str) -> str:
    cleaned = " ".join(title.split())
    if not cleaned:
        raise ValidationError("A task needs a title")
    if len(cleaned) > TITLE_MAX:
        raise ValidationError(f"Title is too long (max {TITLE_MAX} characters)")
    return cleaned


def _clean_optional(text: str | None, limit: int, what: str) -> str | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        raise ValidationError(f"{what} is too long (max {limit} characters)")
    return cleaned


def _require_aware(value: datetime, what: str) -> None:
    if value.tzinfo is None:
        raise ValidationError(f"{what} must include a time zone")


class TaskService:
    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], clock: Clock, authorizer: Authorizer
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._authz = authorizer

    # =========================================================================================
    # Reads
    # =========================================================================================

    def get(self, actor: Actor, ref: str) -> Task:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            return self._load(uow, actor, ref)

    def list_tasks(self, actor: Actor, query: TaskQuery | None = None) -> list[Task]:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            return uow.tasks.list(query or TaskQuery(), actor.person)

    def history(self, actor: Actor, ref: str, *, limit: int | None = None) -> list[ActivityEvent]:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            task = self._load(uow, actor, ref)
            return uow.events.list_visible(actor.person, task_id=task.id, limit=limit)

    def recent_activity(
        self, actor: Actor, *, since: datetime | None = None, limit: int = 50
    ) -> list[ActivityEvent]:
        """Newest-first ledger entries the actor may see (task and project events)."""
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            return uow.events.list_visible(
                actor.person, since=since, limit=limit, newest_first=True
            )

    # =========================================================================================
    # Create
    # =========================================================================================

    def create(self, actor: Actor, new: NewTask) -> Task:
        if new.status not in (TaskStatus.OPEN, TaskStatus.INBOX):
            raise ValidationError("New tasks start as OPEN or INBOX")

        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            person = actor.person
            owner_id = new.owner_id
            if new.scope is not Scope.FAMILY and owner_id is None:
                owner_id = person.id
            self._authz.require_create_task(person, new.scope, owner_id)
            title = _clean_title(new.title)
            description = _clean_optional(new.description, DESCRIPTION_MAX, "Description")
            if owner_id is not None:
                self._require_assignable_person(uow, owner_id)
            if new.project_id is not None:
                self._check_project(uow, person, new.scope, new.project_id)
            if new.category_id is not None:
                self._check_category(uow, new.category_id)
            if new.parent_task_id is not None:
                parent = uow.tasks.get_visible(new.parent_task_id, person)
                if parent is None:
                    raise NotFoundError("No such parent task")
                if not is_at_least_as_restrictive(new.scope, parent.visibility_scope):
                    raise ConflictError("A subtask can't be less private than its parent task")
            if new.due is not None:
                _require_aware(new.due.at, "Due date")

            now = self._clock.now()
            task = Task(
                id=new_id(),
                title=title,
                description=description,
                status=new.status,
                owner_id=owner_id,
                creator_id=person.id,
                project_id=new.project_id,
                category_id=new.category_id,
                visibility_scope=new.scope,
                priority=new.priority,
                effort=new.effort,
                created_at=now,
                updated_at=now,
                due_at=new.due.at if new.due else None,
                due_all_day=new.due.all_day if new.due else False,
                source=actor.source,
                parent_task_id=new.parent_task_id,
            )
            uow.tasks.add(task)
            record(
                uow,
                self._clock,
                actor,
                EventType.TASK_CREATED,
                task=task,
                data={
                    "title": task.title,
                    "status": task.status.value,
                    "scope": task.visibility_scope.value,
                    "owner_id": task.owner_id,
                    "project_id": task.project_id,
                    "category_id": task.category_id,
                    "priority": task.priority.value,
                    "effort": task.effort.value if task.effort else None,
                    "due_at": iso(task.due_at),
                    "parent_task_id": task.parent_task_id,
                },
            )
            uow.commit()
        self._log("task_created", actor, task)
        return task

    # =========================================================================================
    # Edit
    # =========================================================================================

    def update(self, actor: Actor, ref: str, patch: TaskPatch) -> Task:
        person = actor.person
        self._authz.require_active(person)
        with self._uow() as uow:
            task = self._load(uow, actor, ref)
            self._authz.require_edit_task(person, task)
            now = self._clock.now()
            new = task
            changes: dict[str, Any] = {}
            extra_events: list[EventSpec] = []
            scope_kwargs: dict[str, Any] = {}

            if not isinstance(patch.title, Unset):
                title = _clean_title(patch.title)
                if title != task.title:
                    changes["title"] = [task.title, title]
                    new = replace(new, title=title)
            if not isinstance(patch.description, Unset):
                description = _clean_optional(patch.description, DESCRIPTION_MAX, "Description")
                if description != task.description:
                    changes["description_changed"] = True
                    new = replace(new, description=description)
            if not isinstance(patch.priority, Unset) and patch.priority is not task.priority:
                changes["priority"] = [task.priority.value, patch.priority.value]
                new = replace(new, priority=patch.priority)
            if not isinstance(patch.effort, Unset) and patch.effort is not task.effort:
                changes["effort"] = [
                    task.effort.value if task.effort else None,
                    patch.effort.value if patch.effort else None,
                ]
                new = replace(new, effort=patch.effort)
            if not isinstance(patch.category_id, Unset) and patch.category_id != task.category_id:
                if patch.category_id is not None:
                    self._check_category(uow, patch.category_id)
                changes["category_id"] = [task.category_id, patch.category_id]
                new = replace(new, category_id=patch.category_id)

            # Scope first, because project/parent containment depends on the target scope.
            target_scope = task.visibility_scope
            if not isinstance(patch.scope, Unset) and patch.scope is not task.visibility_scope:
                self._authz.require_change_scope(person, task, patch.scope)
                target_scope = patch.scope
                new_owner = task.owner_id
                if target_scope is not Scope.FAMILY and new_owner is None:
                    new_owner = person.id  # making an unassigned task private claims it
                self._check_scope_containment(uow, person, task, target_scope)
                new = replace(new, visibility_scope=target_scope, owner_id=new_owner)
                strict = stricter(task.visibility_scope, target_scope)
                scope_kwargs = {"scope": strict, "scope_owner_id": new_owner or task.owner_id}
                extra_events.append(
                    (
                        EventType.SCOPE_CHANGED,
                        {"from": task.visibility_scope.value, "to": target_scope.value},
                    )
                )
                if new_owner != task.owner_id:
                    extra_events.append(
                        (EventType.TASK_CLAIMED, {"from": None, "to": new_owner, "auto": True})
                    )

            if not isinstance(patch.project_id, Unset) and patch.project_id != task.project_id:
                if patch.project_id is not None:
                    self._check_project(uow, person, target_scope, patch.project_id)
                changes["project_id"] = [task.project_id, patch.project_id]
                new = replace(new, project_id=patch.project_id)

            if not isinstance(patch.due, Unset):
                new_at = patch.due.at if patch.due else None
                new_all_day = patch.due.all_day if patch.due else False
                if patch.due is not None:
                    _require_aware(patch.due.at, "Due date")
                if new_at != task.due_at or new_all_day != task.due_all_day:
                    postponed = (
                        task.due_at is not None and new_at is not None and new_at > task.due_at
                    )
                    new = replace(
                        new,
                        due_at=new_at,
                        due_all_day=new_all_day,
                        postpone_count=task.postpone_count + (1 if postponed else 0),
                    )
                    extra_events.append(
                        (
                            EventType.DEADLINE_CHANGED,
                            {
                                "from": iso(task.due_at),
                                "to": iso(new_at),
                                "all_day": new_all_day,
                                "postponed": postponed,
                            },
                        )
                    )

            events: list[EventSpec] = []
            if changes:
                events.append((EventType.TASK_UPDATED, {"changes": changes}))
            events.extend(extra_events)
            if not events:
                return task
            saved = self._commit_change(uow, actor, task, _Change(new, events, scope_kwargs), now)
        self._log("task_updated", actor, saved)
        return saved

    def add_note(self, actor: Actor, ref: str, text: str) -> ActivityEvent:
        """Append a comment to the task's history. Anyone who can see the task may comment."""
        note = _clean_optional(text, NOTE_MAX, "Note")
        if note is None:
            raise ValidationError("A note can't be empty")
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            task = self._load(uow, actor, ref)
            event = record(
                uow, self._clock, actor, EventType.TASK_NOTE_ADDED, task=task, data={"text": note}
            )
            uow.commit()
        self._log("task_note_added", actor, task)
        return event

    # =========================================================================================
    # Assignment
    # =========================================================================================

    def assign(self, actor: Actor, ref: str, owner_id: str | None) -> Task:
        """Give the task to someone, or (None) release it back to the unassigned pool."""
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            task = self._load(uow, actor, ref)
            self._authz.require_assign(actor.person, task, owner_id)
            self._require_open_for_assignment(task)
            if owner_id is not None:
                self._require_assignable_person(uow, owner_id)
            if owner_id == task.owner_id:
                raise ConflictError(
                    "Task is already unassigned"
                    if owner_id is None
                    else "Task is already assigned to that person"
                )
            if owner_id is None:
                event: EventSpec = (EventType.TASK_UNASSIGNED, {"from": task.owner_id, "to": None})
            else:
                event = (EventType.TASK_ASSIGNED, {"from": task.owner_id, "to": owner_id})
            saved = self._commit_change(
                uow,
                actor,
                task,
                _Change(replace(task, owner_id=owner_id), [event], {}),
                self._clock.now(),
            )
        self._log("task_assigned", actor, saved)
        return saved

    def claim(self, actor: Actor, ref: str) -> Task:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            task = self._load(uow, actor, ref)
            self._require_open_for_assignment(task)
            if task.owner_id is not None:
                raise ConflictError("This task already has an owner")
            self._authz.require_assign(actor.person, task, actor.id)
            event: EventSpec = (EventType.TASK_CLAIMED, {"from": None, "to": actor.id})
            saved = self._commit_change(
                uow,
                actor,
                task,
                _Change(replace(task, owner_id=actor.id), [event], {}),
                self._clock.now(),
            )
        self._log("task_claimed", actor, saved)
        return saved

    # =========================================================================================
    # Lifecycle
    # =========================================================================================

    def start(self, actor: Actor, ref: str) -> Task:
        def apply(task: Task, now: datetime) -> _Change:
            check_transition(task.status, TaskStatus.IN_PROGRESS)
            new, events = self._auto_claim(task, actor)
            new = replace(
                new, status=TaskStatus.IN_PROGRESS, blocked_reason=None, snoozed_until=None
            )
            events.append((EventType.TASK_STARTED, {"from": task.status.value}))
            return _Change(new, events, {})

        return self._work(actor, ref, apply, "task_started")

    def complete(self, actor: Actor, ref: str) -> Task:
        def apply(task: Task, now: datetime) -> _Change:
            check_transition(task.status, TaskStatus.DONE)
            new, events = self._auto_claim(task, actor)
            new = replace(
                new,
                status=TaskStatus.DONE,
                completed_at=now,
                completed_by_id=actor.id,
                blocked_reason=None,
                snoozed_until=None,
            )
            events.append((EventType.TASK_COMPLETED, {"from": task.status.value}))
            return _Change(new, events, {})

        return self._work(actor, ref, apply, "task_completed")

    def wait(self, actor: Actor, ref: str, reason: str | None = None) -> Task:
        """Mark WAITING (on a person, a delivery, a reply...). The reason is optional."""
        clean = _clean_optional(reason, REASON_MAX, "Reason")

        def apply(task: Task, now: datetime) -> _Change:
            if task.status is TaskStatus.WAITING and clean == task.blocked_reason:
                raise ConflictError("Task is already WAITING")
            if task.status is not TaskStatus.WAITING:
                check_transition(task.status, TaskStatus.WAITING)
            new = replace(task, status=TaskStatus.WAITING, blocked_reason=clean)
            return _Change(
                new, [(EventType.TASK_WAITING, {"from": task.status.value, "reason": clean})], {}
            )

        return self._work(actor, ref, apply, "task_waiting")

    def block(self, actor: Actor, ref: str, reason: str) -> Task:
        clean = _clean_optional(reason, REASON_MAX, "Reason")
        if clean is None:
            raise ValidationError("Say what the task is blocked on")

        def apply(task: Task, now: datetime) -> _Change:
            if task.status is TaskStatus.BLOCKED and clean == task.blocked_reason:
                raise ConflictError("Task is already BLOCKED for that reason")
            if task.status is not TaskStatus.BLOCKED:
                check_transition(task.status, TaskStatus.BLOCKED)
            new = replace(task, status=TaskStatus.BLOCKED, blocked_reason=clean)
            return _Change(
                new, [(EventType.TASK_BLOCKED, {"from": task.status.value, "reason": clean})], {}
            )

        return self._work(actor, ref, apply, "task_blocked")

    def unblock(self, actor: Actor, ref: str) -> Task:
        """BLOCKED or WAITING back to OPEN."""

        def apply(task: Task, now: datetime) -> _Change:
            if task.status not in (TaskStatus.BLOCKED, TaskStatus.WAITING):
                raise ConflictError("Task isn't blocked or waiting")
            new = replace(task, status=TaskStatus.OPEN, blocked_reason=None)
            return _Change(new, [(EventType.TASK_UNBLOCKED, {"from": task.status.value})], {})

        return self._work(actor, ref, apply, "task_unblocked")

    def snooze(self, actor: Actor, ref: str, until: datetime) -> Task:
        """Hide from actionable views until `until`. Counts as a postponement."""
        _require_aware(until, "Snooze time")

        def apply(task: Task, now: datetime) -> _Change:
            if not task.is_active:
                raise ConflictError(f"Task is {task.status.value}")
            if until <= now:
                raise ValidationError("Snooze time must be in the future")
            new = replace(task, snoozed_until=until, postpone_count=task.postpone_count + 1)
            event = (
                EventType.TASK_SNOOZED,
                {"until": iso(until), "previous": iso(task.snoozed_until)},
            )
            return _Change(new, [event], {})

        return self._work(actor, ref, apply, "task_snoozed")

    def set_status(self, actor: Actor, ref: str, status: TaskStatus) -> Task:
        """Move between the triage statuses INBOX, OPEN and PLANNED."""
        if status not in (TaskStatus.INBOX, TaskStatus.OPEN, TaskStatus.PLANNED):
            raise ValidationError("Use start/wait/block/complete/cancel for other statuses")

        def apply(task: Task, now: datetime) -> _Change:
            check_transition(task.status, status)
            new = replace(task, status=status, blocked_reason=None)
            event = (EventType.TASK_STATUS_CHANGED, {"from": task.status.value, "to": status.value})
            return _Change(new, [event], {})

        return self._work(actor, ref, apply, "task_status_changed")

    def cancel(self, actor: Actor, ref: str, reason: str | None = None) -> Task:
        clean = _clean_optional(reason, REASON_MAX, "Reason")

        def apply(task: Task, now: datetime) -> _Change:
            check_transition(task.status, TaskStatus.CANCELLED)
            new = replace(
                task,
                status=TaskStatus.CANCELLED,
                cancelled_at=now,
                blocked_reason=None,
                snoozed_until=None,
            )
            return _Change(
                new, [(EventType.TASK_CANCELLED, {"from": task.status.value, "reason": clean})], {}
            )

        return self._work(actor, ref, apply, "task_cancelled", need="edit")

    def reopen(self, actor: Actor, ref: str) -> Task:
        def apply(task: Task, now: datetime) -> _Change:
            check_reopen(task.status)
            new = replace(
                task,
                status=TaskStatus.OPEN,
                completed_at=None,
                completed_by_id=None,
                cancelled_at=None,
            )
            return _Change(new, [(EventType.TASK_REOPENED, {"from": task.status.value})], {})

        return self._work(actor, ref, apply, "task_reopened", need="edit")

    # =========================================================================================
    # Internals
    # =========================================================================================

    def _work(
        self,
        actor: Actor,
        ref: str,
        apply: Callable[[Task, datetime], _Change],
        log_name: str,
        *,
        need: str = "work",
    ) -> Task:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            task = self._load(uow, actor, ref)
            if need == "edit":
                self._authz.require_edit_task(actor.person, task)
            else:
                self._authz.require_work_on_task(actor.person, task)
            now = self._clock.now()
            saved = self._commit_change(uow, actor, task, apply(task, now), now)
        self._log(log_name, actor, saved)
        return saved

    def _commit_change(
        self, uow: UnitOfWork, actor: Actor, before: Task, change: _Change, now: datetime
    ) -> Task:
        saved = uow.tasks.update(replace(change.task, updated_at=now))
        for event_type, data in change.events:
            record(
                uow, self._clock, actor, event_type, task=saved, data=data, **change.scope_kwargs
            )
        uow.commit()
        return saved

    @staticmethod
    def _auto_claim(task: Task, actor: Actor) -> tuple[Task, list[EventSpec]]:
        """Starting or finishing an unassigned family task claims it for the actor (D21)."""
        if task.visibility_scope is Scope.FAMILY and task.owner_id is None:
            return (
                replace(task, owner_id=actor.id),
                [(EventType.TASK_CLAIMED, {"from": None, "to": actor.id, "auto": True})],
            )
        return task, []

    def _load(self, uow: UnitOfWork, actor: Actor, ref: str) -> Task:
        """Resolve a full id or a unique id prefix among tasks the actor may see."""
        ref = ref.strip().lower()
        viewer = actor.person
        if len(ref) == 36:
            task = uow.tasks.get_visible(ref, viewer)
            if task is None:
                raise NotFoundError("No such task")
            return task
        if len(ref) < MIN_PREFIX or not looks_like_id_prefix(ref):
            raise NotFoundError("No such task")
        matches = uow.tasks.find_visible_by_prefix(ref, viewer)
        if not matches:
            raise NotFoundError("No such task")
        if len(matches) > 1:
            raise ValidationError("That id prefix matches several tasks; type more characters")
        return matches[0]

    @staticmethod
    def _require_open_for_assignment(task: Task) -> None:
        if not task.is_active:
            raise ConflictError(f"Task is {task.status.value}; reopen it first")

    @staticmethod
    def _require_assignable_person(uow: UnitOfWork, person_id: str) -> Person:
        person = uow.people.get(person_id)
        if person is None or not person.active:
            raise ValidationError("That person doesn't exist or is inactive")
        return person

    @staticmethod
    def _check_category(uow: UnitOfWork, category_id: str) -> None:
        category = uow.categories.get(category_id)
        if category is None or not category.active:
            raise ValidationError("That category doesn't exist or is inactive")

    @staticmethod
    def _check_project(uow: UnitOfWork, viewer: Person, scope: Scope, project_id: str) -> Project:
        project = uow.projects.get_visible(project_id, viewer)
        if project is None:
            raise NotFoundError("No such project")
        if project.status in (ProjectStatus.DONE, ProjectStatus.ARCHIVED):
            raise ConflictError("That project is closed")
        if not is_at_least_as_restrictive(scope, project.visibility_scope):
            raise ConflictError(
                "A task can't be less private than its project; pick a different project or scope"
            )
        return project

    def _check_scope_containment(
        self, uow: UnitOfWork, viewer: Person, task: Task, target_scope: Scope
    ) -> None:
        """Containment rule (D5) for a scope change: parent, project and subtasks."""
        if task.project_id is not None:
            project = uow.projects.get_visible(task.project_id, viewer)
            if project is not None and not is_at_least_as_restrictive(
                target_scope, project.visibility_scope
            ):
                raise ConflictError("Move the task to a project with matching privacy first")
        if task.parent_task_id is not None:
            parent = uow.tasks.get_visible(task.parent_task_id, viewer)
            if parent is not None and not is_at_least_as_restrictive(
                target_scope, parent.visibility_scope
            ):
                raise ConflictError("A subtask can't be less private than its parent task")
        children = uow.tasks.list(TaskQuery(parent_task_id=task.id, include_closed=True), viewer)
        if any(not is_at_least_as_restrictive(c.visibility_scope, target_scope) for c in children):
            raise ConflictError("Change the privacy of its subtasks first")

    @staticmethod
    def _log(name: str, actor: Actor, task: Task) -> None:
        # IDs only. Titles and descriptions never go to logs (decision D14).
        log.info(
            name, extra={"task_id": task.id, "actor_id": actor.id, "source": actor.source.value}
        )
