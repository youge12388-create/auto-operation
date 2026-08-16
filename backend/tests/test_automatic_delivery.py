from types import SimpleNamespace

from content_ops.delivery import deliver_article
from content_ops.models import Article, ArticleRevision, ChannelAccount, Job, Publication, Source, Strategy
from content_ops.providers import CompletionResponse, FakeProvider
from content_ops.workflow import create_job, run_job


def delivery_record(db, *, publish: bool):
    strategy = Strategy(name=f"delivery-{publish}", objective="test automatic delivery")
    db.add(strategy)
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key=f"delivery-job-{publish}")
    db.add(job)
    db.flush()
    article = Article(job_id=job.id, title="自动交付文章", status="approved")
    db.add(article)
    db.flush()
    revision = ArticleRevision(
        article_id=article.id,
        version=1,
        content_markdown="# 自动交付文章\n\n完整正文",
        rendered_html="<h1>自动交付文章</h1><p>完整正文</p>",
    )
    account = ChannelAccount(
        name=f"delivery-account-{publish}",
        enabled=True,
        capabilities_json={"draft": True, "publish": publish},
    )
    db.add_all([revision, account])
    db.commit()
    return article, revision, account


def test_auto_publish_mode_creates_draft_but_global_stop_blocks_publish(monkeypatch, db):
    article, revision, account = delivery_record(db, publish=True)
    calls: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **_):
            calls.append("draft")
            return SimpleNamespace(media_id="draft-blocked")

        def submit_publish(self, _):
            calls.append("publish")
            return SimpleNamespace(publish_id="should-not-run")

    monkeypatch.setattr("content_ops.delivery.wechat_client_for_account", lambda _: FakeClient())
    monkeypatch.setattr("content_ops.delivery.get_settings", lambda: SimpleNamespace(auto_publish_enabled=False))
    config = {
        "delivery_mode": "auto_publish",
        "channel_account_id": account.id,
        "wechat_thumb_media_id": "thumb-1",
    }

    first = deliver_article(db, article, revision, config)
    second = deliver_article(db, article, revision, config)

    assert first.publish_blocked == "global_auto_publish_disabled"
    assert second.remote_id == first.remote_id == "draft-blocked"
    assert article.status == "wechat_draft"
    assert calls == ["draft"]
    assert db.query(Publication).filter(Publication.action == "publish").count() == 0


def test_auto_publish_submits_only_once_when_global_switch_and_account_allow_it(monkeypatch, db):
    article, revision, account = delivery_record(db, publish=True)
    calls: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **_):
            calls.append("draft")
            return SimpleNamespace(media_id="draft-ready")

        def submit_publish(self, media_id):
            calls.append(f"publish:{media_id}")
            return SimpleNamespace(publish_id="publish-1")

    monkeypatch.setattr("content_ops.delivery.wechat_client_for_account", lambda _: FakeClient())
    monkeypatch.setattr("content_ops.delivery.get_settings", lambda: SimpleNamespace(auto_publish_enabled=True))
    config = {
        "delivery_mode": "auto_publish",
        "channel_account_id": account.id,
        "wechat_thumb_media_id": "thumb-1",
    }

    first = deliver_article(db, article, revision, config)
    second = deliver_article(db, article, revision, config)

    assert first.status == "submitted"
    assert second.publication_id == first.publication_id
    assert article.status == "publishing"
    assert calls == ["draft", "publish:draft-ready"]


