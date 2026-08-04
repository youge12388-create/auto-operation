from content_ops.settings import PROJECT_ROOT, _resolve_sqlite_url


def test_relative_sqlite_url_is_resolved_from_backend_root():
    resolved = _resolve_sqlite_url("sqlite:///./data/content_ops.db")

    assert resolved == f"sqlite:///{(PROJECT_ROOT / 'data' / 'content_ops.db').as_posix()}"


def test_absolute_database_urls_are_preserved():
    url = "postgresql+psycopg://content_ops:secret@localhost:5432/content_ops"

    assert _resolve_sqlite_url(url) == url