from __future__ import annotations

from collections.abc import Callable
from typing import Any

import click

from family_hq.application.actor import Actor
from family_hq.application.patch import UNSET
from family_hq.application.task_service import NewTask, TaskPatch
from family_hq.cli import render
from family_hq.cli.context import CliState, emit_json, state_of
from family_hq.domain.dates import parse_when
from family_hq.domain.enums import Effort, Priority, Scope, TaskStatus
from family_hq.domain.tasks import Due, Task, TaskQuery

# ---- argument helpers -------------------------------------------------------------------------


def _due(state: CliState, text: str) -> Due:
    parsed = parse_when(text, state.container.clock.now(), state.settings.tz)
    return Due(parsed.deadline(state.settings.tz), parsed.all_day)


def _owner_id(state: CliState, actor: Actor, text: str) -> str | None:
    lowered = text.strip().lower()
    if lowered in ("me", "myself", "self"):
        return actor.id
    if lowered in ("none", "nobody", "unassigned", "-"):
        return None
    return state.container.people.find(text).id


def _project_id(state: CliState, actor: Actor, text: str) -> str:
    return state.container.projects.find(actor, text).id


def _category_id(state: CliState, text: str) -> str:
    return state.container.categories.find(text).id


def _show_task_line(state: CliState, actor: Actor, task: Task, headline: str) -> None:
    if state.json_output:
        names = state.names(actor)
        emit_json(render.task_to_dict(task, names, state.settings.tz, state.settings.effort_points))
    else:
        click.echo(f"{headline} {render.short(task.id)}  {task.title}  [{task.status.value}]")


# ---- command group ----------------------------------------------------------------------------


@click.group()
def task() -> None:
    """Create, change, find and inspect tasks."""


@task.command("add")
@click.argument("title")
@click.option("--desc", "description", help="Longer notes.")
@click.option("--owner", help="Person name, 'me', or 'none'. Family tasks default to unassigned.")
@click.option("--mine", is_flag=True, help="Shortcut for --owner me.")
@click.option(
    "--scope", default="family", show_default=True, help="family, personal or private-work."
)
@click.option("--project", help="Project name or id.")
@click.option("--category", help="Category name.")
@click.option("--priority", default="normal", show_default=True, help="low, normal, high, urgent.")
@click.option("--effort", help="xs, s, m, l, xl.")
@click.option("--due", help="today, tomorrow, fri, 'fri 5pm', 2026-10-09, +3d ...")
@click.option("--parent", help="Parent task id (makes this a subtask).")
@click.option("--inbox", is_flag=True, help="Capture into the inbox for later triage.")
@click.pass_context
def add(ctx: click.Context, title: str, description: str | None, owner: str | None, mine: bool,
        scope: str, project: str | None, category: str | None, priority: str,
        effort: str | None, due: str | None, parent: str | None, inbox: bool) -> None:  # fmt: skip
    """Create a task. Only the title is required."""
    state = state_of(ctx)
    actor = state.actor()
    owner_text = "me" if mine else owner
    owner_id = _owner_id(state, actor, owner_text) if owner_text else None
    parent_id = state.container.tasks.get(actor, parent).id if parent else None
    created = state.container.tasks.create(
        actor,
        NewTask(
            title=title,
            description=description,
            scope=Scope.parse(scope),
            owner_id=owner_id,
            project_id=_project_id(state, actor, project) if project else None,
            category_id=_category_id(state, category) if category else None,
            priority=Priority.parse(priority),
            effort=Effort.parse(effort) if effort else None,
            due=_due(state, due) if due else None,
            parent_task_id=parent_id,
            status=TaskStatus.INBOX if inbox else TaskStatus.OPEN,
        ),
    )
    _show_task_line(state, actor, created, "Created")


