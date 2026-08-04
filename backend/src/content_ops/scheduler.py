from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job, Strategy
from .workflow import create_job


def schedule_window(schedule: str, now: datetime) -> str | None:
    normalized = schedule.strip().lower()
    if normalized == "manual":
        return None
    if normalized == "hourly":
        return now.strftime("hourly:%Y%m%d%H")
    if normalized == "daily":
        return now.strftime("daily:%Y%m%d")
    return None


def enqueue_due_jobs(db: Session, now: datetime | None = None) -> list[Job]:
    current = now or datetime.now(timezone.utc)
    created: list[Job] = []
    strategies = db.scalars(select(Strategy).where(Strategy.enabled.is_(True))).all()
    for strategy in strategies:
        window = schedule_window(strategy.schedule, current)
        if window is None:
            continue
        key = f"schedule:{strategy.id}:{window}"
        existing = db.scalar(select(Job).where(Job.idempotency_key == key))
        if existing is not None:
            continue
        created.append(create_job(db, strategy, key, payload={"mode": "scan"}))
    return created