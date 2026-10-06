from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from family_hq.app import build_container
from family_hq.application.backup_service import (
    BackupDestination,
    BackupService,
    RetentionPolicy,
    select_to_keep,
)
from family_hq.application.project_service import NewProject
from family_hq.application.task_service import NewTask
from family_hq.domain.enums import Scope
from family_hq.errors import ConfigError, PermissionDeniedError, ValidationError

SECRET = "ZZ-BACKUP-SECRET-ZZ"


def make_backups(world, tmp_path, *destinations):
    service = world.container.backups
    assert service is not None
    return BackupService(
        db_path=service._db_path,
        destinations=list(destinations),
        retention=RetentionPolicy(keep_last=3, keep_daily_days=0, keep_weekly_weeks=0),
        clock=world.clock,
        authorizer=world.container.authz,
        person_lookup=world.people.get_person,
    )


@pytest.fixture
def populated(world):
    fam = world.tasks.create(world.admin, NewTask(title="Family chore visible"))
    world.tasks.create(world.admin, NewTask(title=f"{SECRET} work", scope=Scope.PRIVATE_WORK))
    pers = world.tasks.create(
        world.admin, NewTask(title=f"{SECRET} personal", scope=Scope.PERSONAL)
    )
    world.tasks.add_note(world.admin, pers.id, f"{SECRET} note")
    world.projects.create(
        world.admin, NewProject(name=f"{SECRET} project", scope=Scope.PRIVATE_WORK)
    )
    return fam


def test_full_backup_is_verified_and_complete(world, tmp_path, populated):
    svc = make_backups(world, tmp_path, BackupDestination("local", tmp_path / "bk"))
    [result] = svc.create(world.admin)
    assert result.path.name == "family_hq-20261007T150000Z.sqlite3"
    report = svc.verify(world.admin, result.path)
    assert report.integrity_ok
    assert report.counts["tasks"] == 3 and report.counts["people"] == 4
    assert report.migration_revision is not None
    assert SECRET.encode() in result.path.read_bytes()  # sanity: a full copy has everything
    assert not list((tmp_path / "bk").glob("*.partial")) and not list(
        (tmp_path / "bk").glob("*-wal")
    )


def test_scrubbed_backup_contains_no_private_text_at_all(world, tmp_path, populated):
    dest = BackupDestination(
        "cloud", tmp_path / "cloud", scrub_scopes=(Scope.PERSONAL, Scope.PRIVATE_WORK)
    )
    svc = make_backups(world, tmp_path, dest)
    [result] = svc.create(world.admin)
    assert result.scrubbed == (Scope.PERSONAL, Scope.PRIVATE_WORK)
    data = result.path.read_bytes()
    assert SECRET.encode() not in data  # not in tables, not in free pages
    assert b"Family chore visible" in data
    report = svc.verify(world.admin, result.path)
    assert report.integrity_ok and report.counts["tasks"] == 1 and report.counts["projects"] == 0
    conn = sqlite3.connect(result.path)
    scopes = {r[0] for r in conn.execute("SELECT visibility_scope FROM activity_events")}
    conn.close()
    assert scopes == {"FAMILY"}
    # the live database is untouched
    assert world.tasks.list_tasks(world.admin).__len__() == 3


def test_scrubbing_only_private_work_keeps_personal(world, tmp_path, populated):
    svc = make_backups(
        world, tmp_path, BackupDestination("d", tmp_path / "d", (Scope.PRIVATE_WORK,))
    )
    [result] = svc.create(world.admin)
    data = result.path.read_bytes()
    assert f"{SECRET} personal".encode() in data
    assert f"{SECRET} work".encode() not in data


def test_scrub_set_must_be_closed_upward(world, tmp_path):
    with pytest.raises(ConfigError):
        make_backups(world, tmp_path, BackupDestination("bad", tmp_path / "bad", (Scope.PERSONAL,)))


