from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from family_hq.application.actor import Actor, reload_actor
from family_hq.application.authz import Authorizer
from family_hq.application.ledger import iso, record
from family_hq.application.patch import UNSET, Unset
from family_hq.clock import Clock
from family_hq.domain.enums import EventType, ProjectStatus, Scope
from family_hq.domain.events import ActivityEvent
from family_hq.domain.ids import looks_like_id_prefix, new_id
from family_hq.domain.projects import Project
from family_hq.domain.tasks import Due
from family_hq.errors import ConflictError, NotFoundError, ValidationError
from family_hq.repositories.base import UnitOfWork

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewProject:
    name: str
    description: str | None = None
    scope: Scope = Scope.FAMILY
    due: Due | None = None


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 200:
        raise ValidationError("A project name must be 1 to 200 characters")
    return cleaned


class ProjectService:
    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], clock: Clock, authorizer: Authorizer
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._authz = authorizer

    # ---- reads ----------------------------------------------------------------------------

    def find(self, actor: Actor, ref: str) -> Project:
        """Resolve by id, unique id prefix, or name; only among projects the actor can see."""
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            return self._resolve(uow, actor, ref)

    def list_projects(self, actor: Actor, *, include_closed: bool = False) -> list[Project]:
        statuses = (
            None if include_closed else frozenset({ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD})
        )
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            return uow.projects.list_visible(actor.person, statuses=statuses)

    def history(self, actor: Actor, ref: str, *, limit: int | None = None) -> list[ActivityEvent]:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            project = self._resolve(uow, actor, ref)
            return uow.events.list_visible(actor.person, project_id=project.id, limit=limit)

    def _resolve(self, uow: UnitOfWork, actor: Actor, ref: str) -> Project:
        ref = ref.strip()
        viewer = actor.person
        if len(ref) == 36:
            project = uow.projects.get_visible(ref, viewer)
            if project is not None:
                return project
        by_name = uow.projects.find_visible_by_name(ref, viewer)
        if len(by_name) == 1:
            return by_name[0]
        if len(by_name) > 1:
            raise ValidationError("Several projects have that name; use the project id instead")
        if len(ref) >= 4 and looks_like_id_prefix(ref):
            matches = [p for p in uow.projects.list_visible(viewer) if p.id.startswith(ref.lower())]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise ValidationError("That id prefix matches several projects")
        raise NotFoundError("No such project")

    # ---- writes ---------------------------------------------------------------------------

    def create(self, actor: Actor, new: NewProject) -> Project:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            owner_id = None if new.scope is Scope.FAMILY else actor.id
            self._authz.require_create_project(actor.person, new.scope, owner_id)
            name = _clean_name(new.name)
            if uow.projects.find_visible_by_name(name, actor.person):
                raise ConflictError("A project with that name already exists")
            now = self._clock.now()
            project = Project(
                id=new_id(),
                name=name,
                description=(new.description or "").strip() or None,
                status=ProjectStatus.ACTIVE,
                visibility_scope=new.scope,
                created_at=now,
                updated_at=now,
                owner_id=owner_id,
                due_at=new.due.at if new.due else None,
                due_all_day=new.due.all_day if new.due else False,
            )
            uow.projects.add(project)
            record(
                uow,
                self._clock,
                actor,
                EventType.PROJECT_CREATED,
                project=project,
                data={"name": project.name, "scope": project.visibility_scope.value},
            )
            uow.commit()
        log.info("project_created", extra={"project_id": project.id, "actor_id": actor.id})
        return project

    def update(
        self,
        actor: Actor,
        ref: str,
        *,
        name: str | Unset = UNSET,
        description: str | Unset | None = UNSET,
        status: ProjectStatus | Unset = UNSET,
        due: Due | Unset | None = UNSET,
    ) -> Project:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            project = self._resolve(uow, actor, ref)
            self._authz.require_edit_project(actor.person, project)
            changed = project
            changes: dict[str, Any] = {}
            if not isinstance(name, Unset):
                clean = _clean_name(name)
                if clean != project.name:
                    clash = [
                        p
                        for p in uow.projects.find_visible_by_name(clean, actor.person)
                        if p.id != project.id
                    ]
                    if clash:
                        raise ConflictError("A project with that name already exists")
                    changes["name"] = [project.name, clean]
                    changed = replace(changed, name=clean)
            if not isinstance(description, Unset):
                clean_desc = (description or "").strip() or None
                if clean_desc != project.description:
                    changes["description_changed"] = True
                    changed = replace(changed, description=clean_desc)
            if not isinstance(status, Unset) and status is not project.status:
                changes["status"] = [project.status.value, status.value]
                changed = replace(changed, status=status)
            if not isinstance(due, Unset):
                new_at = due.at if due else None
                new_all_day = due.all_day if due else False
                if new_at != project.due_at or new_all_day != project.due_all_day:
                    changes["due_at"] = [iso(project.due_at), iso(new_at)]
                    changed = replace(changed, due_at=new_at, due_all_day=new_all_day)
            if not changes:
                return project
            changed = replace(changed, updated_at=self._clock.now())
            uow.projects.update(changed)
            record(
                uow, self._clock, actor, EventType.PROJECT_UPDATED, project=changed,
                data={"changes": changes},
            )  # fmt: skip
            uow.commit()
        log.info("project_updated", extra={"project_id": project.id, "actor_id": actor.id})
        return changed