@task.command("list")
@click.option("--status", multiple=True, help="Repeatable. Default: all active statuses.")
@click.option("--all", "include_closed", is_flag=True, help="Include DONE and CANCELLED.")
@click.option("--mine", is_flag=True)
@click.option("--owner", help="Person name.")
@click.option("--unassigned", is_flag=True)
@click.option("--project")
@click.option("--category")
@click.option("--scope", multiple=True, help="Repeatable: family, personal, private-work.")
@click.option("--priority", multiple=True)
@click.option("--overdue", is_flag=True)
@click.option("--due-by", help="Due on or before this date (end of that day).")
@click.option("--done-since", help="Completed since this date (implies DONE).")
@click.option("--hide-snoozed", is_flag=True)
@click.option("--search", "text", help="Text in title or description.")
@click.option("--limit", type=int)
@click.pass_context
def list_tasks(ctx: click.Context, status: tuple[str, ...], include_closed: bool, mine: bool,
               owner: str | None, unassigned: bool, project: str | None, category: str | None,
               scope: tuple[str, ...], priority: tuple[str, ...], overdue: bool,
               due_by: str | None, done_since: str | None, hide_snoozed: bool,
               text: str | None, limit: int | None) -> None:  # fmt: skip
    """List tasks you are allowed to see."""
    state = state_of(ctx)
    actor = state.actor()
    tz = state.settings.tz
    now = state.container.clock.now()
    statuses = frozenset(TaskStatus.parse(s) for s in status) or None
    completed_after = None
    if done_since:
        completed_after = parse_when(done_since, now, tz, past=True).start(tz)
        statuses = frozenset({TaskStatus.DONE})
    query = TaskQuery(
        statuses=statuses,
        include_closed=include_closed,
        owner_id=actor.id if mine else (state.container.people.find(owner).id if owner else None),
        unassigned=unassigned,
        project_id=_project_id(state, actor, project) if project else None,
        category_id=_category_id(state, category) if category else None,
        scopes=frozenset(Scope.parse(s) for s in scope) or None,
        priorities=frozenset(Priority.parse(p) for p in priority) or None,
        due_before=_due(state, due_by).at if due_by else None,
        overdue_as_of=now if overdue else None,
        hide_snoozed_as_of=now if hide_snoozed else None,
        completed_after=completed_after,
        text=text,
        limit=limit,
    )
    tasks = state.container.tasks.list_tasks(actor, query)
    names = state.names(actor)
    if state.json_output:
        points = state.settings.effort_points
        emit_json([render.task_to_dict(t, names, tz, points) for t in tasks])
        return
    if not tasks:
        click.echo("No matching tasks.")
        return
    click.echo(render.task_table(tasks, names, tz, now))
    click.echo()
    click.echo(render.workload_summary(tasks, state.settings.effort_points))


@task.command("inbox")
@click.pass_context
def inbox(ctx: click.Context) -> None:
    """Tasks captured into the inbox and not yet triaged."""
    ctx.invoke(list_tasks, status=("INBOX",), include_closed=False, mine=False, owner=None,
               unassigned=False, project=None, category=None, scope=(), priority=(),
               overdue=False, due_by=None, done_since=None, hide_snoozed=False, text=None,
               limit=None)  # fmt: skip


@task.command("show")
@click.argument("ref")
@click.pass_context
def show(ctx: click.Context, ref: str) -> None:
    """Everything about one task, including its history. REF is an id or a unique id prefix."""
    state = state_of(ctx)
    actor = state.actor()
    c = state.container
    tz = state.settings.tz
    t = c.tasks.get(actor, ref)
    history = c.tasks.history(actor, t.id)
    names = state.names(actor)
    points = state.settings.effort_points
    if state.json_output:
        data = render.task_to_dict(t, names, tz, points)
        data["history"] = [render.event_to_dict(e) for e in history]
        emit_json(data)
        return
    now = c.clock.now()
    effort = "-"
    if t.effort:
        effort = f"{t.effort.value} ({points[t.effort]} pts)"
    click.echo(t.title)
    click.echo("=" * min(len(t.title), 72))
    fields = [
        ("id", t.id),
        ("status", t.status.value + (f" ({t.blocked_reason})" if t.blocked_reason else "")),
        ("scope", t.visibility_scope.value),
        ("owner", names.person(t.owner_id) if t.owner_id else "(unassigned)"),
        ("created by", names.person(t.creator_id)),
        ("priority", t.priority.value),
        ("effort", effort),
        ("due", render.fmt_due(t, tz, now)),
        ("project", names.project(t.project_id)),
        ("category", names.category(t.category_id)),
        ("created", render.fmt_dt(t.created_at, tz)),
        ("updated", render.fmt_dt(t.updated_at, tz)),
    ]
    if t.snoozed_until:
        fields.append(("snoozed until", render.fmt_dt(t.snoozed_until, tz)))
    if t.postpone_count:
        fields.append(("postponed", f"{t.postpone_count} time(s)"))
    if t.completed_at:
        fields.append(
            (
                "completed",
                f"{render.fmt_dt(t.completed_at, tz)} by {names.person(t.completed_by_id)}",
            )
        )
    if t.cancelled_at:
        fields.append(("cancelled", render.fmt_dt(t.cancelled_at, tz)))
    if t.parent_task_id:
        fields.append(("parent", render.short(t.parent_task_id)))
    for label, value in fields:
        click.echo(f"{label + ':':<15}{value}")
    if t.description:
        click.echo(f"\n{t.description}")
    click.echo("\nHistory")
    click.echo(render.history_lines(history, names, tz))


@task.command("history")
@click.argument("ref")
@click.pass_context
def history(ctx: click.Context, ref: str) -> None:
    """The activity log for one task."""
    state = state_of(ctx)
    actor = state.actor()
    t = state.container.tasks.get(actor, ref)
    events = state.container.tasks.history(actor, t.id)
    if state.json_output:
        emit_json([render.event_to_dict(e) for e in events])
    else:
        click.echo(render.history_lines(events, state.names(actor), state.settings.tz))