def test_adhoc_backup_to_file_and_folder_with_scrub(world, tmp_path, populated):
    svc = make_backups(world, tmp_path)
    [r1] = svc.create(
        world.admin, to=tmp_path / "bundle" / "hq.sqlite3", scrub=[Scope.PRIVATE_WORK]
    )
    assert r1.path.name == "hq.sqlite3" and f"{SECRET} work".encode() not in r1.path.read_bytes()
    [r2] = svc.create(world.admin, to=tmp_path / "folder")
    assert r2.path.parent == tmp_path / "folder" and r2.path.name.startswith("family_hq-")


def test_only_people_with_manage_backups_may_back_up_and_changes_apply_immediately(world, tmp_path):
    svc = make_backups(world, tmp_path, BackupDestination("local", tmp_path / "bk"))
    with pytest.raises(PermissionDeniedError):
        svc.create(world.adult)
    with pytest.raises(PermissionDeniedError):
        svc.create(world.kid)
    world.people.update(world.admin, "Mysti", permissions={"manage_backups": True})
    assert svc.create(world.adult)
    world.people.update(world.admin, "Mysti", active=False)
    with pytest.raises(PermissionDeniedError):
        svc.create(world.adult)


def test_retention_prunes_only_backup_files_and_keeps_newest(world, tmp_path):
    folder = tmp_path / "bk"
    folder.mkdir()
    (folder / "notes.txt").write_text("not a backup")
    (folder / "family_hq-old.sqlite3").write_text("wrong name pattern")
    svc = make_backups(world, tmp_path, BackupDestination("local", folder))
    for _ in range(5):
        world.clock.advance(hours=1)
        svc.create(world.admin)
    kept = sorted(p.name for p in folder.glob("family_hq-2*.sqlite3"))
    assert len(kept) == 3 and kept[-1].endswith("200000Z.sqlite3")
    assert (folder / "notes.txt").exists() and (folder / "family_hq-old.sqlite3").exists()


def test_select_to_keep_rules():
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    stamps = [now - timedelta(hours=h) for h in (0, 1, 2, 3)]  # four on the same day
    stamps += [now - timedelta(days=d, hours=1) for d in (1, 2, 3, 10, 40, 100)]
    policy = RetentionPolicy(keep_last=2, keep_daily_days=3, keep_weekly_weeks=2)
    keep = select_to_keep(stamps, now, policy)
    assert now in keep and now - timedelta(hours=1) in keep  # newest two
    assert now - timedelta(hours=2) not in keep  # extra same-day copies go
    for d in (1, 2, 3):  # one per day for the last 3 days
        assert now - timedelta(days=d, hours=1) in keep
    assert now - timedelta(days=10, hours=1) in keep  # weekly slot
    assert now - timedelta(days=40, hours=1) not in keep
    assert now - timedelta(days=100, hours=1) not in keep
    everything = select_to_keep(stamps, now, RetentionPolicy(keep_last=100))
    assert everything == set(stamps)


def test_run_scheduled_backs_up_only_when_due(world, tmp_path):
    svc = make_backups(world, tmp_path, BackupDestination("local", tmp_path / "bk"))
    assert len(svc.run_scheduled(24)) == 1
    world.clock.advance(hours=23)
    assert svc.run_scheduled(24) == []
    world.clock.advance(hours=2)
    assert len(svc.run_scheduled(24)) == 1


def test_verify_rejects_non_database_files(world, tmp_path):
    svc = make_backups(world, tmp_path)
    bogus = tmp_path / "bogus.sqlite3"
    bogus.write_text("this is not sqlite")
    with pytest.raises(ValidationError):
        svc.verify(world.admin, bogus)
    with pytest.raises(ValidationError):
        svc.verify(world.admin, tmp_path / "missing.sqlite3")


def test_container_builds_default_local_destination(world):
    assert world.container.backups is not None
    [dest] = world.container.backups.destinations()
    assert dest.name == "local" and dest.path == world.settings.data_dir / "backups"
    assert build_container  # imported for the composition root smoke check
    assert isinstance(dest.path, Path)
