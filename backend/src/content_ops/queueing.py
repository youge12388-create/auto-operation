"""Postgres LISTEN/NOTIFY based job wake mechanism.  Works without Redis."""

from __future__ import annotations

import select
from dataclasses import dataclass

import psycopg

from .settings import get_settings

CHANNEL = "content_ops_jobs"
LISTEN_CHANNEL = "content_ops_jobs"


def _dsn() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return ""
    # psycopg DSN: postgresql://user:pass@host:port/db
    fixed = url
    if fixed.startswith("postgresql+"):
        fixed = fixed.split("+", 1)[1]
    return fixed


def notify_wake() -> None:
    """Send NOTIFY on the job channel from any connection (API side)."""
    dsn = _dsn()
    if not dsn:
        return  # sqlite — no NOTIFY support
    with psycopg.connect(dsn) as conn:
        conn.execute("NOTIFY content_ops_jobs")
        conn.commit()


@dataclass
class Listener:
    """Holds an open Postgres connection for LISTEN + select() polling."""

    _conn: "psycopg.Connection"
    _channel: str

    def wait(self, timeout: float = 2.0) -> bool:
        """Block until a NOTIFY arrives or timeout expires. Returns True on notify."""
        try:
            conn = self._conn
            # psycopg 3 uses a non-blocking socket internally
            if select.select([conn.fileno()], [], [], timeout) == ([], [], []):
                return False
            conn.poll()
            while conn.notifies:
                conn.notifies.pop(0)
            return True
        except (OSError, psycopg.Error) as exc:
            # connection error, caller should reconnect
            raise ConnectionError(f"Listener connection lost: {exc}") from exc

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


def create_listener() -> Listener | None:
    """Create a dedicated LISTEN connection for the worker loop."""
    dsn = _dsn()
    if not dsn:
        return None  # sqlite — no listener
    conn = psycopg.connect(dsn, autocommit=True)
    conn.execute(f"LISTEN {LISTEN_CHANNEL}")
    return Listener(_conn=conn, _channel=LISTEN_CHANNEL)
