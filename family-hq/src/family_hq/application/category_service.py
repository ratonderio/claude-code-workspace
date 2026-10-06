from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import replace

from family_hq.application.actor import Actor, reload_actor
from family_hq.application.authz import Authorizer
from family_hq.clock import Clock
from family_hq.domain.ids import new_id
from family_hq.domain.people import Category, Permission
from family_hq.errors import ConflictError, NotFoundError, ValidationError
from family_hq.repositories.base import UnitOfWork

log = logging.getLogger(__name__)


def _clean(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 100:
        raise ValidationError("A category name must be 1 to 100 characters")
    return cleaned


class CategoryService:
    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], clock: Clock, authorizer: Authorizer
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._authz = authorizer

    def seed_if_empty(self, names: Iterable[str]) -> int:
        """Insert the initial categories once, only into an empty table (decision D19)."""
        with self._uow() as uow:
            if uow.categories.count() > 0:
                return 0
            created = 0
            for order, raw in enumerate(names):
                name = _clean(raw)
                if uow.categories.get_by_name(name) is not None:
                    continue
                uow.categories.add(
                    Category(
                        id=new_id(),
                        name=name,
                        sort_order=order,
                        active=True,
                        created_at=self._clock.now(),
                    )
                )
                created += 1
            uow.commit()
        return created

    def list_categories(self, *, active_only: bool = True) -> list[Category]:
        with self._uow() as uow:
            return uow.categories.list(active_only=active_only)

    def find(self, text: str) -> Category:
        with self._uow() as uow:
            return self._find(uow, text)

    @staticmethod
    def _find(uow: UnitOfWork, text: str) -> Category:
        category = uow.categories.get_by_name(text) or uow.categories.get(text.strip())
        if category is None:
            raise NotFoundError("No such category")
        return category

    def add(self, actor: Actor, name: str) -> Category:
        with self._uow() as uow:
            self._require_admin(uow, actor)
            clean = _clean(name)
            if uow.categories.get_by_name(clean) is not None:
                raise ConflictError("That category already exists")
            order = max((c.sort_order for c in uow.categories.list()), default=-1) + 1
            category = Category(
                id=new_id(), name=clean, sort_order=order, active=True, created_at=self._clock.now()
            )
            uow.categories.add(category)
            uow.commit()
        log.info("category_added", extra={"category_id": category.id, "actor_id": actor.id})
        return category

    def rename(self, actor: Actor, ref: str, new_name: str) -> Category:
        with self._uow() as uow:
            self._require_admin(uow, actor)
            category = self._find(uow, ref)
            clean = _clean(new_name)
            clash = uow.categories.get_by_name(clean)
            if clash is not None and clash.id != category.id:
                raise ConflictError("That category already exists")
            changed = replace(category, name=clean)
            uow.categories.update(changed)
            uow.commit()
        return changed

    def set_active(self, actor: Actor, ref: str, active: bool) -> Category:
        with self._uow() as uow:
            self._require_admin(uow, actor)
            category = self._find(uow, ref)
            changed = replace(category, active=active)
            uow.categories.update(changed)
            uow.commit()
        return changed

    def _require_admin(self, uow: UnitOfWork, actor: Actor) -> None:
        fresh = reload_actor(uow, actor)
        self._authz.require(fresh.person, Permission.MANAGE_CATEGORIES, "manage categories")
