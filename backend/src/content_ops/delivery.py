from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Article, ArticleRevision, ChannelAccount, Publication, Theme
from .security import decrypt_secret
from .settings import get_settings
from .themes import render_revision
from .wechat import WeChatAPIError, WeChatClient


@dataclass(frozen=True)
class DeliveryResult:
    mode: str
    status: str
    publication_id: str | None = None
    remote_id: str | None = None
    publish_blocked: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def wechat_client_for_account(account: ChannelAccount) -> WeChatClient:
    if not account.encrypted_credentials:
        raise ValueError("公众号账号未配置凭证")
    credentials = json.loads(decrypt_secret(account.encrypted_credentials) or "{}")
    app_id = str(credentials.get("app_id") or "")
    app_secret = str(credentials.get("app_secret") or "")
    if not app_id or not app_secret:
        raise ValueError("公众号账号凭证不完整")
    return WeChatClient(app_id, app_secret)


def _mark_delivery_error(publication: Publication, exc: Exception) -> None:
    if isinstance(exc, WeChatAPIError):
        publication.status = (
            "unknown" if exc.result_unknown else ("failed_retryable" if exc.retryable else "failed_terminal")
        )
    else:
        publication.status = "failed_terminal"
    publication.error = str(exc)[:2000]


def _channel_html(
    db: Session,
    article: Article,
    revision: ArticleRevision,
    theme_id: str | None,
) -> tuple[str, dict[str, object]]:
    selected_theme_id = theme_id or (article.runtime_snapshot_json.get("theme") or {}).get("id")
    if not selected_theme_id:
        return revision.rendered_html, {}
    snapshot_config = article.runtime_snapshot_json.get("execution_config") or {}
    if str(snapshot_config.get("render_mode") or "") == "ai":
        # AI 装配产物在渲染阶段已按主题生成，直接交付，避免被确定性渲染覆盖。
        return revision.rendered_html, {"theme_id": selected_theme_id, "render_mode": "ai"}
    theme = db.get(Theme, selected_theme_id)
    if theme is None or not theme.enabled:
        raise ValueError("自动交付配置的排版主题不存在或已停用")
    rendered = render_revision(db, revision, theme)
    return rendered.html, {"theme_id": theme.id, "theme_version": theme.current_version}


def _ensure_wechat_draft(
    db: Session,
    article: Article,
    revision: ArticleRevision,
    account: ChannelAccount,
    config: dict[str, Any],
) -> Publication:
    key = f"{revision.id}:{account.id}:create_draft"
    publication = db.scalar(select(Publication).where(Publication.idempotency_key == key))
    if publication is not None and publication.status == "succeeded" and publication.remote_id:
        article.status = "wechat_draft"
        return publication
    if publication is not None and publication.status in {"running", "unknown"}:
        raise ValueError("该文章存在结果未确认的微信草稿请求，已停止重复提交")
    if publication is None:
        publication = Publication(
            article_revision_id=revision.id,
            channel_account_id=account.id,
            action="create_draft",
            status="running",
            idempotency_key=key,
        )
        db.add(publication)
    else:
        publication.status = "running"
        publication.error = None
    db.commit()
    db.refresh(publication)

    channel_html, theme_snapshot = _channel_html(db, article, revision, config.get("theme_id"))
    try:
        with wechat_client_for_account(account) as client:
            result = client.create_draft(
                title=article.title,
                content_html=channel_html,
                thumb_media_id=str(config.get("wechat_thumb_media_id") or ""),
                author=str(config.get("wechat_author") or "")[:20],
                digest=str(config.get("wechat_digest") or "")[:120],
                content_source_url=str(config.get("content_source_url") or "")[:2000],
                need_open_comment=bool(config.get("need_open_comment", False)),
                only_fans_can_comment=bool(config.get("only_fans_can_comment", False)),
            )
    except (WeChatAPIError, ValueError) as exc:
        _mark_delivery_error(publication, exc)
        db.commit()
        raise
    publication.status = "succeeded"
    publication.remote_id = result.media_id
    publication.response_json = {"media_id": result.media_id, **theme_snapshot}
    publication.error = None
    article.status = "wechat_draft"
    db.commit()
    db.refresh(publication)
    return publication


def _submit_publish(
    db: Session,
    article: Article,
    revision: ArticleRevision,
    account: ChannelAccount,
    draft: Publication,
) -> Publication:
    if not (account.capabilities_json or {}).get("publish"):
        raise ValueError("所选公众号账号没有自动发布权限")
    key = f"{revision.id}:{account.id}:publish"
    publication = db.scalar(select(Publication).where(Publication.idempotency_key == key))
    if publication is not None and publication.status in {"submitted", "succeeded"}:
        article.status = "published" if publication.status == "succeeded" else "publishing"
        return publication
    if publication is not None and publication.status in {"running", "unknown"}:
        raise ValueError("该文章存在结果未确认的微信发布请求，已停止重复提交")
    if publication is None:
        publication = Publication(
            article_revision_id=revision.id,
            channel_account_id=account.id,
            action="publish",
            status="running",
            idempotency_key=key,
        )
        db.add(publication)
    else:
        publication.status = "running"
        publication.error = None
    db.commit()
    db.refresh(publication)
    try:
        with wechat_client_for_account(account) as client:
            result = client.submit_publish(str(draft.remote_id or ""))
    except (WeChatAPIError, ValueError) as exc:
        _mark_delivery_error(publication, exc)
        db.commit()
        raise
    publication.status = "submitted"
    publication.remote_id = result.publish_id
    publication.response_json = {"publish_id": result.publish_id, "status": "submitted"}
    publication.error = None
    article.status = "publishing"
    db.commit()
    db.refresh(publication)
    return publication


def deliver_article(
    db: Session,
    article: Article,
    revision: ArticleRevision,
    config: dict[str, Any],
) -> DeliveryResult:
    mode = str(config.get("delivery_mode") or "local_draft")
    if mode == "local_draft":
        article.status = "drafted"
        db.flush()
        return DeliveryResult(mode=mode, status="succeeded")
    account_id = config.get("channel_account_id")
    account = db.get(ChannelAccount, account_id) if isinstance(account_id, str) else None
    if account is None or not account.enabled:
        raise ValueError("自动交付配置的公众号账号不存在或已停用")
    draft = _ensure_wechat_draft(db, article, revision, account, config)
    if mode == "wechat_draft":
        return DeliveryResult(
            mode=mode,
            status="succeeded",
            publication_id=draft.id,
            remote_id=draft.remote_id,
        )
    if mode != "auto_publish":
        raise ValueError(f"不支持的交付模式：{mode}")
    if not get_settings().auto_publish_enabled:
        return DeliveryResult(
            mode=mode,
            status="draft_succeeded",
            publication_id=draft.id,
            remote_id=draft.remote_id,
            publish_blocked="global_auto_publish_disabled",
        )
    publication = _submit_publish(db, article, revision, account, draft)
    return DeliveryResult(
        mode=mode,
        status=publication.status,
        publication_id=publication.id,
        remote_id=publication.remote_id,
    )