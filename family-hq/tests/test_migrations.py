from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from family_hq.db.engine import make_engine, sqlite_url
from family_hq.db.migrate import current_revision, head_revision, upgrade_to_head
from family_hq.db.models import Base


def test_migrations_produce_exactly_the_orm_schema(tmp_path):
    url = sqlite_url(tmp_path / "m.sqlite3")
    upgrade_to_head(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        diffs = compare_metadata(
            MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata
        )
    assert diffs == [], f"models and migrations have drifted; write a migration: {diffs}"
    assert current_revision(engine) == head_revision()
    assert {"people", "tasks", "projects", "activity_events", "external_refs", "categories"} <= set(
        inspect(engine).get_table_names()
    )


def test_upgrade_is_idempotent(tmp_path):
    url = sqlite_url(tmp_path / "m.sqlite3")
    upgrade_to_head(url)
    upgrade_to_head(url)
    assert current_revision(make_engine(url)) == head_revision()


def test_sqlite_pragmas_are_applied(tmp_path):
    from sqlalchemy import text

    url = sqlite_url(tmp_path / "p.sqlite3")
    upgrade_to_head(url)
    engine = make_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_foreign_keys_are_enforced(tmp_path):
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    url = sqlite_url(tmp_path / "f.sqlite3")
    upgrade_to_head(url)
    engine = make_engine(url)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tasks (id,title,status,owner_id,visibility_scope,priority,created_at,"
                "updated_at,due_all_day,postpone_count,source,version) VALUES "
                "('t','x','OPEN','nobody','FAMILY','NORMAL','2026-01-01','2026-01-01',0,0,'CLI',1)"
            )
        )


def test_recurrence_occurrence_uniqueness_is_enforced_by_the_database(world):
    """The database-level guarantee behind idempotent recurrence generation (Phase 3)."""
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    engine = world.container.engine
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO recurrence_definitions (id,title,visibility_scope,priority,rrule,dtstart,"
                "timezone,active,created_at,updated_at) VALUES ('r1','Trash','FAMILY','NORMAL',"
                "'FREQ=WEEKLY','2026-10-01T07:00:00','America/New_York',1,'2026-01-01','2026-01-01')"
            )
        )

    def occurrence(task_id: str, key: str | None) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tasks (id,title,status,visibility_scope,priority,created_at,updated_at,"
                    "due_all_day,postpone_count,source,version,recurrence_definition_id,occurrence_key) "
                    "VALUES (:id,'Trash','OPEN','FAMILY','NORMAL','2026-01-01','2026-01-01',0,0,'RECURRENCE',1,"
                    ":rd,:key)"
                ),
                {"id": task_id, "rd": "r1" if key else None, "key": key},
            )

    occurrence("a", "2026-10-08")
    with pytest.raises(IntegrityError):
        occurrence("b", "2026-10-08")
    occurrence("c", "2026-10-15")
    occurrence("d", None)  # ordinary tasks (NULL, NULL) never collide
    occurrence("e", None)
