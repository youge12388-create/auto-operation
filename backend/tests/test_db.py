from content_ops.db import _engine_kwargs


def test_sqlite_engine_waits_for_short_write_contention() -> None:
    kwargs = _engine_kwargs("sqlite:///test.db")

    assert kwargs["connect_args"] == {"check_same_thread": False, "timeout": 30}


def test_postgres_engine_keeps_connection_health_check() -> None:
    assert _engine_kwargs("postgresql://localhost/content_ops") == {"pool_pre_ping": True}


def test_sqlite_engine_registers_begin_immediate() -> None:
    """SQLite transactions must start with BEGIN IMMEDIATE so a deferred
    read->write upgrade can never fail immediately despite busy_timeout."""
    import sqlalchemy.event

    from content_ops import db as db_module
    from content_ops.settings import get_settings

    if not get_settings().database_url.startswith("sqlite"):
        import pytest

        pytest.skip("SQLite-only behavior")

    assert sqlalchemy.event.contains(db_module.engine, "begin", db_module._begin_immediate)
    assert sqlalchemy.event.contains(db_module.engine, "connect", db_module._configure_sqlite)