def test_auto_publish_workflow_skips_human_review_after_quality_passes(monkeypatch, db):
    account = ChannelAccount(
        name="workflow-publish-account",
        enabled=True,
        capabilities_json={"draft": True, "publish": True},
    )
    source = Source(
        name="workflow-publish-source",
        source_type="manual",
        url="https://example.com/workflow-publish",
        config_json={
            "title": "Automatic publication",
            "content": "A complete source record for automatic publication.",
        },
    )
    db.add_all([account, source])
    db.flush()
    strategy = Strategy(
        name="workflow-publish-strategy",
        objective="publish after AI quality review",
        config_json={
            "delivery_mode": "auto_publish",
            "channel_account_id": account.id,
            "wechat_thumb_media_id": "thumb-workflow-publish",
            "review_rules": {"human_review_required": False},
        },
    )
    db.add(strategy)
    db.commit()
    calls: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **_):
            calls.append("draft")
            return SimpleNamespace(media_id="draft-workflow")

        def submit_publish(self, media_id):
            calls.append(f"publish:{media_id}")
            return SimpleNamespace(publish_id="publish-workflow")

    monkeypatch.setattr("content_ops.delivery.wechat_client_for_account", lambda _: FakeClient())
    monkeypatch.setattr("content_ops.delivery.get_settings", lambda: SimpleNamespace(auto_publish_enabled=True))
    monkeypatch.setattr(
        "content_ops.workflow.verify_evidence",
        lambda *_: {"verification_status": "verified", "summary": "verified", "claims": [], "sources": []},
    )
    job = create_job(db, strategy, "workflow-publish-job")
    result = run_job(db, job.id, FakeProvider())
    article = db.query(Article).filter(Article.job_id == job.id).one()
    db.expire_all()

    assert result.status == "succeeded"
    assert article.status == "publishing"

    assert any(revision.review and revision.review.status == "auto_approved" for revision in article.revisions)
    assert calls == ["draft", "publish:draft-workflow"]
    assert db.query(Publication).filter(Publication.action == "publish").one().remote_id == "publish-workflow"


class FailingQualityProvider:
    def complete(self, request):
        if request.user.startswith("QUALITY_REVIEW_JSON"):
            return CompletionResponse(
                text='{"status":"fail","score":45,"summary":"事实依据不足","checks":{"fact_traceability":false}}'
            )
        return FakeProvider().complete(request)

def test_failed_ai_quality_review_waits_for_human_review_before_auto_publish(monkeypatch, db):
    account = ChannelAccount(
        name="quality-guard-account",
        enabled=True,
        capabilities_json={"draft": True, "publish": True},
    )
    source = Source(
        name="quality-guard-source",
        source_type="manual",
        url="https://example.com/quality-guard",
        config_json={"title": "需要拦截的文章", "content": "这是一条用于测试审核门的中文事实素材。"},
    )
    db.add_all([account, source])
    db.flush()
    strategy = Strategy(
        name="quality-guard-strategy",
        objective="质量未通过时禁止自动发布",
        config_json={
            "delivery_mode": "auto_publish",
            "channel_account_id": account.id,
            "wechat_thumb_media_id": "thumb-quality",
            "review_rules": {"human_review_required": False},
        },
    )
    db.add(strategy)
    db.commit()

    calls: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **_):
            calls.append("draft")
            return SimpleNamespace(media_id="draft-quality-warning")

        def submit_publish(self, media_id):
            calls.append(f"publish:{media_id}")
            return SimpleNamespace(publish_id="publish-quality-warning")

    monkeypatch.setattr("content_ops.delivery.wechat_client_for_account", lambda _: FakeClient())
    monkeypatch.setattr("content_ops.delivery.get_settings", lambda: SimpleNamespace(auto_publish_enabled=False))

    job = create_job(db, strategy, "quality-guard-job")
    result = run_job(db, job.id, FailingQualityProvider())
    article = db.query(Article).filter(Article.job_id == job.id).one()

    assert result.status == "waiting_review"
    assert article.status == "waiting_review"
    assert article.revisions[-1].review.auto_result_json["status"] == "fail"
    assert article.revisions[-1].review.status == "pending"
    assert calls == []
    assert db.query(Publication).filter(Publication.action == "create_draft").count() == 0


class InvalidQualityProvider:
    def complete(self, request):
        if request.user.startswith("QUALITY_REVIEW_JSON"):
            return CompletionResponse(text="not-json")
        return FakeProvider().complete(request)


def test_invalid_ai_quality_review_is_recorded_but_does_not_fail_local_delivery(db):
    source = Source(
        name="invalid-quality-source",
        source_type="manual",
        url="https://example.com/invalid-quality",
        config_json={"title": "Quality advisory", "content": "A complete verified source record."},
    )
    strategy = Strategy(
        name="invalid-quality-strategy",
        objective="Keep delivery moving when advisory review is unavailable",
        config_json={"review_rules": {"human_review_required": False}},
    )
    db.add_all([source, strategy])
    db.commit()

    job = create_job(db, strategy, "invalid-quality-job")
    result = run_job(db, job.id, InvalidQualityProvider())
    article = db.query(Article).filter(Article.job_id == job.id).one()

    assert result.status == "succeeded"
    assert article.status == "drafted"
    assert article.revisions[-1].review.auto_result_json["status"] == "fail"
    assert article.revisions[-1].review.status == "auto_approved"
