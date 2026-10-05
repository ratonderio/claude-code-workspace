from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace

from family_hq.application.actor import Actor, reload_actor
from family_hq.application.authz import Authorizer
from family_hq.application.patch import UNSET, Unset
from family_hq.clock import Clock
from family_hq.domain.enums import Role, Source
from family_hq.domain.ids import looks_like_id_prefix, new_id
from family_hq.domain.people import Permission, Person
from family_hq.errors import ConflictError, NotFoundError, ValidationError
from family_hq.repositories.base import UnitOfWork

log = logging.getLogger(__name__)


def _clean_name(name: str) -> str:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 100:
        raise ValidationError("A person's name must be 1 to 100 characters")
    return cleaned


class PeopleService:
    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], clock: Clock, authorizer: Authorizer
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._authz = authorizer

    # ---- bootstrap and lookup -------------------------------------------------------------

    def bootstrap_admin(self, name: str, *, discord_user_id: str | None = None) -> Person:
        """Create the first ADMIN. Only possible while there are no people at all."""
        with self._uow() as uow:
            if uow.people.count() > 0:
                raise ConflictError("People already exist; ask an admin to add you")
            now = self._clock.now()
            person = Person(
                id=new_id(),
                display_name=_clean_name(name),
                role=Role.ADMIN,
                active=True,
                created_at=now,
                updated_at=now,
                discord_user_id=discord_user_id,
            )
            uow.people.add(person)
            uow.commit()
        log.info("person_bootstrapped", extra={"person_id": person.id})
        return person

    def has_people(self) -> bool:
        with self._uow() as uow:
            return uow.people.count() > 0

    def get_person(self, person_id: str) -> Person | None:
        with self._uow() as uow:
            return uow.people.get(person_id)

    def find(self, text: str) -> Person:
        """Resolve a display name (case-insensitive) or an id / id prefix."""
        with self._uow() as uow:
            return self._find(uow, text)

    @staticmethod
    def _find(uow: UnitOfWork, text: str) -> Person:
        text = text.strip()
        person = uow.people.get_by_name(text) or uow.people.get(text)
        if person is None and len(text) >= 4 and looks_like_id_prefix(text):
            matches = [p for p in uow.people.list() if p.id.startswith(text.lower())]
            if len(matches) == 1:
                person = matches[0]
            elif len(matches) > 1:
                raise ValidationError("That id prefix matches several people")
        if person is None:
            raise NotFoundError("No such person")
        return person

    def list_people(self, actor: Actor, *, active_only: bool = True) -> list[Person]:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            return uow.people.list(active_only=active_only)

    def actor_for(self, text: str, source: Source) -> Actor:
        person = self.find(text)
        self._authz.require_active(person)
        return Actor(person, source)

    def actor_for_discord(self, discord_user_id: str) -> Actor:
        with self._uow() as uow:
            person = uow.people.get_by_discord_id(str(discord_user_id))
        if person is None or not person.active:
            raise NotFoundError("You're not set up in Family HQ yet. Ask an admin to add you.")
        return Actor(person, Source.DISCORD)

    def sole_admin(self) -> Person | None:
        with self._uow() as uow:
            admins = [p for p in uow.people.list(active_only=True) if p.role is Role.ADMIN]
        return admins[0] if len(admins) == 1 else None

    # ---- administration -------------------------------------------------------------------

    def add(
        self,
        actor: Actor,
        name: str,
        role: Role = Role.MEMBER,
        *,
        discord_user_id: str | None = None,
        google_email: str | None = None,
        permissions: dict[str, bool] | None = None,
    ) -> Person:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            self._authz.require(actor.person, Permission.MANAGE_PEOPLE, "manage people")
            clean = _clean_name(name)
            self._ensure_unique(uow, clean, discord_user_id, exclude_id=None)
            now = self._clock.now()
            person = Person(
                id=new_id(),
                display_name=clean,
                role=role,
                active=True,
                created_at=now,
                updated_at=now,
                discord_user_id=discord_user_id,
                google_email=google_email,
                permissions=self._valid_permissions(permissions or {}),
            )
            uow.people.add(person)
            uow.commit()
        log.info("person_added", extra={"person_id": person.id, "actor_id": actor.id})
        return person

    def update(
        self,
        actor: Actor,
        ref: str,
        *,
        name: str | Unset = UNSET,
        role: Role | Unset = UNSET,
        active: bool | Unset = UNSET,
        discord_user_id: str | Unset | None = UNSET,
        google_email: str | Unset | None = UNSET,
        permissions: dict[str, bool] | Unset = UNSET,
    ) -> Person:
        with self._uow() as uow:
            actor = reload_actor(uow, actor)
            self._authz.require(actor.person, Permission.MANAGE_PEOPLE, "manage people")
            person = self._find(uow, ref)
            changed = replace(person, updated_at=self._clock.now())
            if not isinstance(name, Unset):
                changed = replace(changed, display_name=_clean_name(name))
            if not isinstance(role, Unset):
                changed = replace(changed, role=role)
            if not isinstance(active, Unset):
                changed = replace(changed, active=active)
            if not isinstance(discord_user_id, Unset):
                changed = replace(changed, discord_user_id=discord_user_id)
            if not isinstance(google_email, Unset):
                changed = replace(changed, google_email=google_email)
            if not isinstance(permissions, Unset):
                changed = replace(changed, permissions=self._valid_permissions(permissions))
            self._ensure_unique(
                uow, changed.display_name, changed.discord_user_id, exclude_id=person.id
            )
            self._guard_last_admin(uow, person, changed)
            uow.people.update(changed)
            uow.commit()
        log.info("person_updated", extra={"person_id": person.id, "actor_id": actor.id})
        return changed

    # ---- helpers --------------------------------------------------------------------------

    @staticmethod
    def _valid_permissions(raw: dict[str, bool]) -> dict[str, bool]:
        valid = {p.value for p in Permission}
        unknown = sorted(set(raw) - valid)
        if unknown:
            raise ValidationError(
                f"Unknown permission(s): {', '.join(unknown)}. Valid: {', '.join(sorted(valid))}"
            )
        return {k: bool(v) for k, v in raw.items()}

    @staticmethod
    def _ensure_unique(
        uow: UnitOfWork, name: str, discord_user_id: str | None, *, exclude_id: str | None
    ) -> None:
        by_name = uow.people.get_by_name(name)
        if by_name is not None and by_name.id != exclude_id:
            raise ConflictError("Someone with that name already exists")
        if discord_user_id:
            by_discord = uow.people.get_by_discord_id(discord_user_id)
            if by_discord is not None and by_discord.id != exclude_id:
                raise ConflictError("That Discord account is already linked to someone")

    @staticmethod
    def _guard_last_admin(uow: UnitOfWork, before: Person, after: Person) -> None:
        was_admin = before.active and before.role is Role.ADMIN
        still_admin = after.active and after.role is Role.ADMIN
        if was_admin and not still_admin:
            others = [
                p
                for p in uow.people.list(active_only=True)
                if p.role is Role.ADMIN and p.id != before.id
            ]
            if not others:
                raise ConflictError("There must be at least one active admin")
