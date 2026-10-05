"""SQL form of domain.visibility.can_view. tests/test_visibility.py proves they agree."""

from __future__ import annotations

from sqlalchemy import ColumnElement, false, or_

from family_hq.domain.enums import Scope
from family_hq.domain.people import Person


def visible_clause(scope_col, owner_col, viewer: Person) -> ColumnElement[bool]:  # type: ignore[no-untyped-def]
    if not viewer.active:
        return false()
    return or_(scope_col == Scope.FAMILY.value, owner_col == viewer.id)
