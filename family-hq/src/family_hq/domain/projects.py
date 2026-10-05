from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from family_hq.domain.enums import ProjectStatus, Scope


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    status: ProjectStatus
    visibility_scope: Scope
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    owner_id: str | None = None
    due_at: datetime | None = None
    due_all_day: bool = False
