from __future__ import annotations

from pathlib import Path

import click

from family_hq.application.patch import UNSET
from family_hq.cli import render
from family_hq.cli.context import emit_json, state_of
from family_hq.domain.enums import Role, Scope
from family_hq.domain.people import Permission


def _permissions(pairs: tuple[str, ...]) -> dict[str, bool]:
    """--perm assign_others=true --perm manage_projects=false"""
    parsed: dict[str, bool] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or value.lower() not in ("true", "false", "yes", "no", "1", "0"):
            raise click.BadParameter(f"'{pair}': use NAME=true or NAME=false")
        parsed[key.strip()] = value.lower() in ("true", "yes", "1")
    return parsed


# ---- people -----------------------------------------------------------------------------------


@click.group()
def person() -> None:
    """Household members."""


@person.command("add")
@click.argument("name")
@click.option("--role", default="member", show_default=True, help="admin, adult or member.")
@click.option("--discord-id", help="Discord user id (Developer Mode > right-click > Copy User ID).")
@click.option("--google-email")
@click.option("--perm", "perms", multiple=True, help="Override, e.g. assign_others=true")
@click.pass_context
def add_person(ctx: click.Context, name: str, role: str, discord_id: str | None,
               google_email: str | None, perms: tuple[str, ...]) -> None:  # fmt: skip
    state = state_of(ctx)
    created = state.container.people.add(
        state.actor(),
        name,
        Role.parse(role),
        discord_user_id=discord_id,
        google_email=google_email,
        permissions=_permissions(perms),
    )
    click.echo(f"Added {created.display_name} ({created.role.value})")


@person.command("list")
@click.option("--all", "include_inactive", is_flag=True)
@click.pass_context
def list_people(ctx: click.Context, include_inactive: bool) -> None:
    state = state_of(ctx)
    people = state.container.people.list_people(state.actor(), active_only=not include_inactive)
    if state.json_output:
        emit_json(
            [
                {
                    "id": p.id,
                    "name": p.display_name,
                    "role": p.role.value,
                    "active": p.active,
                    "discord_user_id": p.discord_user_id,
                    "permissions": p.permissions,
                }
                for p in people
            ]
        )
        return
    rows = [
        [
            render.short(p.id),
            p.display_name,
            p.role.value,
            "yes" if p.active else "no",
            p.discord_user_id or "-",
            ", ".join(f"{k}={v}" for k, v in p.permissions.items()) or "-",
        ]
        for p in people
    ]
    click.echo(render.table(["ID", "NAME", "ROLE", "ACTIVE", "DISCORD ID", "OVERRIDES"], rows))


@person.command("edit")
@click.argument("ref")
@click.option("--name")
@click.option("--role")
@click.option("--discord-id")
@click.option("--google-email")
@click.option("--deactivate", is_flag=True)
@click.option("--activate", is_flag=True)
@click.option("--perm", "perms", multiple=True, help="Replaces ALL overrides with these.")
@click.option("--clear-perms", is_flag=True)
@click.pass_context
def edit_person(ctx: click.Context, ref: str, name: str | None, role: str | None,
                discord_id: str | None, google_email: str | None, deactivate: bool,
                activate: bool, perms: tuple[str, ...], clear_perms: bool) -> None:  # fmt: skip
    state = state_of(ctx)
    updated = state.container.people.update(
        state.actor(),
        ref,
        name=name if name is not None else UNSET,
        role=Role.parse(role) if role else UNSET,
        active=False if deactivate else (True if activate else UNSET),
        discord_user_id=discord_id if discord_id is not None else UNSET,
        google_email=google_email if google_email is not None else UNSET,
        permissions={} if clear_perms else (_permissions(perms) if perms else UNSET),
    )
    click.echo(f"Updated {updated.display_name}")


@person.command("permissions")
def list_permissions() -> None:
    """List the permission names usable with --perm."""
    for p in Permission:
        click.echo(p.value)


# ---- categories -------------------------------------------------------------------------------


@click.group()
def category() -> None:
    """Task categories (configurable)."""


