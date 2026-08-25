import pytest
from sqlalchemy import select

from content_ops import workflow
from content_ops.models import (
    Article,
    ArticleRevision,
    EvidencePackage,
    JobEvent,
    JobStep,
    ModelCallLog,
    ModelConfig,
    Review,
    Source,
    Strategy,
    Theme,
    Topic,
)
from content_ops.providers import FakeProvider
from content_ops.themes import ensure_builtin_themes
from content_ops.workflow import _parse_quality_review, create_job, run_job


def test_quality_review_parser_accepts_model_schema_wrapper():
    result = _parse_quality_review(
        '{"response_schema": {"status": "PASS", "score": 91, '
        + '"summary": "可发布", "checks": {"fact_traceability": true}}}'
    )

    assert result == {
        "status": "pass",
        "score": 91.0,
        "summary": "可发布",
        "checks": {"fact_traceability": True},
    }


def test_quality_review_parser_normalizes_common_score_scales():
    assert _parse_quality_review('{"status":"pass","score":0.8}')["score"] == 80.0
    assert _parse_quality_review('{"status":"pass","score":8}')["score"] == 80.0
    assert _parse_quality_review('{"status":"pass","score":80}')["score"] == 80.0



def test_workflow_creates_draft_and_is_idempotent(db):
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/article",
        config_json={"title": "某 AI 产品更新", "content": "官方公告确认产品已发布。"},
    )
    strategy = Strategy(name="每日 AI 干货", objective="生成普通用户看得懂的 AI 更新文章")
    strategy.config_json = {"review_rules": {"human_review_required": True}}
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
    model_calls = db.scalars(select(ModelCallLog).where(ModelCallLog.job_id == job.id)).all()
    assert "writing" in {model_call.stage for model_call in model_calls}
    assert "review" in {model_call.stage for model_call in model_calls}
    assert all(model_call.status == "succeeded" for model_call in model_calls)
    topic = db.query(Topic).filter(Topic.job_id == job.id).one()
    assert topic.status == "writing"
    assert len(topic.scores) == 4
    evidence = db.query(EvidencePackage).filter(EvidencePackage.article_id == article.id).one()
    assert evidence.status == "unavailable"
    assert len(evidence.claims) == 1
    assert db.query(JobEvent).filter(JobEvent.job_id == job.id).count() >= len(job.steps) * 2

    article.status = "approved"
    review.status = "approved"
    db.commit()
    result = run_job(db, job.id, FakeProvider())
    assert result.status == "succeeded"
    assert article.status == "drafted"



def test_auto_theme_selection_records_recommendation_on_the_article(db, monkeypatch):
    source = Source(
        name="manual-source",
        source_type="manual",
        url="https://example.com/source",
        config_json={"title": "workflow guide", "content": "A confirmed source."},
    )
    strategy = Strategy(name="auto-theme", objective="write a useful article")
    strategy.config_json = {
        "theme_selection_mode": "auto",
        "review_rules": {"human_review_required": True},
    }
    db.add_all([source, strategy])
    ensure_builtin_themes(db)
    db.commit()
    monkeypatch.setattr(
        workflow,
        "recommend_editorial_theme",
        lambda *_args: ("editorial-playbook", "deterministic test recommendation"),
    )

    job = create_job(db, strategy, "auto-theme-job")
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "waiting_review"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None
    selected_theme = db.get(Theme, article.runtime_snapshot_json["theme"]["id"])
    assert selected_theme is not None
    assert selected_theme.slug == "editorial-playbook"
    assert article.runtime_snapshot_json["theme_selection"] == {
        "mode": "auto",
        "recommended_slug": "editorial-playbook",
        "theme_id": selected_theme.id,
        "reason": "deterministic test recommendation",
    }
    event = db.scalar(
        select(JobEvent).where(
            JobEvent.job_id == job.id,
            JobEvent.event_type == "theme_recommendation",
        )
    )
    assert event is not None


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

def test_collect_isolates_failed_source_and_keeps_job_running(db, monkeypatch):
    good = Source(
        name="good",
        source_type="manual",
        url="https://example.com/good",
        config_json={"title": "可用素材", "content": "官方公告确认产品已发布。"},
    )
    bad = Source(
        name="bad",
        source_type="manual",
        url="https://example.com/bad",
        config_json={"title": "失败素材", "content": "这条来源会失败。"},
    )
    strategy = Strategy(name="采集隔离", objective="测试单源失败不中断任务")
    strategy.config_json = {"review_rules": {"human_review_required": True}}
    db.add_all([good, bad, strategy])
    db.commit()

    real_collect_source = workflow.collect_source

    def flaky_collect_source(db_session, source, **kwargs):
        if source.name == "bad":
            source.last_error = "simulated network failure"
            db_session.flush()
            raise ConnectionError("simulated network failure")
        return real_collect_source(db_session, source, **kwargs)

    monkeypatch.setattr(workflow, "collect_source", flaky_collect_source)
    job = create_job(db, strategy, "collect-isolation")
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "waiting_review"
    step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "collect"))
    assert step.status == "succeeded"
    assert step.output_json["succeeded_sources"] == 1
    assert "bad" in step.output_json["failed_sources"]
    assert bad.last_error is not None
    assert db.scalar(select(Article).where(Article.job_id == job.id)) is not None


def test_scan_isolates_failed_source_and_keeps_scan_running(db, monkeypatch):
    good = Source(
        name="good",
        source_type="manual",
        url="https://example.com/good",
        config_json={"title": "可用素材", "content": "官方公告确认产品已发布。"},
    )
    bad = Source(
        name="bad",
        source_type="manual",
        url="https://example.com/bad",
        config_json={"title": "失败素材", "content": "这条来源会失败。"},
    )
    model = ModelConfig(name="scan-model", provider="fake", enabled=True)
    db.add_all([good, bad, model])
    db.flush()
    strategy = Strategy(name="扫描隔离", objective="测试单源失败不中断扫描")
    strategy.config_json = {"default_model_id": model.id}
    db.add(strategy)
    db.commit()

    real_collect_source = workflow.collect_source

    def flaky_collect_source(db_session, source, **kwargs):
        if source.name == "bad":
            source.last_error = "simulated network failure"
            db_session.commit()
            raise ConnectionError("simulated network failure")
        return real_collect_source(db_session, source, **kwargs)

    monkeypatch.setattr(workflow, "collect_source", flaky_collect_source)
    job = create_job(db, strategy, "scan-isolation", payload={"mode": "scan"})
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "waiting_topic"
    step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "collect"))
    assert step.status == "succeeded"
    assert bad.last_error == "simulated network failure"
    failed_events = db.scalars(
        select(JobEvent).where(JobEvent.job_id == job.id, JobEvent.event_type == "source_failed")
    ).all()
    assert len(failed_events) == 1
    assert failed_events[0].payload_json["source"] == "bad"
