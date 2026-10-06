from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from family_hq.application.task_service import NewTask, TaskPatch
from family_hq.domain.enums import (
    Effort,
    EventType,
    Priority,
    Scope,
    Source,
    TaskStatus,
)
from family_hq.domain.tasks import Due, TaskQuery
from family_hq.errors import ConflictError, NotFoundError, ValidationError


def types(events):
    return [e.event_type for e in events]


def test_create_minimal_task_uses_sensible_defaults(world):
    task = world.tasks.create(world.kid, NewTask(title="  Take   out\nrecycling  "))
    assert task.title == "Take out recycling"
    assert task.status is TaskStatus.OPEN
    assert task.visibility_scope is Scope.FAMILY
    assert task.priority is Priority.NORMAL
    assert task.owner_id is None
    assert task.creator_id == world.kid.id
    assert task.source is Source.DISCORD
    assert task.created_at == world.clock.now() == task.updated_at
    assert task.version == 1
    assert len(task.id) == 36


def test_empty_and_overlong_titles_are_rejected_without_echoing_them(world):
    with pytest.raises(ValidationError):
        world.tasks.create(world.kid, NewTask(title="   "))
    secret = "x" * 500
    with pytest.raises(ValidationError) as exc:
        world.tasks.create(world.kid, NewTask(title=secret))
    assert secret not in str(exc.value)


def test_full_story_is_recorded_in_history(world):
    t = world.tasks.create(world.admin, NewTask(title="Fix bathroom sink", effort=Effort.M))
    world.clock.advance(minutes=5)
    t = world.tasks.assign(world.admin, t.id, world.kid.id)
    t = world.tasks.start(world.kid, t.id)
    t = world.tasks.block(world.kid, t.id, "need a new washer")
    t = world.tasks.unblock(world.kid, t.id)
    world.clock.advance(hours=2)
    t = world.tasks.complete(world.kid, t.id)

    assert t.status is TaskStatus.DONE
    assert t.completed_at == world.clock.now()
    assert t.completed_by_id == world.kid.id
    assert t.blocked_reason is None
    history = world.tasks.history(world.admin, t.id)
    assert types(history) == [
        EventType.TASK_CREATED,
        EventType.TASK_ASSIGNED,
        EventType.TASK_STARTED,
        EventType.TASK_BLOCKED,
        EventType.TASK_UNBLOCKED,
        EventType.TASK_COMPLETED,
    ]
    assert [e.seq for e in history] == sorted(e.seq for e in history)
    assert history[3].data["reason"] == "need a new washer"
    assert history[1].actor_id == world.admin.id
    assert history[1].data == {"from": None, "to": world.kid.id}


def test_completed_tasks_are_kept_and_listed_when_asked(world):
    t = world.tasks.create(world.admin, NewTask(title="Call mechanic"))
    world.tasks.complete(world.admin, t.id)
    assert world.tasks.list_tasks(world.admin) == []
    done = world.tasks.list_tasks(world.admin, TaskQuery(include_closed=True))
    assert [x.id for x in done] == [t.id]
    done_since = world.tasks.list_tasks(
        world.admin,
        TaskQuery(
            statuses=frozenset({TaskStatus.DONE}),
            completed_after=world.clock.now() - timedelta(hours=1),
        ),
    )
    assert len(done_since) == 1


def test_block_requires_a_reason_and_wait_does_not(world):
    t = world.tasks.create(world.admin, NewTask(title="Plumber estimate"))
    with pytest.raises(ValidationError):
        world.tasks.block(world.admin, t.id, "  ")
    waiting = world.tasks.wait(world.admin, t.id)
    assert waiting.status is TaskStatus.WAITING
    assert waiting.blocked_reason is None
    assert world.tasks.wait(world.admin, t.id, "plumber to call back").blocked_reason


def test_terminal_states_only_leave_through_reopen(world):
    t = world.tasks.create(world.admin, NewTask(title="x1"))
    world.tasks.complete(world.admin, t.id)
    for action in (world.tasks.start, world.tasks.complete, world.tasks.unblock):
        with pytest.raises(ConflictError):
            action(world.admin, t.id)
    with pytest.raises(ConflictError):
        world.tasks.cancel(world.admin, t.id)
    reopened = world.tasks.reopen(world.admin, t.id)
    assert reopened.status is TaskStatus.OPEN
    assert reopened.completed_at is None and reopened.completed_by_id is None
    with pytest.raises(ConflictError):
        world.tasks.reopen(world.admin, t.id)  # not terminal any more
    events = types(world.tasks.history(world.admin, t.id))
    assert events[-2:] == [EventType.TASK_COMPLETED, EventType.TASK_REOPENED]