@task.command("edit")
@click.argument("ref")
@click.option("--title")
@click.option("--desc", "description")
@click.option("--priority")
@click.option("--effort")
@click.option("--no-effort", is_flag=True)
@click.option("--category")
@click.option("--no-category", is_flag=True)
@click.option("--project")
@click.option("--no-project", is_flag=True)
@click.option("--due")
@click.option("--no-due", is_flag=True)
@click.option(
    "--scope", help="family, personal, private-work. Changing it changes who can see the task."
)
@click.pass_context
def edit(ctx: click.Context, ref: str, title: str | None, description: str | None,
         priority: str | None, effort: str | None, no_effort: bool, category: str | None,
         no_category: bool, project: str | None, no_project: bool, due: str | None,
         no_due: bool, scope: str | None) -> None:  # fmt: skip
    """Change fields. Only the options you pass are touched."""
    state = state_of(ctx)
    actor = state.actor()
    patch = TaskPatch(
        title=title if title is not None else UNSET,
        description=description if description is not None else UNSET,
        priority=Priority.parse(priority) if priority else UNSET,
        effort=None if no_effort else (Effort.parse(effort) if effort else UNSET),
        category_id=None if no_category else (_category_id(state, category) if category else UNSET),
        project_id=None
        if no_project
        else (_project_id(state, actor, project) if project else UNSET),
        due=None if no_due else (_due(state, due) if due else UNSET),
        scope=Scope.parse(scope) if scope else UNSET,
    )
    updated = state.container.tasks.update(actor, ref, patch)
    _show_task_line(state, actor, updated, "Updated")


@task.command("assign")
@click.argument("ref")
@click.argument("person")
@click.pass_context
def assign(ctx: click.Context, ref: str, person: str) -> None:
    """Assign to a person (name or 'me'), or 'none' to release back to the pool."""
    state = state_of(ctx)
    actor = state.actor()
    updated = state.container.tasks.assign(actor, ref, _owner_id(state, actor, person))
    _show_task_line(state, actor, updated, "Assigned")


def _simple(
    name: str, help_text: str, call: Callable[[Any, Actor, str], Task], headline: str
) -> None:
    @task.command(name, help=help_text)
    @click.argument("ref")
    @click.pass_context
    def command(ctx: click.Context, ref: str) -> None:
        state = state_of(ctx)
        actor = state.actor()
        _show_task_line(state, actor, call(state.container.tasks, actor, ref), headline)


_simple("claim", "Claim an unassigned task for yourself.", lambda s, a, r: s.claim(a, r), "Claimed")
_simple("start", "Mark in progress.", lambda s, a, r: s.start(a, r), "Started")
_simple("done", "Mark complete.", lambda s, a, r: s.complete(a, r), "Completed")
_simple("unblock", "Clear BLOCKED or WAITING.", lambda s, a, r: s.unblock(a, r), "Unblocked")
_simple("reopen", "Reopen a DONE or CANCELLED task.", lambda s, a, r: s.reopen(a, r), "Reopened")


@task.command("wait")
@click.argument("ref")
@click.argument("reason", required=False)
@click.pass_context
def wait(ctx: click.Context, ref: str, reason: str | None) -> None:
    """Mark WAITING (on a reply, a delivery, a person). Reason optional."""
    state = state_of(ctx)
    actor = state.actor()
    _show_task_line(state, actor, state.container.tasks.wait(actor, ref, reason), "Waiting")


@task.command("block")
@click.argument("ref")
@click.argument("reason")
@click.pass_context
def block(ctx: click.Context, ref: str, reason: str) -> None:
    """Mark BLOCKED with a reason."""
    state = state_of(ctx)
    actor = state.actor()
    _show_task_line(state, actor, state.container.tasks.block(actor, ref, reason), "Blocked")


@task.command("snooze")
@click.argument("ref")
@click.argument("until")
@click.pass_context
def snooze(ctx: click.Context, ref: str, until: str) -> None:
    """Hide from actionable views until a date (start of that day) or date and time."""
    state = state_of(ctx)
    actor = state.actor()
    tz = state.settings.tz
    when = parse_when(until, state.container.clock.now(), tz).start(tz)
    _show_task_line(state, actor, state.container.tasks.snooze(actor, ref, when), "Snoozed")


@task.command("cancel")
@click.argument("ref")
@click.option("--reason")
@click.pass_context
def cancel(ctx: click.Context, ref: str, reason: str | None) -> None:
    """Cancel a task (kept in history)."""
    state = state_of(ctx)
    actor = state.actor()
    _show_task_line(state, actor, state.container.tasks.cancel(actor, ref, reason), "Cancelled")


@task.command("triage")
@click.argument("ref")
@click.argument("status", type=click.Choice(["inbox", "open", "planned"], case_sensitive=False))
@click.pass_context
def triage(ctx: click.Context, ref: str, status: str) -> None:
    """Move a task between INBOX, OPEN and PLANNED."""
    state = state_of(ctx)
    actor = state.actor()
    updated = state.container.tasks.set_status(actor, ref, TaskStatus.parse(status))
    _show_task_line(state, actor, updated, "Moved")


@task.command("note")
@click.argument("ref")
@click.argument("text")
@click.pass_context
def note(ctx: click.Context, ref: str, text: str) -> None:
    """Add a comment to a task's history."""
    state = state_of(ctx)
    actor = state.actor()
    state.container.tasks.add_note(actor, ref, text)
    if not state.json_output:
        click.echo("Note added.")
