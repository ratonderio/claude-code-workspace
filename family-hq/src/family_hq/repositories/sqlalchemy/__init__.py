"""SQLAlchemy persistence. Dialect-agnostic: SQLite today, PostgreSQL by changing the URL."""

from family_hq.repositories.sqlalchemy.uow import SqlAlchemyUnitOfWork

__all__ = ["SqlAlchemyUnitOfWork"]
