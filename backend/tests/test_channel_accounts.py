from types import SimpleNamespace

from content_ops.api import (
    ENV_CHANNEL_ID,
    add_channel_account,
    create_wechat_draft,
    list_channel_accounts,
    list_publications,
    resolve_channel_account,
)
from content_ops.models import Article, ArticleRevision, ChannelAccount, Job, Source, Strategy, Theme
from content_ops.providers import FakeProvider
from content_ops.schemas import ChannelAccountCreate, WechatDraftCreate
from content_ops.workflow import create_job, run_job


def test_channel_credentials_are_encrypted_and_redacted(db):
    created = add_channel_account(
        ChannelAccountCreate(
            name="测试公众号",
            app_id="wx-test",
            app_secret="secret-value",
            config={"publish_enabled": False},
        ),
        None,
        db,
    )

    account = db.get(ChannelAccount, created.id)
    assert account is not None
    assert account.encrypted_credentials != "secret-value"
    assert created.has_credentials is True
    assert "secret-value" not in str(created.model_dump())
    assert list_channel_accounts(None, db)[0].id == created.id


def test_environment_channel_is_listed_without_exposing_credentials(db, monkeypatch):
    monkeypatch.setattr(
        "content_ops.api.get_settings",
        lambda: SimpleNamespace(wechat_app_id="wx-env", wechat_app_secret="secret"),
    )

    listed = list_channel_accounts(None, db)
    environment = next(item for item in listed if item.id == ENV_CHANNEL_ID)
    account, channel_id = resolve_channel_account(db, ENV_CHANNEL_ID)

    assert environment.name == "环境默认公众号"
    assert environment.has_credentials is True
    assert environment.config == {"source": "environment", "readonly": True}
    assert environment.capabilities == {"draft": True, "publish": False}
    assert account is None
    assert channel_id == ENV_CHANNEL_ID


def test_channel_routes_and_draft_payload_keep_account_scope():
    from content_ops.api import app
    from content_ops.schemas import WechatDraftCreate

    paths = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/api/v1/channels/wechat/test" in paths
    assert "/api/v1/channels/accounts/{account_id}/test" in paths
    assert "/api/v1/channels/{account_id}/test" not in paths

    payload = WechatDraftCreate(channel_account_id="channel-1", thumb_media_id="thumb-1")
    assert payload.channel_account_id == "channel-1"


def test_bound_channel_draft_is_idempotent_without_exposing_credentials(db, monkeypatch):
    source = Source(
        name="公众号草稿测试来源",
        source_type="manual",
        url="https://example.com/wechat-draft",
        config_json={"title": "账号级草稿", "content": "已验证内容"},
    )
    strategy = Strategy(name="公众号草稿测试策略", objective="测试账号级草稿")
    db.add_all([source, strategy])
    db.commit()
    job = create_job(db, strategy, "wechat-bound-draft")
    run_job(db, job.id, FakeProvider())
    article = db.query(Article).filter(Article.job_id == job.id).one()
    revision = db.query(ArticleRevision).filter(ArticleRevision.article_id == article.id).one()
    article.status = "approved"
    db.commit()

    account = add_channel_account(
        ChannelAccountCreate(name="账号级公众号", app_id="wx-bound", app_secret="bound-secret"),
        None,
        db,
    )
    calls: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **kwargs):
            calls.append(kwargs["title"])
            return type("Result", (), {"media_id": "remote-draft-1"})()

    monkeypatch.setattr("content_ops.api.wechat_client_for_account", lambda _: FakeClient())
    payload = WechatDraftCreate(channel_account_id=account.id, thumb_media_id="thumb-1")
    first = create_wechat_draft(article.id, revision.id, payload, None, db)
    second = create_wechat_draft(article.id, revision.id, payload, None, db)

    assert first.remote_id == "remote-draft-1"
    assert second.id == first.id
    assert calls == [article.title]
    assert list_publications(None, db)[0].id == first.id
    assert db.query(ChannelAccount).one().encrypted_credentials != "bound-secret"


def test_draft_uses_selected_theme_without_changing_revision(monkeypatch, db):
    strategy = Strategy(name="主题草稿策略", objective="验证草稿排版")
    db.add(strategy)
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key="theme-draft-job")
    db.add(job)
    db.flush()
    article = Article(job_id=job.id, title="主题文章", status="approved")
    db.add(article)
    db.flush()
    revision = ArticleRevision(
        article_id=article.id,
        version=1,
        content_markdown="# 标题\n\n正文",
        rendered_html="<h1>标题</h1><p>正文</p>",
    )
    db.add(revision)
    db.flush()
    account = add_channel_account(
        ChannelAccountCreate(name="主题公众号", app_id="wx-theme", app_secret="secret"),
        None,
        db,
    )
    from content_ops.themes import ensure_builtin_themes

    ensure_builtin_themes(db)
    theme = db.query(Theme).filter(Theme.slug == "swiss-blue-grid").one()
    db.commit()
    received: list[str] = []

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **kwargs):
            received.append(kwargs["content_html"])
            return type("Result", (), {"media_id": "theme-draft"})()

    monkeypatch.setattr("content_ops.api.wechat_client_for_account", lambda _: FakeClient())
    result = create_wechat_draft(
        article.id,
        revision.id,
        WechatDraftCreate(channel_account_id=account.id, theme_id=theme.id, thumb_media_id="thumb"),
        None,
        db,
    )

    assert result.remote_id == "theme-draft"
    assert 'data-theme="swiss-blue-grid"' in received[0]
    assert "style=" in received[0]
    assert revision.content_markdown == "# 标题\n\n正文"
    assert result.response_json["theme_id"] == theme.id
