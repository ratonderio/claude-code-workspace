from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from family_hq.repositories.sqlalchemy.repos import (
    SqlCategoryRepository,
    SqlEventRepository,
    SqlExternalRefRepository,
    SqlPersonRepository,
    SqlProjectRepository,
    SqlTaskRepository,
)


class SqlAlchemyUnitOfWork:
    """One database transaction exposing every repository. Rolls back unless commit() is called."""

    people: SqlPersonRepository
    categories: SqlCategoryRepository
    projects: SqlProjectRepository
    tasks: SqlTaskRepository
    events: SqlEventRepository
    external_refs: SqlExternalRefRepository

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.people = SqlPersonRepository(session)
        self.categories = SqlCategoryRepository(session)
        self.projects = SqlProjectRepository(session)
        self.tasks = SqlTaskRepository(session)
        self.events = SqlEventRepository(session)
        self.external_refs = SqlExternalRefRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            self._session.rollback()  # no-op after commit; undoes everything otherwise
        finally:
            self._session.close()
            self._session = None

    def commit(self) -> None:
        assert self._session is not None
        self._session.commit()

    def rollback(self) -> None:
        assert self._session is not None
        self._session.rollback()
