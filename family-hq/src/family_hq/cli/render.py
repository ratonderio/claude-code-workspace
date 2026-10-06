"""Plain-text rendering (ASCII only, so Windows consoles never choke) and JSON shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from family_hq.cli.context import Names
from family_hq.domain.enums import Effort, EventType, Scope
from family_hq.domain.events import ActivityEvent
from family_hq.domain.projects import Project
from family_hq.domain.tasks import Task
from family_hq.domain.workload import points_for


def short(task_id: str) -> str:
    return task_id[:8]


def fmt_dt(value: datetime | None, tz: ZoneInfo) -> str:
    return "-" if value is None else value.astimezone(tz).strftime("%a %Y-%m-%d %H:%M")


def fmt_due(task: Task, tz: ZoneInfo, now: datetime) -> str:
    if task.due_at is None:
        return "-"
    local = task.due_at.astimezone(tz)
    text = (
        local.strftime("%a %Y-%m-%d") if task.due_all_day else local.strftime("%a %Y-%m-%d %H:%M")
    )
    return f"{text} OVERDUE" if task.is_overdue(now) else text


def table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def line(cells: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    out = [line(headers), line(["-" * w for w in widths])]
    out.extend(line(r) for r in rows)
    return "\n".join(out)


def task_table(tasks: list[Task], names: Names, tz: ZoneInfo, now: datetime) -> str:
    show_scope = any(t.visibility_scope is not Scope.FAMILY for t in tasks)
    headers = ["ID", "STATUS", "PRI", "OWNER", "DUE", "EFF"]
    if show_scope:
        headers.append("SCOPE")
    headers += ["TITLE"]
    rows = []
    for t in tasks:
        status = t.status.value + (" zz" if t.is_snoozed(now) else "")
        row = [
            short(t.id),
            status,
            t.priority.value,
            names.person(t.owner_id) if t.owner_id else "(unassigned)",
            fmt_due(t, tz, now),
            t.effort.value if t.effort else "-",
        ]
        if show_scope:
            row.append("" if t.visibility_scope is Scope.FAMILY else t.visibility_scope.value)
        suffix = f"  [{names.project(t.project_id)}]" if t.project_id else ""
        row.append(t.title + suffix)
        rows.append(row)
    return table(headers, rows)


def workload_summary(tasks: list[Task], points: dict[Effort, int]) -> str:
    total = sum(points_for(t.effort, points) for t in tasks)
    unestimated = sum(1 for t in tasks if t.effort is None)
    text = f"{len(tasks)} task(s), about {total} workload points"
    return text + (f", {unestimated} unestimated" if unestimated else "")


def describe_event(event: ActivityEvent, names: Names, tz: ZoneInfo) -> str:
    d = event.data
    t = event.event_type
    who = names.person(event.actor_id)
    if t is EventType.TASK_CREATED:
        owner = f", assigned to {names.person(d.get('owner_id'))}" if d.get("owner_id") else ""
        return f"{who} created it ({d.get('scope', '?')}{owner})"
    if t is EventType.TASK_UPDATED:
        parts = []
        for key, value in d.get("changes", {}).items():
            if key == "description_changed":
                parts.append("description")
            elif isinstance(value, list) and len(value) == 2:
                parts.append(f"{key}: {value[0]} -> {value[1]}")
        return f"{who} edited " + ("; ".join(parts) or "it")
    if t is EventType.TASK_CLAIMED:
        return f"{who} claimed it" + (" (automatically)" if d.get("auto") else "")
    if t in (EventType.TASK_ASSIGNED, EventType.TASK_UNASSIGNED):
        if t is EventType.TASK_ASSIGNED:
            return f"{who} assigned it to {names.person(d.get('to'))}"
        return f"{who} released it from {names.person(d.get('from'))}"
    if t is EventType.DEADLINE_CHANGED:
        text = f"{who} changed the deadline: {d.get('from') or 'none'} -> {d.get('to') or 'none'}"
        return text + (" (postponed)" if d.get("postponed") else "")
    if t is EventType.TASK_NOTE_ADDED:
        return f'{who} noted: "{d.get("text", "")}"'
    if t in (EventType.TASK_BLOCKED, EventType.TASK_WAITING):
        word = "blocked" if t is EventType.TASK_BLOCKED else "waiting"
        reason = f": {d['reason']}" if d.get("reason") else ""
        return f"{who} marked it {word}{reason}"
    if t is EventType.TASK_CANCELLED:
        return f"{who} cancelled it" + (f": {d['reason']}" if d.get("reason") else "")
    if t is EventType.TASK_SNOOZED:
        return f"{who} snoozed it until {d.get('until')}"
    if t is EventType.SCOPE_CHANGED:
        return f"{who} changed visibility {d.get('from')} -> {d.get('to')}"
    if t is EventType.TASK_STATUS_CHANGED:
        return f"{who} moved it {d.get('from')} -> {d.get('to')}"
    simple = {
        EventType.TASK_STARTED: "started it",
        EventType.TASK_UNBLOCKED: "unblocked it",
        EventType.TASK_COMPLETED: "completed it",
        EventType.TASK_REOPENED: "reopened it",
        EventType.PROJECT_CREATED: "created the project",
        EventType.PROJECT_UPDATED: "updated the project",
    }
    return f"{who} {simple.get(t, t.value.lower())}"


def history_lines(events: list[ActivityEvent], names: Names, tz: ZoneInfo) -> str:
    return "\n".join(
        f"  {fmt_dt(e.occurred_at, tz)}  {describe_event(e, names, tz)}" for e in events
    )


# ---- JSON shapes ------------------------------------------------------------------------------


def task_to_dict(
    task: Task, names: Names, tz: ZoneInfo, points: dict[Effort, int]
) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "scope": task.visibility_scope.value,
        "priority": task.priority.value,
        "effort": task.effort.value if task.effort else None,
        "workload_points": points_for(task.effort, points),
        "owner": names.person(task.owner_id) if task.owner_id else None,
        "owner_id": task.owner_id,
        "creator_id": task.creator_id,
        "project": names.project(task.project_id) if task.project_id else None,
        "project_id": task.project_id,
        "category": names.category(task.category_id) if task.category_id else None,
        "category_id": task.category_id,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "due_date": due_date.isoformat() if (due_date := task.due_date(tz)) else None,
        "due_all_day": task.due_all_day,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "completed_by_id": task.completed_by_id,
        "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
        "snoozed_until": task.snoozed_until.isoformat() if task.snoozed_until else None,
        "postpone_count": task.postpone_count,
        "blocked_reason": task.blocked_reason,
        "source": task.source.value,
        "parent_task_id": task.parent_task_id,
        "recurrence_definition_id": task.recurrence_definition_id,
        "version": task.version,
    }


def event_to_dict(event: ActivityEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "seq": event.seq,
        "occurred_at": event.occurred_at.isoformat(),
        "type": event.event_type.value,
        "actor_id": event.actor_id,
        "source": event.source.value,
        "task_id": event.task_id,
        "project_id": event.project_id,
        "data": event.data,
    }


def project_to_dict(project: Project, names: Names) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status.value,
        "scope": project.visibility_scope.value,
        "owner": names.person(project.owner_id) if project.owner_id else None,
        "created_at": project.created_at.isoformat(),
        "due_at": project.due_at.isoformat() if project.due_at else None,
    }
