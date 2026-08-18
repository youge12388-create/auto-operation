from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False, "timeout": 30}}
    return {"pool_pre_ping": True}


engine = create_engine(get_settings().database_url, future=True, **_engine_kwargs(get_settings().database_url))


if get_settings().database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        # Disable pysqlite's automatic BEGIN so SQLAlchemy controls the
        # transaction start (see _begin_immediate below).
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(dbapi_connection) -> None:  # type: ignore[no-untyped-def]
        # SQLite's default deferred transactions upgrade from a read lock to a
        # write lock on the first write. That upgrade fails immediately with
        # "database is locked" even when busy_timeout is set, because SQLite
        # cannot wait without risking a deadlock between upgrading writers.
        # BEGIN IMMEDIATE acquires the write lock up front so concurrent
        # writers (API and worker share one SQLite file) queue under
        # busy_timeout instead of failing on the read->write upgrade.
        dbapi_connection.exec_driver_sql("BEGIN IMMEDIATE")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
