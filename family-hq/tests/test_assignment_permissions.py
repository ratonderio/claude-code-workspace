from __future__ import annotations

import pytest

from family_hq.application.task_service import NewTask, TaskPatch
from family_hq.domain.enums import EventType, Priority
from family_hq.errors import ConflictError, PermissionDeniedError, ValidationError


def test_member_can_create_for_self_but_not_for_others(world):
    ok = world.tasks.create(world.kid, NewTask(title="mine", owner_id=world.kid.id))
    assert ok.owner_id == world.kid.id
    with pytest.raises(PermissionDeniedError):
        world.tasks.create(world.kid, NewTask(title="not yours", owner_id=world.kid2.id))


def test_adult_and_admin_can_assign_anyone(world):
    t = world.tasks.create(world.adult, NewTask(title="Chore"))
    assert world.tasks.assign(world.adult, t.id, world.kid.id).owner_id == world.kid.id
    assert world.tasks.assign(world.admin, t.id, world.kid2.id).owner_id == world.kid2.id
    history = world.tasks.history(world.admin, t.id)
    assert history[-1].data == {"from": world.kid.id, "to": world.kid2.id}


def test_member_cannot_assign_others_or_steal_owned_tasks(world):
    t = world.tasks.create(world.admin, NewTask(title="Dishes", owner_id=world.kid2.id))
    with pytest.raises(PermissionDeniedError):
        world.tasks.assign(world.kid, t.id, world.kid.id)  # steal
    with pytest.raises(PermissionDeniedError):
        world.tasks.assign(world.kid, t.id, world.adult.id)
    with pytest.raises(ConflictError):
        world.tasks.claim(world.kid, t.id)


def test_claim_is_first_come_first_served(world):
    t = world.tasks.create(world.adult, NewTask(title="Clean garage"))
    claimed = world.tasks.claim(world.kid, t.id)
    assert claimed.owner_id == world.kid.id
    with pytest.raises(ConflictError):
        world.tasks.claim(world.kid2, t.id)
    assert world.tasks.history(world.kid, t.id)[-1].event_type is EventType.TASK_CLAIMED


def test_release_returns_task_to_pool(world):
    t = world.tasks.create(world.admin, NewTask(title="Mow", owner_id=world.kid.id))
    released = world.tasks.assign(world.kid, t.id, None)  # members may release their own
    assert released.owner_id is None
    assert world.tasks.history(world.kid, t.id)[-1].event_type is EventType.TASK_UNASSIGNED
    with pytest.raises(ConflictError):
        world.tasks.assign(world.admin, t.id, None)  # already unassigned


def test_cannot_assign_to_inactive_or_unknown_people_or_closed_tasks(world):
    t = world.tasks.create(world.admin, NewTask(title="x"))
    world.people.update(world.admin, "Ada", active=False)
    with pytest.raises(ValidationError):
        world.tasks.assign(world.admin, t.id, world.kid2.id)
    with pytest.raises(ValidationError):
        world.tasks.assign(world.admin, t.id, "not-a-person")
    world.tasks.complete(world.admin, t.id)
    with pytest.raises(ConflictError):
        world.tasks.assign(world.admin, t.id, world.kid.id)


def test_member_edit_rights(world):
    theirs = world.tasks.create(world.kid, NewTask(title="Wyatt's own"))
    others = world.tasks.create(world.adult, NewTask(title="Mom's task", owner_id=world.adult.id))
    world.tasks.update(world.kid, theirs.id, TaskPatch(priority=Priority.HIGH))
    with pytest.raises(PermissionDeniedError):
        world.tasks.update(world.kid, others.id, TaskPatch(priority=Priority.HIGH))
    with pytest.raises(PermissionDeniedError):
        world.tasks.cancel(world.kid, others.id)
    # but adults can edit any family task
    assert world.tasks.update(world.adult, theirs.id, TaskPatch(title="Renamed")).title == "Renamed"


def test_member_can_work_unassigned_but_not_other_peoples_tasks(world):
    free = world.tasks.create(world.adult, NewTask(title="Free task"))
    owned = world.tasks.create(world.adult, NewTask(title="Owned", owner_id=world.adult.id))
    world.tasks.start(world.kid, free.id)
    for action in (world.tasks.start, world.tasks.complete):
        with pytest.raises(PermissionDeniedError):
            action(world.kid, owned.id)
    with pytest.raises(PermissionDeniedError):
        world.tasks.block(world.kid, owned.id, "because")
    # an adult may finish a child's chore; ownership stays, completion is attributed
    done = world.tasks.complete(world.adult, free.id)
    assert done.owner_id == world.kid.id and done.completed_by_id == world.adult.id


def test_anyone_can_comment_on_family_tasks(world):
    t = world.tasks.create(world.adult, NewTask(title="Discuss me", owner_id=world.adult.id))
    world.tasks.add_note(world.kid, t.id, "can I help?")
    notes = [
        e for e in world.tasks.history(world.kid, t.id) if e.event_type is EventType.TASK_NOTE_ADDED
    ]
    assert notes[0].actor_id == world.kid.id


def test_per_person_permission_override(world):
    world.people.update(world.admin, "Wyatt", permissions={"assign_others": True})
    t = world.tasks.create(world.kid, NewTask(title="Delegating", owner_id=world.kid2.id))
    assert t.owner_id == world.kid2.id
    world.people.update(world.admin, "Mysti", permissions={"assign_others": False})
    with pytest.raises(PermissionDeniedError):
        world.tasks.create(world.adult, NewTask(title="No delegating", owner_id=world.kid.id))
