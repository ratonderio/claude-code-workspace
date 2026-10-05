from __future__ import annotations

from dataclasses import dataclass

from family_hq.domain.enums import Source
from family_hq.domain.people import Person
from family_hq.errors import PermissionDeniedError
from family_hq.repositories.base import UnitOfWork


@dataclass(frozen=True)
class Actor:
    """Who is doing this, and through which door (decision D25)."""

    person: Person
    source: Source

    @property
    def id(self) -> str:
        return self.person.id


def reload_actor(uow: UnitOfWork, actor: Actor) -> Actor:
    """Re-read the actor's person inside the transaction.

    An Actor may have been built minutes or days ago (a Discord session, a long-running
    process). Role, permissions and active state are always taken from the database at the
    moment of the action, so deactivating or demoting someone takes effect immediately.
    """
    person = uow.people.get(actor.person.id)
    if person is None or not person.active:
        raise PermissionDeniedError("This person is inactive")
    return Actor(person, actor.source)