@category.command("list")
@click.option("--all", "include_inactive", is_flag=True)
@click.pass_context
def list_categories(ctx: click.Context, include_inactive: bool) -> None:
    state = state_of(ctx)
    items = state.container.categories.list_categories(active_only=not include_inactive)
    if state.json_output:
        emit_json([{"id": c.id, "name": c.name, "active": c.active} for c in items])
        return
    for c in items:
        click.echo(c.name + ("" if c.active else "  (inactive)"))


@category.command("add")
@click.argument("name")
@click.pass_context
def add_category(ctx: click.Context, name: str) -> None:
    state = state_of(ctx)
    created = state.container.categories.add(state.actor(), name)
    click.echo(f"Added category {created.name}")


@category.command("rename")
@click.argument("name")
@click.argument("new_name")
@click.pass_context
def rename_category(ctx: click.Context, name: str, new_name: str) -> None:
    state = state_of(ctx)
    updated = state.container.categories.rename(state.actor(), name, new_name)
    click.echo(f"Renamed to {updated.name}")


@category.command("deactivate")
@click.argument("name")
@click.pass_context
def deactivate_category(ctx: click.Context, name: str) -> None:
    state = state_of(ctx)
    state.container.categories.set_active(state.actor(), name, False)
    click.echo("Deactivated (existing tasks keep it; new tasks cannot use it).")


@category.command("activate")
@click.argument("name")
@click.pass_context
def activate_category(ctx: click.Context, name: str) -> None:
    state = state_of(ctx)
    state.container.categories.set_active(state.actor(), name, True)
    click.echo("Activated.")


# ---- backups ----------------------------------------------------------------------------------


def _backups(ctx: click.Context):  # type: ignore[no-untyped-def]
    state = state_of(ctx)
    service = state.container.backups
    if service is None:
        raise click.ClickException("Backups are only supported for a local SQLite database.")
    return state, service


@click.group()
def backup() -> None:
    """Create, list, prune and verify database backups."""


@backup.command("create")
@click.option("--destination", help="Only this configured destination.")
@click.option(
    "--to", "to", type=click.Path(path_type=Path), help="Ad-hoc file (.sqlite3) or folder."
)
@click.option("--scrub", multiple=True, help="Remove this scope from the copy (e.g. PRIVATE_WORK).")
@click.pass_context
def create_backup(ctx: click.Context, destination: str | None, to: Path | None,
                  scrub: tuple[str, ...]) -> None:  # fmt: skip
    """Back up now. Use --scrub PRIVATE_WORK --to FILE for a copy that leaves work data behind."""
    state, service = _backups(ctx)
    results = service.create(
        state.actor(), destination=destination, to=to, scrub=[Scope.parse(s) for s in scrub]
    )
    for r in results:
        scrubbed = f"  scrubbed: {', '.join(s.value for s in r.scrubbed)}" if r.scrubbed else ""
        click.echo(f"[{r.destination}] {r.path}  ({r.size_bytes:,} bytes){scrubbed}")
        for p in r.pruned:
            click.echo(f"  pruned {p.name}")


@backup.command("list")
@click.pass_context
def list_backups(ctx: click.Context) -> None:
    state, service = _backups(ctx)
    for name, files in service.list_files(state.actor()).items():
        click.echo(f"[{name}]")
        for f in files:
            click.echo(f"  {f.path.name}  {f.size_bytes:>10,} bytes")
        if not files:
            click.echo("  (none)")


@backup.command("prune")
@click.option("--destination")
@click.pass_context
def prune_backups(ctx: click.Context, destination: str | None) -> None:
    state, service = _backups(ctx)
    for name, removed in service.prune(state.actor(), destination).items():
        click.echo(f"[{name}] removed {len(removed)} old backup(s)")


@backup.command("verify")
@click.argument("path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.pass_context
def verify_backup(ctx: click.Context, path: Path) -> None:
    """Check a backup file's integrity and show what it contains."""
    state, service = _backups(ctx)
    report = service.verify(state.actor(), path)
    status = "OK" if report.integrity_ok else "FAILED"
    click.echo(f"integrity: {status}   schema revision: {report.migration_revision or 'unknown'}")
    click.echo(", ".join(f"{k}={v}" for k, v in report.counts.items()))
    if not report.integrity_ok:
        raise click.exceptions.Exit(1)
