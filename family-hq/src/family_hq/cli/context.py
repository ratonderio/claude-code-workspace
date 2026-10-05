from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

from family_hq.app import Container, startup
from family_hq.application.actor import Actor
from family_hq.config import Settings, load_settings
from family_hq.domain.enums import Source
from family_hq.errors import ConfigError
from family_hq.logging_setup import configure_logging

ENV_ACTOR = "FAMILY_HQ_ACTOR"


@dataclass
class Names:
    """id -> display name lookups for rendering (what the actor is allowed to see)."""

    people: dict[str, str] = field(default_factory=dict)
    projects: dict[str, str] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)

    def person(self, person_id: str | None) -> str:
        return "-" if person_id is None else self.people.get(person_id, "?")

    def project(self, project_id: str | None) -> str:
        return "-" if project_id is None else self.projects.get(project_id, "?")

    def category(self, category_id: str | None) -> str:
        return "-" if category_id is None else self.categories.get(category_id, "?")


class CliState:
    """Lazily loads settings and the service container once per invocation."""

    def __init__(
        self, config_path: Path | None, as_name: str | None, json_output: bool, verbose: bool
    ) -> None:
        self.config_path = config_path
        self.as_name = as_name
        self.json_output = json_output
        self.verbose = verbose
        self._settings: Settings | None = None
        self._container: Container | None = None

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings(self.config_path)
            section = self._settings.logging.model_copy()
            if not self.verbose:
                section.level = "WARNING"  # CLI users do not want service-style log chatter
            configure_logging(section, self._settings.resolve)
        return self._settings

    @property
    def container(self) -> Container:
        if self._container is None:
            self._container = startup(self.settings)
        return self._container

    def actor(self) -> Actor:
        name = self.as_name or os.environ.get(ENV_ACTOR) or self.settings.cli.default_actor
        people = self.container.people
        if name:
            return people.actor_for(name, Source.CLI)
        admin = people.sole_admin()
        if admin is not None:
            return Actor(admin, Source.CLI)
        raise ConfigError(
            "Say who is acting: --as NAME, FAMILY_HQ_ACTOR, or [cli] default_actor in config.toml"
        )

    def names(self, actor: Actor) -> Names:
        c = self.container
        return Names(
            people={p.id: p.display_name for p in c.people.list_people(actor, active_only=False)},
            projects={p.id: p.name for p in c.projects.list_projects(actor, include_closed=True)},
            categories={x.id: x.name for x in c.categories.list_categories(active_only=False)},
        )

    def close(self) -> None:
        if self._container is not None:
            self._container.close()


def state_of(ctx: click.Context) -> CliState:
    state = ctx.find_object(CliState)
    assert state is not None
    return state


def emit_json(data: Any) -> None:
    click.echo(json.dumps(data, indent=2, default=str, ensure_ascii=False))
