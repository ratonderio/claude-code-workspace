from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from family_hq.app import Container, startup
from family_hq.application.actor import Actor
from family_hq.clock import FixedClock
from family_hq.config import Settings
from family_hq.domain.enums import Role, Source
from family_hq.domain.people import Person

# A Wednesday, 2026-10-07 15:00 UTC = 11:00 in New York (EDT).
START = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


@dataclass
class World:
    container: Container
    clock: FixedClock
    admin: Actor
    adult: Actor
    kid: Actor
    kid2: Actor
    settings: Settings

    # convenient service shortcuts
    @property
    def tasks(self):  # type: ignore[no-untyped-def]
        return self.container.tasks

    @property
    def projects(self):  # type: ignore[no-untyped-def]
        return self.container.projects

    @property
    def people(self):  # type: ignore[no-untyped-def]
        return self.container.people


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    data = {"app": {"timezone": "America/New_York", "data_dir": "data"}}
    data.update(overrides)  # type: ignore[arg-type]
    settings = Settings.model_validate(data)
    settings.base_dir = tmp_path
    return settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def world(tmp_path: Path, settings: Settings) -> World:
    clock = FixedClock(START)
    container = startup(settings, clock)
    admin_person = container.people.bootstrap_admin("Joey")
    admin = Actor(admin_person, Source.CLI)
    adult = Actor(container.people.add(admin, "Mysti", Role.ADULT), Source.DISCORD)
    kid = Actor(container.people.add(admin, "Wyatt", Role.MEMBER), Source.DISCORD)
    kid2 = Actor(container.people.add(admin, "Ada", Role.MEMBER), Source.DISCORD)
    yield_world = World(container, clock, admin, adult, kid, kid2, settings)
    return yield_world


def person_of(actor: Actor) -> Person:
    return actor.person
