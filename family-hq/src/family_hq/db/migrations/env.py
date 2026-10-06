"""Alembic environment.

The database URL arrives via config.attributes["url"] (set by family_hq.db.migrate), or, for
developers running the `alembic` command directly, from the normal Family HQ configuration.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from family_hq.db.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.attributes.get("url") or config.get_main_option("sqlalchemy.url")
    if url:
        return str(url)
    from family_hq.config import load_settings  # developer path: `alembic revision --autogenerate`

    return load_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite cannot ALTER most things; batch mode rebuilds tables
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
