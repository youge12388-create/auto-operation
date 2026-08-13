from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job, Strategy
from .workflow import create_job

_DAILY_AT_PATTERN = re.compile(r"daily@([01]\d|2[0-3]):[0-5]\d$")
_SCHEDULE_TIME_ZONE = ZoneInfo("Asia/Shanghai")


def normalize_schedule(schedule: str) -> str:
    normalized = schedule.strip().lower()
    if normalized in {"manual", "hourly", "daily"} or _DAILY_AT_PATTERN.fullmatch(normalized):
        return normalized
    raise ValueError("运行频率必须是 manual、hourly、daily 或 daily@HH:MM")


def schedule_window(schedule: str, now: datetime) -> str | None:
    try:
        normalized = normalize_schedule(schedule)
    except (AttributeError, ValueError):
        return None
    if normalized == "manual":
        return None
    if normalized == "hourly":
        return now.strftime("hourly:%Y%m%d%H")
    if normalized == "daily":
        return now.strftime("daily:%Y%m%d")
    match = _DAILY_AT_PATTERN.fullmatch(normalized)
    if match is not None:
        local_now = now.astimezone(_SCHEDULE_TIME_ZONE)
        scheduled_minutes = int(match.group(1)) * 60 + int(normalized[-2:])
        current_minutes = local_now.hour * 60 + local_now.minute
        if current_minutes < scheduled_minutes:
            return None
        return local_now.strftime("daily:%Y%m%d")
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
        created.append(create_job(db, strategy, key, payload={"mode": "automation"}))
    return created
