"""Engine factory. The only place that knows about SQLite specifics."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def sqlite_url(path: Path) -> str:
    # as_posix keeps Windows drive paths valid: sqlite:///C:/Users/...
    return f"sqlite:///{path.resolve().as_posix()}"


def is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def sqlite_file(url: str) -> Path | None:
    parsed = make_url(url)
    if (
        parsed.get_backend_name() != "sqlite"
        or not parsed.database
        or parsed.database == ":memory:"
    ):
        return None
    return Path(parsed.database)


def make_engine(url: str) -> Engine:
    engine = create_engine(url)
    if is_sqlite(url):
        _configure_sqlite(engine)
    return engine


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _record):  # type: ignore[no-untyped-def]
        # Take over transaction control from pysqlite (see _on_begin below).
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(connection):  # type: ignore[no-untyped-def]
        # Every transaction takes SQLite's write lock up front. A household app has a handful of
        # writers, so serializing them is cheap, and it makes read-then-write sequences (such as
        # "claim if still unassigned") race-free instead of relying on luck.
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
