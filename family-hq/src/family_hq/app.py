"""Composition root: the only module that wires settings, database and services together."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Engine

from family_hq.application.authz import Authorizer
from family_hq.application.backup_service import (
    BackupDestination,
    BackupService,
    RetentionPolicy,
)
from family_hq.application.category_service import CategoryService
from family_hq.application.people_service import PeopleService
from family_hq.application.project_service import ProjectService
from family_hq.application.task_service import TaskService
from family_hq.clock import Clock, SystemClock
from family_hq.config import Settings
from family_hq.db.engine import make_engine, make_session_factory, sqlite_file
from family_hq.db.migrate import upgrade_to_head
from family_hq.domain.enums import Scope
from family_hq.repositories.sqlalchemy import SqlAlchemyUnitOfWork

log = logging.getLogger(__name__)

_SYNC_FOLDER_HINTS = ("onedrive", "dropbox", "google drive", "googledrive", "icloud", "box sync")


@dataclass
class Container:
    settings: Settings
    clock: Clock
    engine: Engine
    authz: Authorizer
    people: PeopleService
    categories: CategoryService
    projects: ProjectService
    tasks: TaskService
    backups: BackupService | None  # None when the database is not a local SQLite file

    def close(self) -> None:
        self.engine.dispose()


def build_container(settings: Settings, clock: Clock | None = None) -> Container:
    clock = clock or SystemClock()
    url = settings.database_url
    engine = make_engine(url)
    session_factory = make_session_factory(engine)

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    authz = Authorizer()
    people = PeopleService(uow_factory, clock, authz)
    db_file = sqlite_file(url)
    backups = None
    if db_file is not None:
        backups = BackupService(
            db_path=db_file,
            destinations=[
                BackupDestination(d.name, d.path, tuple(Scope.parse(s) for s in d.scrub_scopes))
                for d in settings.backup_destinations
            ],
            retention=RetentionPolicy(
                settings.backup.retention.keep_last,
                settings.backup.retention.keep_daily_days,
                settings.backup.retention.keep_weekly_weeks,
            ),
            clock=clock,
            authorizer=authz,
            person_lookup=people.get_person,
        )
    return Container(
        settings=settings,
        clock=clock,
        engine=engine,
        authz=authz,
        people=people,
        categories=CategoryService(uow_factory, clock, authz),
        projects=ProjectService(uow_factory, clock, authz),
        tasks=TaskService(uow_factory, clock, authz),
        backups=backups,
    )


def startup(settings: Settings, clock: Clock | None = None) -> Container:
    """Startup sequence: data dir, migrations, seed categories. Safe to call repeatedly."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    warn_if_synced_folder(settings.database_url)
    upgrade_to_head(settings.database_url)
    container = build_container(settings, clock)
    seeded = container.categories.seed_if_empty(settings.categories.initial)
    if seeded:
        log.info("categories_seeded", extra={"count": seeded})
    return container


def warn_if_synced_folder(url: str) -> str | None:
    """SQLite and cloud sync clients corrupt each other; flag it loudly (docs/deployment.md)."""
    db_file = sqlite_file(url)
    if db_file is None:
        return None
    for part in db_file.resolve().parts:
        if any(hint in part.lower() for hint in _SYNC_FOLDER_HINTS):
            message = (
                f"The database is inside a cloud-synced folder ('{part}'). Sync clients can "
                "corrupt SQLite databases and would upload private tasks. Move it."
            )
            log.warning("database_in_synced_folder", extra={"folder": part})
            return message
    return None


# ---- long-running service skeleton (Discord and recurrence plug in here in later phases) -------


@dataclass
class Job:
    name: str
    interval_seconds: float
    func: Callable[[], object]


def build_jobs(container: Container) -> list[Job]:
    jobs: list[Job] = []
    settings = container.settings
    if settings.backup.enabled and container.backups is not None:
        backups = container.backups
        interval = settings.backup.interval_hours
        # Check often, back up only when due: a sleeping laptop catches up on wake.
        jobs.append(
            Job("backup", min(interval * 3600, 900), lambda: backups.run_scheduled(interval))
        )
    return jobs


async def _run_job(job: Job, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(job.func)
        except Exception:  # a failing job must never stop the service
            log.exception("job_failed", extra={"job": job.name})
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=job.interval_seconds)


async def run_forever(container: Container, stop: asyncio.Event | None = None) -> None:
    stop = stop or asyncio.Event()
    jobs = build_jobs(container)
    log.info("service_started", extra={"jobs": [j.name for j in jobs]})
    await asyncio.gather(*(_run_job(job, stop) for job in jobs), stop.wait())
    log.info("service_stopped")


def database_description(settings: Settings) -> str:
    from sqlalchemy.engine import make_url

    return make_url(settings.database_url).render_as_string(hide_password=True)


__all__ = ["Container", "build_container", "database_description", "run_forever", "startup"]
