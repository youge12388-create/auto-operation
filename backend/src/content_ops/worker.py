from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from redis.exceptions import RedisError
from sqlalchemy import or_, select

from .db import SessionLocal, init_db
from .models import Job, ModelConfig
from .providers import provider_for
from .queueing import JOB_QUEUE, redis_client
from .scheduler import enqueue_due_jobs
from .settings import get_settings
from .workflow import run_job


def claim_and_run_once() -> bool:
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
            .order_by(Job.created_at)
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
        run_job(db, job.id, provider_for(model))
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def main() -> None:
    init_db()
    queue = redis_client()
    while True:
        db = SessionLocal()
        try:
            enqueue_due_jobs(db)
        finally:
            db.close()
        if not claim_and_run_once():
            try:
                queue.blpop(JOB_QUEUE, timeout=2)
            except RedisError:
                time.sleep(2)


if __name__ == "__main__":
    main()
