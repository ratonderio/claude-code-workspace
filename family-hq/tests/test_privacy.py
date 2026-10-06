"""Titles, descriptions, notes and project names must never reach logs or error messages."""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest

from family_hq.application.project_service import NewProject
from family_hq.application.task_service import NewTask, TaskPatch
from family_hq.domain.enums import Scope, TaskStatus
from family_hq.errors import FamilyHQError

TITLE = "AA-LOGGED-TITLE-AA"
DESC = "BB-LOGGED-DESCRIPTION-BB"
NOTE = "CC-LOGGED-NOTE-CC"
REASON = "DD-LOGGED-REASON-DD"
PROJECT = "EE-LOGGED-PROJECT-EE"
NEEDLES = (TITLE, DESC, NOTE, REASON, PROJECT, "AA-", "BB-", "CC-", "DD-", "EE-")


def _flatten(record: logging.LogRecord) -> str:
    return " ".join([record.getMessage(), str(record.args), str(record.__dict__)])


@pytest.mark.parametrize("scope", list(Scope))
def test_logs_and_errors_never_contain_user_content(world, caplog, scope):
    caplog.set_level(logging.DEBUG)
    errors: list[str] = []

    def attempt(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FamilyHQError as exc:
            errors.append(str(exc))
            return None

    project = world.projects.create(world.admin, NewProject(name=PROJECT, scope=scope))
    task = world.tasks.create(
        world.admin,
        NewTask(title=TITLE, description=DESC, scope=scope, project_id=project.id),
    )
    world.tasks.add_note(world.admin, task.id, NOTE)
    world.tasks.update(
        world.admin, task.id, TaskPatch(title=TITLE + " renamed", description=DESC + "2")
    )
    world.tasks.block(world.admin, task.id, REASON)
    world.tasks.unblock(world.admin, task.id)
    world.tasks.snooze(world.admin, task.id, world.clock.now() + timedelta(days=1))
    world.tasks.complete(world.admin, task.id)

    # failure paths, including strangers poking at the same objects
    for stranger in (world.kid, world.kid2):
        attempt(world.tasks.get, stranger, task.id)
        attempt(world.tasks.update, stranger, task.id, TaskPatch(title=NOTE))
        attempt(world.tasks.add_note, stranger, task.id, NOTE)
        attempt(world.tasks.assign, stranger, task.id, stranger.id)
        attempt(world.projects.find, stranger, PROJECT)
        attempt(world.projects.update, stranger, project.id, name=PROJECT + "x")
    attempt(world.tasks.start, world.admin, task.id)  # invalid transition
    attempt(world.tasks.create, world.admin, NewTask(title=TITLE * 50))
    attempt(world.tasks.create, world.admin, NewTask(title=TITLE, project_id="nope"))
    attempt(world.tasks.set_status, world.admin, task.id, TaskStatus.DONE)

    assert errors, "the scenario should have produced errors to inspect"
    for needle in NEEDLES:
        assert not any(needle in e for e in errors), f"{needle!r} leaked into an error message"
    for record in caplog.records:
        flat = _flatten(record)
        for needle in NEEDLES:
            assert needle not in flat, f"{needle!r} leaked into a log record: {record.getMessage()}"
    assert any(r.getMessage() == "task_created" for r in caplog.records)  # logging is on
