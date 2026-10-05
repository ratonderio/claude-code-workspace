from __future__ import annotations

import click

from family_hq.application.patch import UNSET
from family_hq.application.project_service import NewProject
from family_hq.cli import render
from family_hq.cli.context import emit_json, state_of
from family_hq.domain.dates import parse_when
from family_hq.domain.enums import ProjectStatus, Scope
from family_hq.domain.tasks import Due, TaskQuery


def _due(ctx: click.Context, text: str) -> Due:
    state = state_of(ctx)
    parsed = parse_when(text, state.container.clock.now(), state.settings.tz)
    return Due(parsed.deadline(state.settings.tz), parsed.all_day)


@click.group()
def project() -> None:
    """Group related tasks (Fix Van, Vacation, House Repairs...)."""


@project.command("add")
@click.argument("name")
@click.option("--desc", "description")
@click.option("--scope", default="family", show_default=True)
@click.option("--due")
@click.pass_context
def add(
    ctx: click.Context, name: str, description: str | None, scope: str, due: str | None
) -> None:
    state = state_of(ctx)
    actor = state.actor()
    created = state.container.projects.create(
        actor,
        NewProject(
            name=name,
            description=description,
            scope=Scope.parse(scope),
            due=_due(ctx, due) if due else None,
        ),
    )
    if state.json_output:
        emit_json(render.project_to_dict(created, state.names(actor)))
    else:
        click.echo(f"Created project {created.name} ({render.short(created.id)})")


@project.command("list")
@click.option("--all", "include_closed", is_flag=True, help="Include DONE and ARCHIVED.")
@click.pass_context
def list_projects(ctx: click.Context, include_closed: bool) -> None:
    state = state_of(ctx)
    actor = state.actor()
    projects = state.container.projects.list_projects(actor, include_closed=include_closed)
    names = state.names(actor)
    if state.json_output:
        emit_json([render.project_to_dict(p, names) for p in projects])
        return
    if not projects:
        click.echo("No projects.")
        return
    tz = state.settings.tz
    rows = []
    for p in projects:
        open_count = len(state.container.tasks.list_tasks(actor, TaskQuery(project_id=p.id)))
        rows.append(
            [
                render.short(p.id),
                p.status.value,
                "" if p.visibility_scope is Scope.FAMILY else p.visibility_scope.value,
                render.fmt_dt(p.due_at, tz) if p.due_at else "-",
                str(open_count),
                p.name,
            ]
        )
    click.echo(render.table(["ID", "STATUS", "SCOPE", "DUE", "OPEN", "NAME"], rows))


@project.command("show")
@click.argument("ref")
@click.pass_context
def show(ctx: click.Context, ref: str) -> None:
    state = state_of(ctx)
    actor = state.actor()
    c = state.container
    p = c.projects.find(actor, ref)
    tasks = c.tasks.list_tasks(actor, TaskQuery(project_id=p.id, include_closed=True))
    names = state.names(actor)
    tz = state.settings.tz
    if state.json_output:
        data = render.project_to_dict(p, names)
        data["tasks"] = [
            render.task_to_dict(t, names, tz, state.settings.effort_points) for t in tasks
        ]
        emit_json(data)
        return
    click.echo(f"{p.name}  [{p.status.value}, {p.visibility_scope.value}]")
    if p.description:
        click.echo(p.description)
    active = [t for t in tasks if t.is_active]
    click.echo(f"\nOpen work: {render.workload_summary(active, state.settings.effort_points)}")
    if tasks:
        click.echo(render.task_table(tasks, names, tz, c.clock.now()))


@project.command("edit")
@click.argument("ref")
@click.option("--name")
@click.option("--desc", "description")
@click.option("--due")
@click.option("--no-due", is_flag=True)
@click.pass_context
def edit(ctx: click.Context, ref: str, name: str | None, description: str | None,
         due: str | None, no_due: bool) -> None:  # fmt: skip
    state = state_of(ctx)
    actor = state.actor()
    updated = state.container.projects.update(
        actor,
        ref,
        name=name if name is not None else UNSET,
        description=description if description is not None else UNSET,
        due=None if no_due else (_due(ctx, due) if due else UNSET),
    )
    click.echo(f"Updated project {updated.name}")


@project.command("status")
@click.argument("ref")
@click.argument("status")
@click.pass_context
def set_status(ctx: click.Context, ref: str, status: str) -> None:
    """Set ACTIVE, ON_HOLD, DONE or ARCHIVED."""
    state = state_of(ctx)
    actor = state.actor()
    updated = state.container.projects.update(actor, ref, status=ProjectStatus.parse(status))
    click.echo(f"{updated.name} is now {updated.status.value}")