def test_cancel_records_reason_and_timestamp(world):
    t = world.tasks.create(world.admin, NewTask(title="Old idea"))
    world.clock.advance(days=1)
    c = world.tasks.cancel(world.admin, t.id, "not needed")
    assert c.status is TaskStatus.CANCELLED and c.cancelled_at == world.clock.now()
    assert world.tasks.history(world.admin, t.id)[-1].data["reason"] == "not needed"


def test_start_and_complete_claim_unassigned_family_tasks(world):
    t = world.tasks.create(world.admin, NewTask(title="Clean garage"))
    done = world.tasks.complete(world.kid, t.id)
    assert done.owner_id == world.kid.id
    assert EventType.TASK_CLAIMED in types(world.tasks.history(world.kid, t.id))


def test_snooze_hides_from_actionable_views_and_counts_as_postponement(world):
    t = world.tasks.create(world.admin, NewTask(title="Renew passport"))
    until = world.clock.now() + timedelta(days=2)
    s = world.tasks.snooze(world.admin, t.id, until)
    assert s.snoozed_until == until and s.postpone_count == 1
    now = world.clock.now()
    assert world.tasks.list_tasks(world.admin, TaskQuery(hide_snoozed_as_of=now)) == []
    assert len(world.tasks.list_tasks(world.admin)) == 1
    later = until + timedelta(minutes=1)
    assert len(world.tasks.list_tasks(world.admin, TaskQuery(hide_snoozed_as_of=later))) == 1
    with pytest.raises(ValidationError):
        world.tasks.snooze(world.admin, t.id, now - timedelta(hours=1))
    with pytest.raises(ValidationError):
        world.tasks.snooze(world.admin, t.id, datetime(2026, 10, 9))  # naive


def test_update_records_old_and_new_values_but_not_description_text(world):
    t = world.tasks.create(world.admin, NewTask(title="Paint fence", description="two coats"))
    world.clock.advance(minutes=1)
    u = world.tasks.update(
        world.admin,
        t.id,
        TaskPatch(title="Paint the fence", priority=Priority.HIGH, description="three coats"),
    )
    assert u.title == "Paint the fence" and u.priority is Priority.HIGH
    assert u.updated_at > t.updated_at and u.version == t.version + 1
    event = world.tasks.history(world.admin, t.id)[-1]
    assert event.event_type is EventType.TASK_UPDATED
    assert event.data["changes"]["title"] == ["Paint fence", "Paint the fence"]
    assert event.data["changes"]["priority"] == ["NORMAL", "HIGH"]
    assert event.data["changes"]["description_changed"] is True
    assert "three coats" not in str(event.data) and "two coats" not in str(event.data)


def test_noop_update_writes_nothing(world):
    t = world.tasks.create(world.admin, NewTask(title="Same"))
    again = world.tasks.update(world.admin, t.id, TaskPatch(title="Same", priority=Priority.NORMAL))
    assert again == t
    assert len(world.tasks.history(world.admin, t.id)) == 1


def test_deadline_changes_are_events_and_later_deadlines_count_as_postponed(world):
    first = Due(datetime(2026, 10, 9, 3, 59, 59, tzinfo=UTC), all_day=True)
    t = world.tasks.create(world.admin, NewTask(title="Pay bill", due=first))
    later = Due(datetime(2026, 10, 12, 3, 59, 59, tzinfo=UTC), all_day=True)
    u = world.tasks.update(world.admin, t.id, TaskPatch(due=later))
    assert u.postpone_count == 1
    earlier = world.tasks.update(world.admin, t.id, TaskPatch(due=first))
    assert earlier.postpone_count == 1  # moving earlier is not a postponement
    cleared = world.tasks.update(world.admin, t.id, TaskPatch(due=None))
    assert cleared.due_at is None
    changes = [
        e
        for e in world.tasks.history(world.admin, t.id)
        if e.event_type is EventType.DEADLINE_CHANGED
    ]
    assert [c.data["postponed"] for c in changes] == [True, False, False]
    assert changes[0].data["to"] == later.at.isoformat()


