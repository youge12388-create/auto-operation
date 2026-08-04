import pytest
from fastapi import BackgroundTasks, HTTPException

from content_ops.api import cancel_job, retry_job
from content_ops.models import Strategy
from content_ops.providers import FakeProvider
from content_ops.workflow import create_job, run_job


def test_retry_and_cancel_enforce_job_state_machine(db):
    failed_strategy = Strategy(name="失败任务状态", objective="验证失败任务")
    db.add(failed_strategy)
    db.commit()
    failed_job = create_job(db, failed_strategy, "state-failed", max_attempts=2)

    with pytest.raises(ValueError):
        run_job(db, failed_job.id, FakeProvider())
    db.refresh(failed_job)
    assert failed_job.status == "failed_retryable"
    retry = retry_job(failed_job.id, BackgroundTasks(), None, db)
    assert retry.status == "queued"
    assert retry.attempt_count == 0
    assert retry.started_at is None

    cancel = cancel_job(retry.id, None, db)
    assert cancel.status == "canceled"
    assert cancel.completed_at is not None
    with pytest.raises(HTTPException) as exc:
        retry_job(cancel.id, BackgroundTasks(), None, db)
    assert exc.value.status_code == 409


def test_successful_job_cannot_be_canceled(db):
    strategy = Strategy(name="成功任务状态", objective="验证成功任务")
    db.add(strategy)
    db.commit()
    job = create_job(db, strategy, "state-success")
    job.status = "succeeded"
    db.commit()

    with pytest.raises(HTTPException) as exc:
        cancel_job(job.id, None, db)
    assert exc.value.status_code == 409
