"""The only place permission rules live (see docs/permissions.md).

Methods named `can_*` return bool; methods named `require_*` raise PermissionDeniedError.
Error messages never include task or project content.
"""

from __future__ import annotations

from family_hq.domain import visibility
from family_hq.domain.enums import Scope
from family_hq.domain.people import Permission, Person
from family_hq.domain.projects import Project
from family_hq.domain.tasks import Task
from family_hq.errors import PermissionDeniedError


def _deny(message: str) -> PermissionDeniedError:
    return PermissionDeniedError(message)


class Authorizer:
    # ---- visibility -----------------------------------------------------------------------

    def can_view_task(self, person: Person, task: Task) -> bool:
        return visibility.can_view(person, task.visibility_scope, task.owner_id)

    def can_view_project(self, person: Person, project: Project) -> bool:
        return visibility.can_view(person, project.visibility_scope, project.owner_id)

    # ---- generic ----------------------------------------------------------------------------

    def require_active(self, person: Person) -> None:
        if not person.active:
            raise _deny("This person is inactive")

    def require(self, person: Person, permission: Permission, what: str) -> None:
        if not person.has(permission):
            raise _deny(f"You don't have permission to {what}")

    # ---- tasks ------------------------------------------------------------------------------

    @staticmethod
    def _is_involved(person: Person, task: Task) -> bool:
        return person.id in (task.owner_id, task.creator_id)

    @staticmethod
    def _owns_private(person: Person, task: Task) -> bool:
        return task.owner_id == person.id

    def can_edit_task(self, person: Person, task: Task) -> bool:
        if task.visibility_scope is not Scope.FAMILY:
            return self._owns_private(person, task)
        return self._is_involved(person, task) or person.has(Permission.EDIT_ANY_FAMILY_TASK)

    def can_work_on_task(self, person: Person, task: Task) -> bool:
        """Start, complete, wait, block, unblock, snooze."""
        if task.visibility_scope is not Scope.FAMILY:
            return self._owns_private(person, task)
        return (
            task.owner_id is None
            or task.owner_id == person.id
            or person.has(Permission.EDIT_ANY_FAMILY_TASK)
        )

    def require_create_task(self, person: Person, scope: Scope, owner_id: str | None) -> None:
        if not person.can_use_scope(scope):
            raise _deny(f"You can't create {scope.value} tasks")
        if scope is not Scope.FAMILY and owner_id != person.id:
            raise _deny(f"{scope.value} tasks can only belong to you")
        if (
            scope is Scope.FAMILY
            and owner_id not in (None, person.id)
            and not person.has(Permission.ASSIGN_OTHERS)
        ):
            raise _deny("You can't assign tasks to other people")

    def require_edit_task(self, person: Person, task: Task) -> None:
        if not self.can_edit_task(person, task):
            raise _deny("You don't have permission to edit this task")

    def require_work_on_task(self, person: Person, task: Task) -> None:
        if not self.can_work_on_task(person, task):
            raise _deny("This task belongs to someone else")

    def require_assign(self, person: Person, task: Task, new_owner_id: str | None) -> None:
        if task.visibility_scope is not Scope.FAMILY:
            raise _deny(f"{task.visibility_scope.value} tasks can't be assigned to anyone else")
        claiming_free_task = new_owner_id == person.id and task.owner_id is None
        releasing_own_task = new_owner_id is None and task.owner_id == person.id
        if claiming_free_task or releasing_own_task:
            return
        if person.has(Permission.ASSIGN_OTHERS):
            return
        if new_owner_id is None and person.has(Permission.EDIT_ANY_FAMILY_TASK):
            return
        raise _deny("You can't assign tasks to other people")

    def require_change_scope(self, person: Person, task: Task, new_scope: Scope) -> None:
        if not person.can_use_scope(new_scope):
            raise _deny(f"You can't use the {new_scope.value} scope")
        if task.visibility_scope is not Scope.FAMILY:
            if not self._owns_private(person, task):
                raise _deny("You don't have permission to change this task")
            return
        # FAMILY -> private scope: must be allowed to edit, and be (or become) the owner.
        self.require_edit_task(person, task)
        if new_scope is not Scope.FAMILY and task.owner_id not in (None, person.id):
            raise _deny("A task owned by someone else can't be made private by you")

    # ---- projects ---------------------------------------------------------------------------

    def require_create_project(self, person: Person, scope: Scope, owner_id: str | None) -> None:
        if scope is Scope.FAMILY:
            self.require(person, Permission.MANAGE_PROJECTS, "create family projects")
            return
        if not person.can_use_scope(scope):
            raise _deny(f"You can't create {scope.value} projects")
        if owner_id != person.id:
            raise _deny(f"{scope.value} projects can only belong to you")

    def require_edit_project(self, person: Person, project: Project) -> None:
        if project.visibility_scope is Scope.FAMILY:
            self.require(person, Permission.MANAGE_PROJECTS, "edit family projects")
        elif project.owner_id != person.id:
            raise _deny("You don't have permission to edit this project")
