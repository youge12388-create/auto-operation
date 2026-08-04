import pytest
from fastapi import HTTPException

from content_ops.api import add_channel_account, publish_wechat_article
from content_ops.models import Article, ArticleRevision, Job, Publication, Strategy, User
from content_ops.schemas import ChannelAccountCreate, WechatPublishRequest


def test_publish_requires_explicit_channel_capability(db):
    strategy = Strategy(name="publish-guard", objective="guard")
    db.add(strategy)
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key="publish-guard-job")
    db.add(job)
    db.flush()
    article = Article(job_id=job.id, title="待发布文章", status="approved")
    db.add(article)
    db.flush()
    revision = ArticleRevision(
        article_id=article.id,
        version=1,
        content_markdown="# 标题",
        rendered_html="<h1>标题</h1>",
    )
    db.add(revision)
    db.commit()
    account = add_channel_account(
        ChannelAccountCreate(name="publish-guard-channel", app_id="wx", app_secret="secret"),
        None,
        db,
    )

    with pytest.raises(HTTPException) as error:
        publish_wechat_article(
            article.id,
            revision.id,
            WechatPublishRequest(channel_account_id=account.id),
            None,
            db,
        )

    assert error.value.status_code == 403


def test_publish_uses_idempotency_and_bound_account(monkeypatch, db):
    strategy = Strategy(name="publish-success", objective="publish")
    db.add(strategy)
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key="publish-success-job")
    db.add(job)
    db.flush()
    article = Article(job_id=job.id, title="可发布文章", status="approved")
    db.add(article)
    db.flush()
    revision = ArticleRevision(
        article_id=article.id,
        version=1,
        content_markdown="# 标题",
        rendered_html="<h1>标题</h1>",
    )
    db.add(revision)
    db.flush()
    account = add_channel_account(
        ChannelAccountCreate(
            name="publish-success-channel",
            app_id="wx-success",
            app_secret="secret",
            config={"publish_enabled": True},
        ),
        None,
        db,
    )
    db.add(
        Publication(
            article_revision_id=revision.id,
            channel_account_id=account.id,
            action="create_draft",
            status="succeeded",
            idempotency_key=f"{revision.id}:{account.id}:create_draft",
            remote_id="draft-1",
        )
    )
    db.commit()
    calls: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def submit_publish(self, media_id: str):
            calls.append(media_id)
            return type("Result", (), {"publish_id": "publish-1"})()

    monkeypatch.setattr("content_ops.api.wechat_client_for_account", lambda _: FakeClient())
    payload = WechatPublishRequest(channel_account_id=account.id)
    first = publish_wechat_article(article.id, revision.id, payload, None, db)
    second = publish_wechat_article(article.id, revision.id, payload, None, db)

    assert first.remote_id == "publish-1"
    assert second.id == first.id
    assert calls == ["draft-1"]


def test_operator_cannot_enable_publish_capability(db):
    operator = User(email="operator-publish@example.com", password_hash="hash", role="operator")
    db.add(operator)
    db.commit()

    with pytest.raises(HTTPException) as error:
        add_channel_account(
            ChannelAccountCreate(
                name="operator-publish-channel",
                app_id="wx-operator",
                app_secret="secret",
                config={"publish_enabled": True},
            ),
            operator,
            db,
        )

    assert error.value.status_code == 403