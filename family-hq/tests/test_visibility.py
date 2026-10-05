"""Authorization and visibility: the tests that matter most.

Goal: nothing about a task the actor may not see (existence, title, history) is observable
through any service method, list, search, history, activity feed or error message.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from itertools import product

import pytest

from family_hq.application.project_service import NewProject
from family_hq.application.task_service import NewTask, TaskPatch
from family_hq.domain.enums import EventType, Scope, Sink, TaskStatus
from family_hq.domain.ids import new_id
from family_hq.domain.tasks import Task, TaskQuery
from family_hq.domain.visibility import SinkPolicy, can_view
from family_hq.errors import (
    ConfigError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)

SECRET = "ZZ-SECRET-TITLE-ZZ"
SECRET_NOTE = "ZZ-SECRET-NOTE-ZZ"


# ---- parity between the Python rule and its SQL twin ---------------------------------------------


def test_sql_visibility_matches_python_rule_for_every_combination(world):
    people = [world.admin.person, world.adult.person, world.kid.person, world.kid2.person]
    now = world.clock.now()
    rows = []
    with world.container.tasks._uow() as uow:
        for scope, owner in product(Scope, [None, *[p.id for p in people]]):
            task = Task(
                id=new_id(),
                title=f"{scope.value}-{owner}",
                status=TaskStatus.OPEN,
                visibility_scope=scope,
                priority=__import__(
                    "family_hq.domain.enums", fromlist=["Priority"]
                ).Priority.NORMAL,
                source=__import__("family_hq.domain.enums", fromlist=["Source"]).Source.SYSTEM,
                created_at=now,
                updated_at=now,
                owner_id=owner,
            )
            uow.tasks.add(task)
            rows.append(task)
        uow.commit()
    inactive = replace(world.kid.person, active=False)
    with world.container.tasks._uow() as uow:
        for viewer in [*people, inactive]:
            expected = {t.id for t in rows if can_view(viewer, t.visibility_scope, t.owner_id)}
            actual = {t.id for t in uow.tasks.list(TaskQuery(include_closed=True), viewer)}
            assert actual == expected, viewer.display_name
            for t in rows:
                got = uow.tasks.get_visible(t.id, viewer)
                assert (got is not None) == (t.id in expected)


# ---- the leak matrix -----------------------------------------------------------------------------


@pytest.fixture
def secrets(world):
    """Private tasks belonging to the admin and to the adult (each with history), plus projects."""
    created = {}
    for name, actor in (("admin", world.admin), ("adult", world.adult)):
        for scope in (Scope.PERSONAL, Scope.PRIVATE_WORK):
            task = world.tasks.create(
                actor, NewTask(title=f"{SECRET} {name} {scope.value}", scope=scope)
            )
            world.tasks.add_note(actor, task.id, SECRET_NOTE)
            world.tasks.start(actor, task.id)
            created[(name, scope)] = task
    return created


ACTIONS = {
    "get": lambda w, a, t: w.tasks.get(a, t),
    "history": lambda w, a, t: w.tasks.history(a, t),
    "update": lambda w, a, t: w.tasks.update(a, t, TaskPatch(title="hijack")),
    "assign": lambda w, a, t: w.tasks.assign(a, t, a.id),
    "claim": lambda w, a, t: w.tasks.claim(a, t),
    "start": lambda w, a, t: w.tasks.start(a, t),
    "complete": lambda w, a, t: w.tasks.complete(a, t),
    "wait": lambda w, a, t: w.tasks.wait(a, t, "r"),
    "block": lambda w, a, t: w.tasks.block(a, t, "r"),
    "unblock": lambda w, a, t: w.tasks.unblock(a, t),
    "snooze": lambda w, a, t: w.tasks.snooze(a, t, w.clock.now() + timedelta(days=1)),
    "set_status": lambda w, a, t: w.tasks.set_status(a, t, TaskStatus.PLANNED),
    "cancel": lambda w, a, t: w.tasks.cancel(a, t),
    "reopen": lambda w, a, t: w.tasks.reopen(a, t),
    "note": lambda w, a, t: w.tasks.add_note(a, t, "intruder"),
    "subtask": lambda w, a, t: w.tasks.create(a, NewTask(title="child", parent_task_id=t)),
}


@pytest.mark.parametrize("action", sorted(ACTIONS))
@pytest.mark.parametrize("scope", [Scope.PERSONAL, Scope.PRIVATE_WORK])
@pytest.mark.parametrize("owner", ["admin", "adult"])
def test_no_service_method_reveals_or_touches_someone_elses_private_task(
    world, secrets, action, scope, owner
):
    task = secrets[(owner, scope)]
    strangers = [
        a
        for a in (world.admin, world.adult, world.kid, world.kid2)
        if a.id != secrets[(owner, scope)].owner_id
    ]
    assert len(strangers) == 3  # including the other adult/admin: roles never override ownership
    for stranger in strangers:
        for ref in (task.id, task.id[:8]):
            with pytest.raises(NotFoundError) as exc:
                ACTIONS[action](world, stranger, ref)
            assert SECRET not in str(exc.value)
    unchanged = world.tasks.get(world.container.people and secrets_owner(world, owner), task.id)
    assert unchanged.version == task.version + 1  # only the owner's own start() touched it


def secrets_owner(world, owner):
    return world.admin if owner == "admin" else world.adult


def test_lists_search_activity_and_overdue_never_include_private_tasks(world, secrets):
    for stranger in (world.kid, world.kid2):
        everything = world.tasks.list_tasks(stranger, TaskQuery(include_closed=True))
        assert everything == []
        assert world.tasks.list_tasks(stranger, TaskQuery(text=SECRET, include_closed=True)) == []
        assert world.tasks.list_tasks(stranger, TaskQuery(text="ZZ", include_closed=True)) == []
        assert (
            world.tasks.list_tasks(
                stranger, TaskQuery(owner_id=world.admin.id, include_closed=True)
            )
            == []
        )
        assert world.tasks.recent_activity(stranger) == []
    # a third party adult sees only their own
    mine = world.tasks.list_tasks(world.adult, TaskQuery(include_closed=True))
    assert {t.title for t in mine} == {f"{SECRET} adult PERSONAL", f"{SECRET} adult PRIVATE_WORK"}
    for event in world.tasks.recent_activity(world.adult, limit=500):
        assert event.actor_id == world.adult.id or event.visibility_scope is Scope.FAMILY


def test_owner_sees_everything_about_their_own_private_tasks(world, secrets):
    task = secrets[("admin", Scope.PRIVATE_WORK)]
    history = world.tasks.history(world.admin, task.id)
    assert [e.event_type for e in history] == [
        EventType.TASK_CREATED,
        EventType.TASK_NOTE_ADDED,
        EventType.TASK_STARTED,
    ]
    assert all(e.visibility_scope is Scope.PRIVATE_WORK for e in history)
    assert all(e.scope_owner_id == world.admin.id for e in history)


# ---- creation rules for private scopes -----------------------------------------------------------


def test_member_cannot_use_private_work_scope_but_can_use_personal(world):
    with pytest.raises(PermissionDeniedError):
        world.tasks.create(world.kid, NewTask(title="x", scope=Scope.PRIVATE_WORK))
    t = world.tasks.create(world.kid, NewTask(title="my diary chore", scope=Scope.PERSONAL))
    assert t.owner_id == world.kid.id  # private tasks default to the creator
    assert world.tasks.list_tasks(world.admin, TaskQuery(text="diary")) == []


def test_private_tasks_cannot_be_created_for_or_assigned_to_other_people(world):
    with pytest.raises(PermissionDeniedError):
        world.tasks.create(
            world.admin, NewTask(title="x", scope=Scope.PERSONAL, owner_id=world.kid.id)
        )
    t = world.tasks.create(world.admin, NewTask(title="mine", scope=Scope.PRIVATE_WORK))
    with pytest.raises(PermissionDeniedError):
        world.tasks.assign(world.admin, t.id, world.kid.id)
    with pytest.raises(PermissionDeniedError):
        world.tasks.assign(world.admin, t.id, None)
    with pytest.raises(ConflictError):
        world.tasks.claim(world.admin, t.id)


# ---- scope changes and history -------------------------------------------------------------------


def test_making_a_family_task_private_hides_it_and_its_history_from_the_family(world):
    t = world.tasks.create(
        world.adult, NewTask(title="Plan surprise party", owner_id=world.adult.id)
    )
    assert len(world.tasks.recent_activity(world.kid)) == 1  # visible while family
    world.tasks.update(world.adult, t.id, TaskPatch(scope=Scope.PERSONAL))
    with pytest.raises(NotFoundError):
        world.tasks.get(world.kid, t.id)
    with pytest.raises(NotFoundError):
        world.tasks.history(world.kid, t.id)
    assert world.tasks.recent_activity(world.kid) == []  # old CREATED event hidden too
    assert len(world.tasks.history(world.adult, t.id)) == 2  # owner still sees everything


def test_private_era_history_stays_private_after_the_task_becomes_family_again(world):
    t = world.tasks.create(world.adult, NewTask(title="Gift idea", owner_id=world.adult.id))
    world.tasks.update(world.adult, t.id, TaskPatch(scope=Scope.PRIVATE_WORK))
    world.tasks.add_note(world.adult, t.id, SECRET_NOTE)
    world.tasks.update(world.adult, t.id, TaskPatch(scope=Scope.FAMILY))

    visible_to_kid = world.tasks.history(world.kid, t.id)
    assert [e.event_type for e in visible_to_kid] == [EventType.TASK_CREATED]  # family-era only
    assert SECRET_NOTE not in str([e.data for e in visible_to_kid])
    owner_view = world.tasks.history(world.adult, t.id)
    assert EventType.TASK_NOTE_ADDED in [e.event_type for e in owner_view]
    assert [e.event_type for e in owner_view].count(EventType.SCOPE_CHANGED) == 2
    feed = world.tasks.recent_activity(world.kid)
    assert all(SECRET_NOTE not in str(e.data) for e in feed)


def test_unassigned_family_task_made_private_is_claimed_by_the_changer(world):
    t = world.tasks.create(world.admin, NewTask(title="Look into insurance"))
    changed = world.tasks.update(world.admin, t.id, TaskPatch(scope=Scope.PERSONAL))
    assert changed.owner_id == world.admin.id and changed.visibility_scope is Scope.PERSONAL


def test_cannot_make_someone_elses_family_task_private(world):
    t = world.tasks.create(world.adult, NewTask(title="Kid's chore", owner_id=world.kid.id))
    with pytest.raises(PermissionDeniedError):
        world.tasks.update(world.adult, t.id, TaskPatch(scope=Scope.PERSONAL))
    with pytest.raises(PermissionDeniedError):
        world.tasks.update(world.kid, t.id, TaskPatch(scope=Scope.PRIVATE_WORK))  # no scope perm


def test_only_the_owner_can_change_scope_of_a_private_task(world, secrets):
    t = secrets[("adult", Scope.PERSONAL)]
    with pytest.raises(NotFoundError):
        world.tasks.update(world.admin, t.id, TaskPatch(scope=Scope.FAMILY))
    moved = world.tasks.update(world.adult, t.id, TaskPatch(scope=Scope.FAMILY))
    assert moved.visibility_scope is Scope.FAMILY
    assert world.tasks.get(world.kid, t.id).id == t.id


# ---- containment rule ----------------------------------------------------------------------------


def test_family_task_cannot_live_in_a_private_project(world):
    pp = world.projects.create(world.admin, NewProject(name="Job hunt", scope=Scope.PRIVATE_WORK))
    with pytest.raises(ConflictError):
        world.tasks.create(world.admin, NewTask(title="x", project_id=pp.id))
    ok = world.tasks.create(
        world.admin, NewTask(title="y", project_id=pp.id, scope=Scope.PRIVATE_WORK)
    )
    assert ok.project_id == pp.id
    with pytest.raises(ConflictError):
        world.tasks.update(world.admin, ok.id, TaskPatch(scope=Scope.FAMILY))  # would leak project


def test_private_task_may_live_in_a_family_project(world):
    fp = world.projects.create(world.adult, NewProject(name="Vacation"))
    t = world.tasks.create(
        world.adult, NewTask(title="Book flights", scope=Scope.PERSONAL, project_id=fp.id)
    )
    assert world.tasks.get(world.adult, t.id).project_id == fp.id
    with pytest.raises(NotFoundError):
        world.tasks.get(world.kid, t.id)
    world.tasks.update(world.adult, t.id, TaskPatch(scope=Scope.FAMILY))  # loosening is fine here


def test_subtasks_cannot_be_less_private_than_parent_and_scope_change_checks_children(world):
    parent = world.tasks.create(world.admin, NewTask(title="Parent", scope=Scope.PERSONAL))
    with pytest.raises(ConflictError):
        world.tasks.create(
            world.admin, NewTask(title="c", parent_task_id=parent.id)
        )  # FAMILY child
    fam_parent = world.tasks.create(world.admin, NewTask(title="FP"))
    world.tasks.create(world.admin, NewTask(title="child", parent_task_id=fam_parent.id))
    with pytest.raises(ConflictError):
        world.tasks.update(world.admin, fam_parent.id, TaskPatch(scope=Scope.PERSONAL))


def test_invisible_project_cannot_be_used(world):
    pp = world.projects.create(world.admin, NewProject(name="Secret project", scope=Scope.PERSONAL))
    with pytest.raises(NotFoundError):
        world.tasks.create(world.kid, NewTask(title="x", project_id=pp.id))
    with pytest.raises(NotFoundError):
        world.tasks.create(world.adult, NewTask(title="x", project_id=pp.id))


# ---- projects ------------------------------------------------------------------------------------


def test_private_projects_are_invisible_and_names_do_not_collide_across_scopes(world):
    p = world.projects.create(world.adult, NewProject(name="Surprise", scope=Scope.PERSONAL))
    for stranger in (world.admin, world.kid):
        assert p.id not in [
            x.id for x in world.projects.list_projects(stranger, include_closed=True)
        ]
        for ref in (p.id, p.id[:8], "Surprise"):
            if stranger is world.kid and ref == "Surprise":
                continue
            with pytest.raises(NotFoundError):
                world.projects.find(stranger, ref)
        with pytest.raises(NotFoundError):
            world.projects.history(stranger, p.id)
    # creating a family project with the same name does not reveal the private one
    fam = world.projects.create(world.admin, NewProject(name="Surprise"))
    assert world.projects.find(world.admin, "surprise").id == fam.id
    # but the adult can now see two with the same name and must disambiguate
    with pytest.raises(Exception, match="Several"):
        world.projects.find(world.adult, "Surprise")
    assert world.projects.find(world.adult, p.id).id == p.id


def test_only_owner_edits_private_project_and_members_cannot_create_family_projects(world):
    p = world.projects.create(world.adult, NewProject(name="Mine", scope=Scope.PERSONAL))
    with pytest.raises(NotFoundError):
        world.projects.update(world.admin, p.id, name="Hijack")
    with pytest.raises(PermissionDeniedError):
        world.projects.create(world.kid, NewProject(name="Kid project"))
    assert world.projects.create(world.kid, NewProject(name="Kid private", scope=Scope.PERSONAL))


# ---- sink policy ---------------------------------------------------------------------------------


def test_default_sink_policy_matches_the_documented_matrix():
    policy = SinkPolicy.default()
    assert all(policy.allows(Scope.FAMILY, s) for s in Sink)
    assert policy.allows(Scope.PERSONAL, Sink.DISCORD_EPHEMERAL)
    assert policy.allows(Scope.PERSONAL, Sink.OBSIDIAN)
    assert not policy.allows(Scope.PERSONAL, Sink.DISCORD_CHANNEL)
    assert not policy.allows(Scope.PERSONAL, Sink.GOOGLE_PRIVATE)  # opt-in
    assert not policy.allows(Scope.PERSONAL, Sink.AI)
    assert policy.allows(Scope.PRIVATE_WORK, Sink.OBSIDIAN)
    for sink in Sink:
        if sink is not Sink.OBSIDIAN:
            assert not policy.allows(Scope.PRIVATE_WORK, sink)


def test_family_audience_sinks_can_never_carry_private_scopes():
    for scope in ("PERSONAL", "PRIVATE_WORK"):
        for sink in ("DISCORD_CHANNEL", "GOOGLE_FAMILY"):
            with pytest.raises(ConfigError):
                SinkPolicy.from_lists({scope: [sink]})


def test_sink_policy_is_configurable_where_allowed():
    policy = SinkPolicy.from_lists(
        {"PERSONAL": ["GOOGLE_PRIVATE", "OBSIDIAN"], "PRIVATE_WORK": ["AI"]}
    )
    assert policy.allows(Scope.PERSONAL, Sink.GOOGLE_PRIVATE)
    assert not policy.allows(Scope.PERSONAL, Sink.DISCORD_EPHEMERAL)
    assert policy.allows(Scope.PRIVATE_WORK, Sink.AI)  # explicit opt-in is honored
    with pytest.raises(ConfigError):
        SinkPolicy.from_lists({"NOPE": ["AI"]})
    with pytest.raises(ConfigError):
        SinkPolicy.from_lists({"FAMILY": ["NOPE"]})


def test_inactive_people_see_nothing():
    from datetime import UTC

    from family_hq.domain.enums import Role
    from family_hq.domain.people import Person

    now = datetime(2026, 1, 1, tzinfo=UTC)
    ghost = Person("p1", "Ghost", Role.ADMIN, False, now, now)
    assert not can_view(ghost, Scope.FAMILY, None)
    assert not can_view(ghost, Scope.PERSONAL, "p1")
