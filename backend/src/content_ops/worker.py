from __future__ import annotations

import signal
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, or_, select

from .db import SessionLocal, init_db
from .models import Job, ModelConfig
from .providers import provider_for
from .queueing import create_listener
from .scheduler import enqueue_due_jobs
from .settings import get_settings
from .workflow import run_job

# Graceful shutdown flag
_shutdown_requested = False
_shutdown_job_done = False
_RUNNING = False  # internal, only read/written under GIL on main thread


def _on_signal(signum, frame) -> None:  # type: ignore[no-untyped-def]
    global _shutdown_requested
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT, _on_signal)


def claim_and_run_once() -> bool:
    global _RUNNING
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        job = db.scalar(
            select(Job)
            .where(
                or_(
                    Job.status == "queued",
                    (Job.status == "running") & (Job.lease_until < now),
                    (Job.status == "failed_retryable") & (Job.available_at <= now),
                )
            )
            .order_by(desc(Job.priority), Job.created_at)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return False
        job.status = "running"
        job.available_at = None
        job.lease_until = datetime.now(timezone.utc) + timedelta(seconds=get_settings().job_lease_seconds)
        db.commit()
        model_id = (job.payload_json or {}).get("model_id")
        model = db.get(ModelConfig, model_id) if model_id else None
        _RUNNING = True
        try:
            run_job(db, job.id, provider_for(model))
        finally:
            _RUNNING = False
        return True
    except Exception:
        db.rollback()
        _RUNNING = False
        return False
    finally:
        db.close()


def _wait_for_notify_or_timeout(listener, timeout: float = 2.0) -> None:
    """Wait using Postgres LISTEN/NOTIFY or fallback to time.sleep."""
    if listener is None:
        # SQLite mode: just sleep
        if _shutdown_requested:
            return
        deadline = time.time() + timeout
        while time.time() < deadline and not _shutdown_requested:
            time.sleep(0.1)
        return
    # Postgres mode: use LISTEN with interruptible polling
    deadline = time.time() + timeout
    while time.time() < deadline and not _shutdown_requested:
        remaining = deadline - time.time()
        poll = min(remaining, 1.0)
        if poll <= 0:
            break
        try:
            listener.wait(timeout=poll)
            return
        except ConnectionError:
            time.sleep(1)
            return


def main() -> None:
    global _shutdown_requested, _RUNNING, _shutdown_job_done

    init_db()
    listener = create_listener()

    try:
        while not _shutdown_requested:
            db = SessionLocal()
            try:
                enqueue_due_jobs(db)
            finally:
                db.close()

            _shutdown_job_done = False
            if not claim_and_run_once():
                if _shutdown_requested:
                    _shutdown_job_done = True
                    break
                _wait_for_notify_or_timeout(listener)

            if _shutdown_requested and not _RUNNING:
                _shutdown_job_done = True
                break

        # Graceful shutdown: wait for running job to finish
        deadline = time.time() + 30  # max 30-second grace period
        print("[worker] 收到关闭信号，等待当前任务完成...")
        while _RUNNING and time.time() < deadline:
            time.sleep(0.25)
        print("[worker] 安全退出。")
    finally:
        if listener is not None:
            listener.close()


if __name__ == "__main__":
    main()
