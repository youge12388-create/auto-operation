from sqlalchemy import create_engine, inspect, text

from content_ops.schema_maintenance import ensure_user_session_version_column


def test_legacy_user_table_receives_session_version_once() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(320) NOT NULL)"))

    assert ensure_user_session_version_column(engine) is True
    assert "session_version" in {column["name"] for column in inspect(engine).get_columns("users")}
    assert ensure_user_session_version_column(engine) is False
