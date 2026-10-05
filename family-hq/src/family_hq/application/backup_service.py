"""SQLite backups: online snapshot, integrity check, optional scrubbing, retention.

* Uses SQLite's online backup API, so it is safe while the service is running.
* A destination may scrub scopes (e.g. PRIVATE_WORK). Scrubbed copies have those rows deleted and
  are VACUUMed so the deleted text does not survive in free pages (decision D15).
* Pruning only ever deletes files that match the backup naming pattern.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from family_hq.application.actor import Actor
from family_hq.application.authz import Authorizer
from family_hq.clock import Clock
from family_hq.domain.dates import week_start
from family_hq.domain.enums import Scope
from family_hq.domain.people import Permission, Person
from family_hq.domain.visibility import SCOPE_RANK
from family_hq.errors import ConfigError, PermissionDeniedError, ValidationError

log = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^family_hq-(\d{8}T\d{6}Z)\.sqlite3$")
_STAMP_FMT = "%Y%m%dT%H%M%SZ"
_COUNT_TABLES = ("people", "categories", "projects", "tasks", "activity_events")


@dataclass(frozen=True)
class RetentionPolicy:
    keep_last: int = 14
    keep_daily_days: int = 30
    keep_weekly_weeks: int = 12


@dataclass(frozen=True)
class BackupDestination:
    name: str
    path: Path
    scrub_scopes: tuple[Scope, ...] = ()


@dataclass(frozen=True)
class BackupFile:
    path: Path
    created_at: datetime
    size_bytes: int


@dataclass(frozen=True)
class BackupResult:
    destination: str
    path: Path
    size_bytes: int
    scrubbed: tuple[Scope, ...] = ()
    pruned: tuple[Path, ...] = field(default=())


@dataclass(frozen=True)
class VerifyReport:
    path: Path
    integrity_ok: bool
    counts: dict[str, int]
    migration_revision: str | None


def select_to_keep(
    stamps: Iterable[datetime], now: datetime, policy: RetentionPolicy
) -> set[datetime]:
    """Pure retention rule: newest N, plus newest per day for D days, plus newest per ISO week
    for W weeks (all in UTC). Returns the timestamps to KEEP."""
    ordered = sorted(set(stamps), reverse=True)
    keep: set[datetime] = set(ordered[: policy.keep_last])

    today = now.astimezone(UTC).date()
    oldest_day: date = today - timedelta(days=policy.keep_daily_days)
    seen_days: set[date] = set()
    for stamp in ordered:  # newest first, so the first hit per day is the newest
        day = stamp.astimezone(UTC).date()
        if day >= oldest_day and day not in seen_days:
            seen_days.add(day)
            keep.add(stamp)

    oldest_week: date = week_start(today) - timedelta(weeks=policy.keep_weekly_weeks)
    seen_weeks: set[tuple[int, int]] = set()
    for stamp in ordered:
        day = stamp.astimezone(UTC).date()
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        if week_start(day) >= oldest_week and key not in seen_weeks:
            seen_weeks.add(key)
            keep.add(stamp)
    return keep


def _validate_scrub(scopes: Sequence[Scope]) -> None:
    """A scrub set must be closed upward: scrubbing PERSONAL but keeping PRIVATE_WORK would leave
    rows that may reference deleted projects/parents (containment rule, D5)."""
    chosen = set(scopes)
    for scope in chosen:
        for other, rank in SCOPE_RANK.items():
            if rank > SCOPE_RANK[scope] and other not in chosen:
                raise ConfigError(
                    f"Scrubbing {scope.value} also requires scrubbing {other.value} "
                    "(more private scopes must go with it)"
                )


class BackupService:
    def __init__(
        self,
        db_path: Path,
        destinations: Sequence[BackupDestination],
        retention: RetentionPolicy,
        clock: Clock,
        authorizer: Authorizer,
        person_lookup: Callable[[str], Person | None],
    ) -> None:
        self._person_lookup = person_lookup
        self._db_path = db_path
        self._destinations = list(destinations)
        self._retention = retention
        self._clock = clock
        self._authz = authorizer
        names = [d.name for d in self._destinations]
        if len(set(names)) != len(names):
            raise ConfigError("Backup destination names must be unique")
        paths = [d.path.resolve() for d in self._destinations]
        if len(set(paths)) != len(paths):
            raise ConfigError("Backup destinations must use different folders")
        for d in self._destinations:
            _validate_scrub(d.scrub_scopes)

    # ---- public (actor-checked) -----------------------------------------------------------

    def destinations(self) -> list[BackupDestination]:
        return list(self._destinations)

    def create(
        self,
        actor: Actor,
        *,
        destination: str | None = None,
        to: Path | None = None,
        scrub: Sequence[Scope] = (),
    ) -> list[BackupResult]:
        """Back up to every configured destination, one named destination, or an ad-hoc `to`
        path (a file name ending in .sqlite3/.db, or a folder). Ad-hoc copies are never pruned."""
        self._require(actor)
        if to is not None:
            _validate_scrub(scrub)
            target = self._adhoc_target(to)
            size = self._snapshot(target, tuple(scrub))
            return [BackupResult("ad-hoc", target, size, tuple(scrub))]
        chosen = self._pick(destination)
        return [self._backup_and_prune(d) for d in chosen]

    def list_files(
        self, actor: Actor, destination: str | None = None
    ) -> dict[str, list[BackupFile]]:
        self._require(actor)
        return {d.name: self._files(d.path) for d in self._pick(destination)}

    def prune(self, actor: Actor, destination: str | None = None) -> dict[str, list[Path]]:
        self._require(actor)
        return {d.name: self._prune(d) for d in self._pick(destination)}

    def verify(self, actor: Actor, path: Path) -> VerifyReport:
        self._require(actor)
        if not path.is_file():
            raise ValidationError("Backup file not found")
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise ValidationError(f"Could not open backup: {exc}") from exc
        try:
            try:
                ok = conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            except sqlite3.DatabaseError as exc:
                raise ValidationError("That file is not a readable SQLite database") from exc
            counts: dict[str, int] = {}
            for table in _COUNT_TABLES:
                try:
                    counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    counts[table] = -1  # table missing: not a Family HQ database
            try:
                row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                revision = row[0] if row else None
            except sqlite3.Error:
                revision = None
        finally:
            conn.close()
        return VerifyReport(path, ok, counts, revision)

    # ---- scheduler entry point (no actor; runs as the system) -----------------------------

    def run_scheduled(self, interval_hours: float) -> list[BackupResult]:
        """Back up every destination whose newest backup is older than the interval."""
        results = []
        now = self._clock.now()
        for dest in self._destinations:
            files = self._files(dest.path)
            if files and now - files[0].created_at < timedelta(hours=interval_hours):
                continue
            results.append(self._backup_and_prune(dest))
        return results

    # ---- internals ------------------------------------------------------------------------

    def _require(self, actor: Actor) -> None:
        person = self._person_lookup(actor.person.id)  # fresh, not the actor's snapshot
        if person is None or not person.active:
            raise PermissionDeniedError("This person is inactive")
        self._authz.require(person, Permission.MANAGE_BACKUPS, "manage backups")

    def _pick(self, name: str | None) -> list[BackupDestination]:
        if name is None:
            return list(self._destinations)
        matches = [d for d in self._destinations if d.name == name]
        if not matches:
            known = ", ".join(d.name for d in self._destinations) or "none configured"
            raise ValidationError(f"Unknown backup destination '{name}' (known: {known})")
        return matches

    def _adhoc_target(self, to: Path) -> Path:
        if to.suffix.lower() in (".sqlite3", ".sqlite", ".db"):
            return to
        stamp = self._clock.now().strftime(_STAMP_FMT)
        return to / f"family_hq-{stamp}.sqlite3"

    def _backup_and_prune(self, dest: BackupDestination) -> BackupResult:
        stamp = self._clock.now().strftime(_STAMP_FMT)
        target = dest.path / f"family_hq-{stamp}.sqlite3"
        size = self._snapshot(target, dest.scrub_scopes)
        pruned = self._prune(dest)
        log.info(
            "backup_created",
            extra={
                "destination": dest.name,
                "bytes": size,
                "scrubbed": [s.value for s in dest.scrub_scopes],
            },
        )
        return BackupResult(dest.name, target, size, dest.scrub_scopes, tuple(pruned))

    def _files(self, folder: Path) -> list[BackupFile]:
        if not folder.is_dir():
            return []
        found = []
        for entry in folder.iterdir():
            match = _NAME_RE.match(entry.name)
            if match and entry.is_file():
                created = datetime.strptime(match.group(1), _STAMP_FMT).replace(tzinfo=UTC)
                found.append(BackupFile(entry, created, entry.stat().st_size))
        return sorted(found, key=lambda f: f.created_at, reverse=True)

    def _prune(self, dest: BackupDestination) -> list[Path]:
        files = self._files(dest.path)
        keep = select_to_keep((f.created_at for f in files), self._clock.now(), self._retention)
        removed = []
        for f in files:
            if f.created_at not in keep:
                f.path.unlink()
                removed.append(f.path)
        return removed

    def _snapshot(self, target: Path, scrub: Sequence[Scope]) -> int:
        if not self._db_path.is_file():
            raise ValidationError("Database file not found; nothing to back up")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".partial")
        tmp.unlink(missing_ok=True)
        src = sqlite3.connect(self._db_path)
        dst = sqlite3.connect(tmp, isolation_level=None)  # autocommit; we manage VACUUM ourselves
        try:
            src.backup(dst)
            src.close()
            dst.execute("PRAGMA journal_mode=DELETE")  # one self-contained file, no -wal sidecar
            if scrub:
                self._scrub(dst, scrub)
            result = dst.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise ValidationError("Backup failed its integrity check; it was discarded")
        except BaseException:
            dst.close()
            tmp.unlink(missing_ok=True)
            raise
        dst.close()
        os.replace(tmp, target)
        return target.stat().st_size

    @staticmethod
    def _scrub(conn: sqlite3.Connection, scopes: Sequence[Scope]) -> None:
        marks = ",".join("?" for _ in scopes)
        values = [s.value for s in scopes]
        private_tasks = f"SELECT id FROM tasks WHERE visibility_scope IN ({marks})"
        private_projects = f"SELECT id FROM projects WHERE visibility_scope IN ({marks})"
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute(
            "DELETE FROM external_refs WHERE "
            f"(entity_type='task' AND entity_id IN ({private_tasks})) OR "
            f"(entity_type='project' AND entity_id IN ({private_projects}))",
            values + values,
        )
        conn.execute(
            "DELETE FROM activity_events WHERE "
            f"visibility_scope IN ({marks}) OR task_id IN ({private_tasks}) "
            f"OR project_id IN ({private_projects})",
            values * 3,
        )
        conn.execute(f"DELETE FROM tasks WHERE visibility_scope IN ({marks})", values)
        conn.execute(
            f"DELETE FROM recurrence_definitions WHERE visibility_scope IN ({marks})", values
        )
        conn.execute(f"DELETE FROM projects WHERE visibility_scope IN ({marks})", values)
        conn.execute("VACUUM")  # rewrites the file so deleted text is not left in free pages
