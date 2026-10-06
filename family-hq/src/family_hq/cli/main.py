from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from family_hq import __version__
from family_hq.app import (
    database_description,
    run_forever,
    startup,
    warn_if_synced_folder,
)
from family_hq.cli import admin_cmds, project_cmds, task_cmds
from family_hq.cli.context import CliState, state_of
from family_hq.config import find_config_path, load_secrets, load_settings
from family_hq.db.migrate import current_revision, head_revision
from family_hq.domain.enums import Scope, Sink
from family_hq.errors import FamilyHQError
from family_hq.logging_setup import configure_logging


class FamilyHQGroup(click.Group):
    """Turn expected errors (permission, validation, config...) into a clean message."""

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except FamilyHQError as exc:
            click.echo(f"Error: {exc}", err=True)
            ctx.exit(1)
        finally:
            state = ctx.find_object(CliState)
            if state is not None:
                state.close()


@click.group(cls=FamilyHQGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__)
@click.option(
    "--config", "config_path", type=click.Path(path_type=Path), help="Path to config.toml."
)
@click.option(
    "--as", "as_name", envvar="FAMILY_HQ_ACTOR", help="Act as this person (display name)."
)
@click.option(
    "--json", "json_output", is_flag=True, help="Machine-readable output where supported."
)
@click.option("-v", "--verbose", is_flag=True, help="Show service log messages.")
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, as_name: str | None, json_output: bool,
        verbose: bool) -> None:  # fmt: skip
    """Family HQ: household tasks, workload tracking and reporting."""
    ctx.obj = CliState(config_path, as_name, json_output, verbose)


cli.add_command(task_cmds.task)
cli.add_command(project_cmds.project)
cli.add_command(admin_cmds.person)
cli.add_command(admin_cmds.category)
cli.add_command(admin_cmds.backup)


@cli.command("init")
@click.option("--admin", "admin_name", help="Name of the first administrator (you).")
@click.option("--discord-id", help="That person's Discord user id (can be added later).")
@click.pass_context
def init(ctx: click.Context, admin_name: str | None, discord_id: str | None) -> None:
    """Create the database, apply migrations, seed categories, create the first admin."""
    state = state_of(ctx)
    container = state.container  # startup(): data dir, migrations, category seed
    click.echo(f"Database: {database_description(state.settings)}")
    if not container.people.has_people():
        name = admin_name or click.prompt("Your name (the first administrator)")
        admin = container.people.bootstrap_admin(name, discord_user_id=discord_id)
        click.echo(f"Created administrator {admin.display_name}")
    else:
        click.echo("People already exist; nothing to bootstrap.")
    click.echo(f"Categories: {', '.join(c.name for c in container.categories.list_categories())}")
    click.echo('Ready. Try: family-hq task add "My first task"')


@cli.group("db")
def db_group() -> None:
    """Database schema management."""


@db_group.command("upgrade")
@click.pass_context
def db_upgrade(ctx: click.Context) -> None:
    """Apply migrations (also done automatically by every command)."""
    state = state_of(ctx)
    startup(state.settings).close()
    click.echo("Database is up to date.")


@db_group.command("current")
@click.pass_context
def db_current(ctx: click.Context) -> None:
    state = state_of(ctx)
    engine = state.container.engine
    click.echo(f"current: {current_revision(engine)}   head: {head_revision()}")


@cli.group("config")
def config_group() -> None:
    """Inspect configuration."""


@config_group.command("check")
@click.pass_context
def config_check(ctx: click.Context) -> None:
    """Validate configuration and show the effective, non-secret values."""
    state = state_of(ctx)
    settings = state.settings
    path = find_config_path(state.config_path)
    secrets = load_secrets(settings)
    click.echo(f"config file : {path}")
    click.echo(f"time zone   : {settings.app.timezone}")
    click.echo(f"database    : {database_description(settings)}")
    click.echo(f"data dir    : {settings.data_dir}")
    warning = warn_if_synced_folder(settings.database_url)
    if warning:
        click.echo(f"WARNING     : {warning}")
    click.echo("sink policy (which scope may go where):")
    policy = settings.sink_policy
    for scope in Scope:
        allowed = ", ".join(s.value for s in Sink if policy.allows(scope, s)) or "(nowhere)"
        click.echo(f"  {scope.value:<13} {allowed}")
    click.echo("backup destinations:")
    for d in settings.backup_destinations:
        scrub = f"  scrubs {', '.join(d.scrub_scopes)}" if d.scrub_scopes else ""
        click.echo(f"  {d.name}: {d.path}{scrub}")
    click.echo(f"secrets     : discord token {'set' if secrets.discord_token else 'not set'}, "
               f"AI key {'set' if secrets.ai_api_key else 'not set'}")  # fmt: skip


@cli.command("run")
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the long-lived service (startup checks, scheduled jobs; Discord arrives in Phase 2)."""
    settings = load_settings(state_of(ctx).config_path)
    configure_logging(settings.logging, settings.resolve)
    container = startup(settings)
    click.echo("Family HQ is running. Press Ctrl+C to stop.", err=True)
    try:
        asyncio.run(run_forever(container))
    except KeyboardInterrupt:  # Windows has no loop signal handlers; Ctrl+C lands here
        click.echo("Stopping.", err=True)
    finally:
        container.close()


def main() -> None:  # pragma: no cover
    cli(prog_name="family-hq")
    sys.exit(0)
