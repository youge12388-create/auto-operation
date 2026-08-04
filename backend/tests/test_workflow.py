import pytest
from sqlalchemy import select

from content_ops.models import (
    Article,
    ArticleRevision,
    EvidencePackage,
    JobEvent,
    ModelCallLog,
    Review,
    Source,
    Strategy,
    Topic,
)
from content_ops.providers import FakeProvider
from content_ops.workflow import create_job, run_job


def test_workflow_creates_draft_and_is_idempotent(db):
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/article",
        config_json={"title": "某 AI 产品更新", "content": "官方公告确认产品已发布。"},
    )
    strategy = Strategy(name="每日 AI 干货", objective="生成普通用户看得懂的 AI 更新文章")
    db.add_all([source, strategy])
    db.commit()

    job = create_job(db, strategy, "manual:one")
    same_job = create_job(db, strategy, "manual:one")
    assert same_job.id == job.id

    result = run_job(db, job.id, FakeProvider())
    assert result.status == "waiting_review"
    assert result.started_at is not None
    assert result.duration_ms >= 0
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None
    assert article.status == "waiting_review"
    assert article.model_snapshot["provider"] == "FakeProvider"
    assert article.skill_snapshot["strategy_version"] == strategy.version
    assert article.runtime_snapshot_json["strategy"]["version"] == strategy.version
    assert article.runtime_snapshot_json["sources"][0]["id"] == source.id
    assert db.get(type(job), job.id).payload_json["runtime_snapshot"]["strategy"]["id"] == strategy.id
    revision = db.scalar(select(ArticleRevision).where(ArticleRevision.article_id == article.id))
    assert revision is not None
    review = db.scalar(select(Review).where(Review.article_revision_id == revision.id))
    assert review is not None
    assert review.status == "pending"
    assert revision.content_markdown
    model_call = db.scalar(select(ModelCallLog).where(ModelCallLog.job_id == job.id))
    assert model_call is not None
    assert model_call.stage == "writing"
    assert model_call.status == "succeeded"
    topic = db.query(Topic).filter(Topic.job_id == job.id).one()
    assert topic.status == "accepted"
    assert len(topic.scores) == 3
    evidence = db.query(EvidencePackage).filter(EvidencePackage.article_id == article.id).one()
    assert evidence.status == "verified"
    assert len(evidence.claims) == 1
    assert db.query(JobEvent).filter(JobEvent.job_id == job.id).count() >= len(job.steps) * 2

    article.status = "approved"
    review.status = "approved"
    db.commit()
    result = run_job(db, job.id, FakeProvider())
    assert result.status == "succeeded"
    assert article.status == "drafted"


def test_failed_job_gets_retry_schedule(db):
    strategy = Strategy(name="重试策略", objective="测试任务重试")
    db.add(strategy)
    db.commit()
    job = create_job(db, strategy, "retryable-job", max_attempts=3)

    with pytest.raises(ValueError):
        run_job(db, job.id, FakeProvider())

    db.refresh(job)
    assert job.status == "failed_retryable"
    assert job.available_at is not None
    assert job.lease_until is None
    assert job.attempt_count == 1


def test_terminal_job_is_not_retried(db):
    strategy = Strategy(name="终态策略", objective="测试终态")
    db.add(strategy)
    db.commit()
    job = create_job(db, strategy, "terminal-job", max_attempts=1)

    with pytest.raises(ValueError):
        run_job(db, job.id, FakeProvider())

    db.refresh(job)
    assert job.status == "failed_terminal"
    assert job.available_at is None


def test_canceled_job_is_not_executed(db):
    strategy = Strategy(name="取消策略", objective="测试取消")
    db.add(strategy)
    db.commit()
    job = create_job(db, strategy, "canceled-job")
    job.status = "canceled"
    db.commit()

    result = run_job(db, job.id, FakeProvider())

    assert result.status == "canceled"
    assert db.scalar(select(Article).where(Article.job_id == job.id)) is None
