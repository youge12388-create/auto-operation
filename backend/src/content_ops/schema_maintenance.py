"""Small, idempotent upgrades for legacy databases without Alembic history."""

from sqlalchemy import Engine, inspect, text

from .db import engine


def ensure_user_session_version_column(bind: Engine) -> bool:
    """Add the per-user session version to an existing user table when absent."""
    user_columns = {column["name"] for column in inspect(bind).get_columns("users")}
    if "session_version" in user_columns:
        return False

    with bind.begin() as connection:
        connection.execute(
            text("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1")
        )
    return True


def main() -> None:
    ensure_user_session_version_column(engine)


if __name__ == "__main__":
    main()
