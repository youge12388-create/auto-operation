from content_ops.db import _engine_kwargs


def test_sqlite_engine_waits_for_short_write_contention() -> None:
    kwargs = _engine_kwargs("sqlite:///test.db")

    assert kwargs["connect_args"] == {"check_same_thread": False, "timeout": 30}


def test_postgres_engine_keeps_connection_health_check() -> None:
    assert _engine_kwargs("postgresql://localhost/content_ops") == {"pool_pre_ping": True}