def test_overdue_and_due_date_helpers(world):
    due = Due(datetime(2026, 10, 7, 3, 59, 59, tzinfo=UTC), all_day=True)  # Oct 6 local
    t = world.tasks.create(world.admin, NewTask(title="Late", due=due))
    assert t.is_overdue(world.clock.now())
    assert t.due_date(world.settings.tz).isoformat() == "2026-10-06"
    overdue = world.tasks.list_tasks(world.admin, TaskQuery(overdue_as_of=world.clock.now()))
    assert [x.id for x in overdue] == [t.id]
    world.tasks.complete(world.admin, t.id)
    assert world.tasks.list_tasks(world.admin, TaskQuery(overdue_as_of=world.clock.now())) == []


def test_notes_are_history_not_state(world):
    t = world.tasks.create(world.kid, NewTask(title="Walk dog"))
    world.tasks.add_note(world.adult, t.id, "he already did the morning one")
    with pytest.raises(ValidationError):
        world.tasks.add_note(world.adult, t.id, "   ")
    assert world.tasks.get(world.adult, t.id).version == t.version  # row untouched
    assert types(world.tasks.history(world.kid, t.id))[-1] is EventType.TASK_NOTE_ADDED


def test_triage_statuses(world):
    t = world.tasks.create(world.admin, NewTask(title="Maybe", status=TaskStatus.INBOX))
    assert t.status is TaskStatus.INBOX
    assert (
        world.tasks.set_status(world.admin, t.id, TaskStatus.PLANNED).status is TaskStatus.PLANNED
    )
    with pytest.raises(ValidationError):
        world.tasks.set_status(world.admin, t.id, TaskStatus.DONE)
    with pytest.raises(ValidationError):
        world.tasks.create(world.admin, NewTask(title="bad", status=TaskStatus.DONE))


def test_id_prefix_resolution(world):
    t = world.tasks.create(world.admin, NewTask(title="Prefix me"))
    assert world.tasks.get(world.admin, t.id[:8]).id == t.id
    assert world.tasks.get(world.admin, t.id.upper()).id == t.id
    for bad in ("abc", "zzzzzzzz", ""):
        with pytest.raises(NotFoundError):
            world.tasks.get(world.admin, bad)


def test_stale_write_is_rejected(world):
    t = world.tasks.create(world.admin, NewTask(title="Race"))
    # Simulate a second client holding the old version of the row.
    with world.container.tasks._uow() as uow:
        from dataclasses import replace

        uow.tasks.update(replace(t, title="Winner"))
        uow.commit()
        with pytest.raises(ConflictError):
            uow.tasks.update(replace(t, title="Loser"))  # still version 1


def test_list_filters_and_ordering(world):
    low = world.tasks.create(world.admin, NewTask(title="low", priority=Priority.LOW))
    urgent = world.tasks.create(world.admin, NewTask(title="urgent", priority=Priority.URGENT))
    soon = world.tasks.create(
        world.admin,
        NewTask(title="soon", due=Due(datetime(2026, 10, 9, 3, 59, 59, tzinfo=UTC), True)),
    )
    later = world.tasks.create(
        world.admin,
        NewTask(title="later", due=Due(datetime(2026, 10, 20, 3, 59, 59, tzinfo=UTC), True)),
    )
    order = [t.id for t in world.tasks.list_tasks(world.admin)]
    assert order == [urgent.id, soon.id, later.id, low.id]
    assert [
        t.id
        for t in world.tasks.list_tasks(
            world.admin, TaskQuery(priorities=frozenset({Priority.LOW}))
        )
    ] == [low.id]
    assert [t.id for t in world.tasks.list_tasks(world.admin, TaskQuery(text="SOO"))] == [soon.id]
    assert (
        world.tasks.list_tasks(world.admin, TaskQuery(text="100%")) == []
    )  # LIKE wildcards are escaped
    due_by = datetime(2026, 10, 10, tzinfo=UTC)
    assert [t.id for t in world.tasks.list_tasks(world.admin, TaskQuery(due_before=due_by))] == [
        soon.id
    ]
    assert len(world.tasks.list_tasks(world.admin, TaskQuery(limit=2))) == 2


def test_inactive_person_cannot_act(world):
    t = world.tasks.create(world.admin, NewTask(title="x"))
    world.people.update(world.admin, "Wyatt", active=False)
    with pytest.raises(Exception, match="inactive"):
        world.tasks.get(world.kid, t.id)
