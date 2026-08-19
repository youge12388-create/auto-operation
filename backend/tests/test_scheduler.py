from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select

from content_ops.api import add_strategy, update_strategy
from content_ops.channels import ENV_CHANNEL_ID
from content_ops.models import Article, Job, ModelConfig, Publication, Source, Strategy, StrategyVersion
from content_ops.providers import FakeProvider
from content_ops.scheduler import enqueue_due_jobs, normalize_schedule, schedule_window
from content_ops.schemas import StrategyCreate
from content_ops.workflow import run_job


def test_schedule_window_supports_manual_hourly_daily_and_daily_at():
    now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)
    assert schedule_window("manual", now) is None
    assert schedule_window("hourly", now) == "hourly:2026072708"
    assert schedule_window("daily", now) == "daily:20260727"
    assert schedule_window("unknown", now) is None
    assert schedule_window("daily@09:00", datetime(2026, 7, 27, 0, 59, tzinfo=timezone.utc)) is None
    assert schedule_window("daily@09:00", datetime(2026, 7, 27, 1, 0, tzinfo=timezone.utc)) == "daily:20260727"
    assert schedule_window("daily@09:00", datetime(2026, 7, 27, 2, 30, tzinfo=timezone.utc)) == "daily:20260727"
    assert normalize_schedule(" DAILY@09:00 ") == "daily@09:00"



def test_normalize_schedule_rejects_invalid_fixed_daily_time():
    try:
        normalize_schedule("daily@24:00")
    except ValueError as exc:
        assert "daily@HH:MM" in str(exc)
    else:
        raise AssertionError("invalid fixed daily time must be rejected")

def test_enqueue_due_jobs_skips_failing_strategy(db, monkeypatch):
    good = Strategy(name="good", objective="good", schedule="hourly", enabled=True)
    good.config_json = {"review_rules": {"human_review_required": True}}
    bad = Strategy(name="bad", objective="bad", schedule="hourly", enabled=True)
    bad.config_json = {"review_rules": {"human_review_required": True}}
    db.add_all([good, bad])
    db.commit()

    from content_ops import scheduler as scheduler_module

    original_create_job = scheduler_module.create_job

    def flaky_create_job(db_, strategy, idempotency_key, **kwargs):
        if strategy.name == "bad":
            raise ValueError("strategy boom")
        return original_create_job(db_, strategy, idempotency_key, **kwargs)

    monkeypatch.setattr(scheduler_module, "create_job", flaky_create_job)
    now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)

    jobs = enqueue_due_jobs(db, now)

    assert len(jobs) == 1
    assert jobs[0].strategy_id == good.id


def test_enqueue_due_jobs_is_idempotent(db):
    source = Source(
        name="scheduled-source",
        source_type="manual",
        url="https://example.com/scheduled",
        config_json={"title": "Scheduled title", "content": "Scheduled facts"},
    )
    strategy = Strategy(name="daily", objective="scheduled", schedule="daily", enabled=True)
    strategy.config_json = {"review_rules": {"human_review_required": True}}
    manual = Strategy(name="manual", objective="manual", schedule="manual", enabled=True)
    model = ModelConfig(provider="fake", name="scheduler-translation-model")
    db.add_all([source, strategy, manual, model])
    db.commit()
    now = datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc)

    first = enqueue_due_jobs(db, now)
    second = enqueue_due_jobs(db, now)

    assert len(first) == 1
    assert second == []
    jobs = db.scalars(select(Job)).all()
    assert len(jobs) == 1
    assert jobs[0].idempotency_key == f"schedule:{strategy.id}:daily:20260727"
    assert jobs[0].payload_json["mode"] == "automation"

    result = run_job(db, jobs[0].id, FakeProvider())
    article = db.scalar(select(Article).where(Article.job_id == jobs[0].id))

    assert result.status == "waiting_review"
    assert article is not None
    assert article.title == "\u4e2d\u6587\u8bd1\u6587\uff1aScheduled title"


def test_strategy_updates_create_immutable_versions(db):
    first = add_strategy(
        StrategyCreate(name="versioned", objective="first", schedule="daily"),
        None,
        db,
    )
    updated = update_strategy(
        first.id,
        StrategyCreate(name="versioned", objective="second", schedule="hourly"),
        None,
        db,
    )

    versions = (
        db.query(StrategyVersion)
        .filter(StrategyVersion.strategy_id == first.id)
        .order_by(StrategyVersion.version)
        .all()
    )
    assert updated.version == 2
    assert [(item.version, item.objective, item.schedule) for item in versions] == [
        (1, "first", "daily"),
        (2, "second", "hourly"),
    ]


def test_scheduled_automatic_draft_uses_environment_channel(monkeypatch, db):
    source = Source(
        name="scheduled-wechat-source",
        source_type="manual",
        url="https://example.com/scheduled-wechat",
        config_json={"title": "Scheduled draft", "content": "A scheduled draft source."},
    )
    db.add(source)
    db.commit()
    add_strategy(
        StrategyCreate(
            name="scheduled-wechat-draft",
            objective="create a WeChat draft automatically",
            schedule="daily",
            enabled=True,
            config={
                "source_ids": [],
                "delivery_mode": "wechat_draft",
                "channel_account_id": ENV_CHANNEL_ID,
                "wechat_thumb_media_id": "scheduled-thumb",
                "review_rules": {"human_review_required": False},
            },
        ),
        None,
        db,
    )
    created: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **_):
            created.append("draft")
            return SimpleNamespace(media_id="scheduled-draft")

    monkeypatch.setattr("content_ops.delivery.WeChatClient.from_settings", lambda _: FakeClient())

    jobs = enqueue_due_jobs(db, datetime(2026, 7, 27, 8, 30, tzinfo=timezone.utc))
    result = run_job(db, jobs[0].id, FakeProvider())
    article = db.scalar(select(Article).where(Article.job_id == jobs[0].id))

    assert result.status == "succeeded"
    assert article is not None
    publication = db.scalar(select(Publication).where(Publication.article_revision_id == article.revisions[0].id))
    assert article.status == "wechat_draft"
    assert publication is not None
    assert publication.channel_account_id == ENV_CHANNEL_ID
    assert publication.remote_id == "scheduled-draft"
    assert created == ["draft"]
