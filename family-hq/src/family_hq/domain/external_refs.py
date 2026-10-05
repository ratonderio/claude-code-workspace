from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExternalRef:
    """Link from one of our entities to an object in an external system (decision D9)."""

    id: str
    entity_type: str  # "task" | "project" | "person"
    entity_id: str
    system: str  # "discord" | "google_calendar" | "google_sheets" | ...
    ref_key: str  # distinguishes several refs per system, e.g. "card", "deadline"
    external_id: str
    synced_at: datetime
    content_hash: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
