"""Postgres LISTEN/NOTIFY based job wake mechanism.  Works without Redis."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from sqlalchemy.engine import make_url

from .settings import get_settings

CHANNEL = "content_ops_jobs"
LISTEN_CHANNEL = "content_ops_jobs"
logger = logging.getLogger(__name__)


def _dsn() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite"):
        return ""
    # SQLAlchemy uses postgresql+psycopg:// while psycopg accepts the
    # driver-free postgresql:// URL. Preserve credentials and query parameters.
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def notify_wake() -> None:
    """Send NOTIFY on the job channel from any connection (API side)."""
    dsn = _dsn()
    if not dsn:
        return  # sqlite — no NOTIFY support
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("NOTIFY content_ops_jobs")
            conn.commit()
    except psycopg.Error:
        # The worker also polls; notification loss must not fail a created job.
        logger.warning("Unable to notify job worker; polling will pick up the job", exc_info=True)


@dataclass
class Listener:
    """Holds an open Postgres connection for LISTEN + select() polling."""

    _conn: "psycopg.Connection"
    _channel: str

    def wait(self, timeout: float = 2.0) -> bool:
        """Block until a NOTIFY arrives or timeout expires. Returns True on notify."""
        try:
            # notifies() is psycopg 3's public notification API.
            return next(self._conn.notifies(timeout=timeout, stop_after=1), None) is not None
        except psycopg.Error as exc:
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
