"""Visibility rules, in one place.

Two separate questions (see docs/permissions.md):

* can_view: may this PERSON see an object with this scope and owner?
* SinkPolicy: may content of this SCOPE be sent to this integration?

The SQL equivalent of can_view lives in repositories/sqlalchemy/visibility.py and is
verified against this function by tests/test_visibility.py.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from family_hq.domain.enums import Scope, Sink
from family_hq.domain.people import Person
from family_hq.errors import ConfigError

# Declaration order of Scope is the restrictiveness rank: FAMILY < PERSONAL < PRIVATE_WORK.
SCOPE_RANK: dict[Scope, int] = {scope: rank for rank, scope in enumerate(Scope)}


def stricter(a: Scope, b: Scope) -> Scope:
    return a if SCOPE_RANK[a] >= SCOPE_RANK[b] else b


def is_at_least_as_restrictive(scope: Scope, than: Scope) -> bool:
    return SCOPE_RANK[scope] >= SCOPE_RANK[than]


def can_view(person: Person, scope: Scope, owner_id: str | None) -> bool:
    """FAMILY is visible to every active person. Everything else only to its owner.

    Roles never override ownership of private data (decision D3).
    """
    if not person.active:
        return False
    if scope is Scope.FAMILY:
        return True
    return owner_id is not None and owner_id == person.id


# Sinks that reach other people. These accept FAMILY content only, always.
FAMILY_ONLY_SINKS: frozenset[Sink] = frozenset({Sink.DISCORD_CHANNEL, Sink.GOOGLE_FAMILY})

_DEFAULT_SINKS: dict[Scope, frozenset[Sink]] = {
    Scope.FAMILY: frozenset(Sink),
    Scope.PERSONAL: frozenset({Sink.DISCORD_EPHEMERAL, Sink.OBSIDIAN}),
    Scope.PRIVATE_WORK: frozenset({Sink.OBSIDIAN}),
}


@dataclass(frozen=True)
class SinkPolicy:
    allowed: Mapping[Scope, frozenset[Sink]]

    def __post_init__(self) -> None:
        for scope, sinks in self.allowed.items():
            if scope is not Scope.FAMILY:
                bad = sinks & FAMILY_ONLY_SINKS
                if bad:
                    names = ", ".join(sorted(s.value for s in bad))
                    raise ConfigError(
                        f"Scope {scope.value} may not be enabled for family-audience sinks: {names}"
                    )

    @classmethod
    def default(cls) -> SinkPolicy:
        return cls(dict(_DEFAULT_SINKS))

    @classmethod
    def from_lists(cls, raw: Mapping[str, Iterable[str]] | None) -> SinkPolicy:
        """Build from config shape {"FAMILY": ["OBSIDIAN"]}; omitted scopes use defaults."""
        merged: dict[Scope, frozenset[Sink]] = dict(_DEFAULT_SINKS)
        for scope_name, sink_names in (raw or {}).items():
            try:
                scope = Scope.parse(scope_name)
                merged[scope] = frozenset(Sink.parse(s) for s in sink_names)
            except Exception as exc:  # ValidationError -> ConfigError with context
                raise ConfigError(f"visibility.sinks.{scope_name}: {exc}") from exc
        return cls(merged)

    def allows(self, scope: Scope, sink: Sink) -> bool:
        if scope is not Scope.FAMILY and sink in FAMILY_ONLY_SINKS:
            return False
        return sink in self.allowed.get(scope, frozenset())
