from __future__ import annotations

import pytest

from family_hq.application.actor import Actor
from family_hq.application.project_service import NewProject
from family_hq.application.task_service import NewTask
from family_hq.domain.enums import EventType, ProjectStatus, Role, Scope, Source
from family_hq.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


def test_bootstrap_only_works_once(world):
    with pytest.raises(ConflictError):
        world.people.bootstrap_admin("Intruder")


def test_only_admins_manage_people(world):
    for actor in (world.adult, world.kid):
        with pytest.raises(PermissionDeniedError):
            world.people.add(actor, "Eve")
        with pytest.raises(PermissionDeniedError):
            world.people.update(actor, "Wyatt", role=Role.ADMIN)


def test_people_names_and_discord_ids_are_unique(world):
    world.people.update(world.admin, "Wyatt", discord_user_id="111")
    with pytest.raises(ConflictError):
        world.people.add(world.admin, "wyatt")  # case-insensitive
    with pytest.raises(ConflictError):
        world.people.add(world.admin, "Eve", discord_user_id="111")
    assert world.people.actor_for_discord("111").person.display_name == "Wyatt"
    assert world.people.actor_for_discord("111").source is Source.DISCORD
    with pytest.raises(NotFoundError):
        world.people.actor_for_discord("999")


def test_inactive_people_cannot_be_resolved_from_discord(world):
    world.people.update(world.admin, "Wyatt", discord_user_id="111")
    world.people.update(world.admin, "Wyatt", active=False)
    with pytest.raises(NotFoundError):
        world.people.actor_for_discord("111")


def test_cannot_remove_the_last_admin(world):
    with pytest.raises(ConflictError):
        world.people.update(world.admin, "Joey", role=Role.ADULT)
    with pytest.raises(ConflictError):
        world.people.update(world.admin, "Joey", active=False)
    world.people.update(world.admin, "Mysti", role=Role.ADMIN)
    world.people.update(world.admin, "Joey", role=Role.ADULT)  # fine now: Mysti is an admin


def test_find_person_by_name_id_or_prefix(world):
    assert world.people.find("mysti").id == world.adult.id
    assert world.people.find(world.adult.id).id == world.adult.id
    assert world.people.find(world.adult.id[:6]).id == world.adult.id
    with pytest.raises(NotFoundError):
        world.people.find("nobody")


def test_unknown_permission_names_are_rejected(world):
    with pytest.raises(ValidationError, match="Unknown permission"):
        world.people.update(world.admin, "Wyatt", permissions={"fly": True})


def test_demotion_takes_effect_immediately_for_a_held_actor(world):
    stale_admin_actor = world.admin
    world.people.update(world.admin, "Mysti", role=Role.ADMIN)
    world.people.update(world.adult, "Joey", role=Role.MEMBER)  # Mysti demotes Joey
    with pytest.raises(PermissionDeniedError):
        world.people.add(stale_admin_actor, "Eve")  # Joey still holds the old Actor object


def test_categories_admin_only_unique_and_deactivation_blocks_new_use(world):
    cats = world.container.categories
    with pytest.raises(PermissionDeniedError):
        cats.add(world.kid, "Hobbies")
    hobbies = cats.add(world.admin, "Hobbies")
    with pytest.raises(ConflictError):
        cats.add(world.admin, "hobbies")
    t = world.tasks.create(world.kid, NewTask(title="Paint", category_id=hobbies.id))
    cats.set_active(world.admin, "Hobbies", False)
    assert t.category_id == hobbies.id
    assert "Hobbies" not in [c.name for c in cats.list_categories()]
    assert "Hobbies" in [c.name for c in cats.list_categories(active_only=False)]
    with pytest.raises(ValidationError):
        world.tasks.create(world.kid, NewTask(title="More", category_id=hobbies.id))
    with pytest.raises(NotFoundError):
        cats.find("Nonexistent")
    assert (
        len(cats.list_categories()) == 15
    )  # the seeded defaults (minus none) plus nothing else active


def test_project_lifecycle_and_history(world):
    project = world.projects.create(world.adult, NewProject(name=" Fix  Van "))
    assert project.name == "Fix Van" and project.status is ProjectStatus.ACTIVE
    assert (
        world.projects.find(world.kid, "fix van").id == project.id
    )  # everyone sees family projects
    with pytest.raises(ConflictError):
        world.projects.create(world.adult, NewProject(name="FIX VAN"))
    renamed = world.projects.update(
        world.adult, project.id, name="Van repairs", description="brakes"
    )
    assert renamed.name == "Van repairs"
    world.projects.update(world.adult, project.id, status=ProjectStatus.ON_HOLD)
    assert [e.event_type for e in world.projects.history(world.kid, project.id)] == [
        EventType.PROJECT_CREATED,
        EventType.PROJECT_UPDATED,
        EventType.PROJECT_UPDATED,
    ]
    with pytest.raises(PermissionDeniedError):
        world.projects.update(world.kid, project.id, name="Mine now")
    world.projects.update(world.adult, project.id, status=ProjectStatus.DONE)
    assert project.id not in [p.id for p in world.projects.list_projects(world.kid)]
    assert project.id in [
        p.id for p in world.projects.list_projects(world.kid, include_closed=True)
    ]
    with pytest.raises(ConflictError):
        world.tasks.create(world.adult, NewTask(title="Late", project_id=project.id))


def test_external_refs_are_idempotent_upserts(world):
    from datetime import timedelta

    from family_hq.domain.external_refs import ExternalRef
    from family_hq.domain.ids import new_id

    task = world.tasks.create(world.admin, NewTask(title="Dentist"))
    with world.container.tasks._uow() as uow:
        ref = ExternalRef(
            new_id(),
            "task",
            task.id,
            "google_calendar",
            "deadline",
            "evt-1",
            world.clock.now(),
            content_hash="h1",
            payload={"calendar": "primary"},
        )
        uow.external_refs.upsert(ref)
        uow.external_refs.upsert(
            ExternalRef(
                new_id(),
                "task",
                task.id,
                "google_calendar",
                "deadline",
                "evt-1",
                world.clock.now() + timedelta(hours=1),
                content_hash="h2",
            )
        )
        uow.commit()
    with world.container.tasks._uow() as uow:
        refs = uow.external_refs.list_for_entity("task", task.id)
        assert len(refs) == 1 and refs[0].content_hash == "h2" and refs[0].external_id == "evt-1"
        assert uow.external_refs.get("task", task.id, "google_calendar", "deadline") is not None
        assert uow.external_refs.get("task", task.id, "google_sheets", "row") is None


def test_actor_object_is_just_a_person_and_a_source(world):
    assert Actor(world.kid.person, Source.CLI).source is Source.CLI
    assert Scope.FAMILY.value == "FAMILY"
