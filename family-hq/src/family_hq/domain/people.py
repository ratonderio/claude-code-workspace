from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from family_hq.domain.enums import Role, Scope


class Permission(StrEnum):
    EDIT_ANY_FAMILY_TASK = "edit_any_family_task"
    ASSIGN_OTHERS = "assign_others"
    MANAGE_PROJECTS = "manage_projects"
    CREATE_RECURRING = "create_recurring"
    USE_PERSONAL_SCOPE = "use_personal_scope"
    USE_PRIVATE_WORK_SCOPE = "use_private_work_scope"
    MANAGE_PEOPLE = "manage_people"
    MANAGE_CATEGORIES = "manage_categories"
    MANAGE_BACKUPS = "manage_backups"


_ADULT = frozenset(
    {
        Permission.EDIT_ANY_FAMILY_TASK,
        Permission.ASSIGN_OTHERS,
        Permission.MANAGE_PROJECTS,
        Permission.CREATE_RECURRING,
        Permission.USE_PERSONAL_SCOPE,
        Permission.USE_PRIVATE_WORK_SCOPE,
    }
)

ROLE_DEFAULTS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: _ADULT
    | {Permission.MANAGE_PEOPLE, Permission.MANAGE_CATEGORIES, Permission.MANAGE_BACKUPS},
    Role.ADULT: _ADULT,
    Role.MEMBER: frozenset({Permission.USE_PERSONAL_SCOPE}),
}

SCOPE_PERMISSION: dict[Scope, Permission | None] = {
    Scope.FAMILY: None,
    Scope.PERSONAL: Permission.USE_PERSONAL_SCOPE,
    Scope.PRIVATE_WORK: Permission.USE_PRIVATE_WORK_SCOPE,
}


@dataclass(frozen=True)
class Person:
    id: str
    display_name: str
    role: Role
    active: bool
    created_at: datetime
    updated_at: datetime
    discord_user_id: str | None = None
    google_email: str | None = None
    # Per-person overrides of role defaults: {"assign_others": True}
    permissions: dict[str, bool] = field(default_factory=dict)

    def has(self, permission: Permission) -> bool:
        override = self.permissions.get(permission.value)
        if override is not None:
            return override
        return permission in ROLE_DEFAULTS[self.role]

    def can_use_scope(self, scope: Scope) -> bool:
        needed = SCOPE_PERMISSION[scope]
        return needed is None or self.has(needed)


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    sort_order: int
    active: bool
    created_at: datetime
