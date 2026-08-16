from content_ops import queueing


def test_notify_wake_sqlite_noop(monkeypatch):
    """When database_url is sqlite, notify_wake is a safe no-op and doesn't raise."""
    monkeypatch.setattr(queueing.get_settings(), "database_url", "sqlite:///./test.db")
    # should not raise
    queueing.notify_wake()


def test_listener_none_on_sqlite(monkeypatch):
    """create_listener returns None when using SQLite (no LISTEN/NOTIFY)."""
    monkeypatch.setattr(queueing.get_settings(), "database_url", "sqlite:///./test.db")
    assert queueing.create_listener() is None


def test_postgres_sqlalchemy_url_is_normalized_for_psycopg(monkeypatch):
    monkeypatch.setattr(
        queueing.get_settings(),
        "database_url",
        "postgresql+psycopg://user:secret@db:5432/content_ops?sslmode=require",
    )
    assert queueing._dsn() == "postgresql://user:secret@db:5432/content_ops?sslmode=require"
