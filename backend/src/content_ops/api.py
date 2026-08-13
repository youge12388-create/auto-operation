from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from markdown_it import MarkdownIt
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .db import get_db
from .ingestion import collect_source
from .material_classification import classify_materials as run_material_classification
from .material_curation import curate_materials as run_material_curation
from .models import (
    Article,
    ArticleRevision,
    AuditLog,
    ChannelAccount,
    EvidencePackage,
    Job,
    JobEvent,
    JobStep,
    MaterialCategory,
    ModelConfig,
    Publication,
    Review,
    Skill,
    SkillVersion,
    Source,
    SourceGroup,
    SourceItem,
    Strategy,
    StrategyVersion,
    Theme,
    ThemeVersion,
    Topic,
    TopicAlgorithm,
    TopicMaterial,
    User,
)
from .providers import CompletionRequest, provider_for
from .queueing import notify_wake
from .scheduler import normalize_schedule
from .schemas import (
    ArticleRead,
    ArticleRevisionCreate,
    ArticleRevisionRead,
    AuditLogRead,
    CalendarItemRead,
    ChannelAccountCreate,
    ChannelAccountRead,
    ChannelAccountUpdate,
    EvidenceClaimRead,
    EvidencePackageRead,
    EvidenceSourceRead,
    JobCreate,
    JobEventRead,
    JobRead,
    LoginRequest,
    ManualMaterialCreate,
    MaterialBatchTopicCreate,
    MaterialCategoryAssign,
    MaterialCategoryCreate,
    MaterialCategoryRead,
    MaterialCategoryUpdate,
    MaterialClassifyRead,
    MaterialClassifyRequest,
    MaterialCurateRead,
    MaterialCurateRequest,
    MaterialDetailRead,
    MaterialRead,
    MaterialTopicCreate,
    MaterialTriage,
    ModelCreate,
    ModelRead,
    ModelTestRead,
    ModelUpdate,
    PublicationRead,
    ReviewCreate,
    ReviewRead,
    SkillRead,
    SkillVersionRead,
    SourceCollectRead,
    SourceCreate,
    SourceGroupCreate,
    SourceGroupRead,
    SourceGroupUpdate,
    SourceRead,
    StrategyCreate,
    StrategyRead,
    StrategyRunRequest,
    ThemeCopy,
    ThemeCreate,
    ThemePreviewRead,
    ThemeRead,
    ThemeUpdate,
    TopicAlgorithmCreate,
    TopicAlgorithmRead,
    TopicAlgorithmUpdate,
    TopicCreate,
    TopicDecision,
    TopicMaterialRead,
    TopicRead,
    TopicScanRequest,
    TopicScoreRead,
    TopicStartWriting,
    UserCreate,
    UserRead,
    WechatConnectionRead,
    WechatDraftCreate,
    WechatMaterialRead,
    WechatPublishRequest,
)
from .security import (
    SESSION_COOKIE,
    decrypt_secret,
    encrypt_secret,
    get_current_user,
    hash_password,
    make_session,
    require_roles,
    verify_password,
)
from .settings import get_settings
from .skills import SkillPackageError, validate_skill_package
from .strategy_combinations import validate_strategy_definition, validate_strategy_definition_references
from .strategy_config import StrategyConfigError, model_id_for_stage
from .themes import ensure_builtin_themes, render_revision
from .topic_algorithms import (
    ensure_builtin_topic_algorithm,
    normalize_topic_algorithm,
    topic_algorithm_snapshot,
    topic_algorithm_values,
)
from .wechat import WeChatAPIError, WeChatClient
from .workflow import create_job, run_job

app = FastAPI(title="AI 自动内容运营系统", version="0.1.0")


def wechat_error_detail(exc: WeChatAPIError) -> str:
    if exc.code != 40164:
        return str(exc)
    match = re.search(r"invalid ip ([0-9.]+)", str(exc))
    ip = match.group(1) if match else "当前服务器出口 IP"
    return (
        f"微信公众号拒绝访问：服务器出口 IP {ip} 未加入白名单。"
        f"请到微信公众平台「设置与开发 → 基本配置 → IP 白名单」添加 {ip} 后重试。"
        "错误中的 ::ffff: 地址是同一 IPv4 的映射形式，无需重复添加。"
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOB_PRIORITY_MIGRATION_DETAIL = (
    "数据库结构尚未升级：缺少 automation_jobs.priority，请先应用 Alembic 迁移 0005_job_priority。"
)
MATERIAL_CATEGORY_MIGRATION_DETAIL = (
    "数据库结构尚未升级：缺少素材分类字段，请先备份数据库并应用 Alembic 迁移 0008_material_categories。"
)


def raise_material_schema_error(exc: OperationalError) -> None:
    detail = str(exc)
    if "source_items.category_id" in detail or "source_items.classification_" in detail:
        raise HTTPException(status_code=503, detail=MATERIAL_CATEGORY_MIGRATION_DETAIL) from exc
    raise exc


def raise_job_schema_error(exc: OperationalError) -> None:
    if "automation_jobs.priority" in str(exc):
        raise HTTPException(status_code=503, detail=JOB_PRIORITY_MIGRATION_DETAIL) from exc
    raise exc


def source_read(source: Source) -> SourceRead:
    return SourceRead(
        id=source.id,
        name=source.name,
        source_type="url" if source.source_type == "website" else source.source_type,
        url=source.url,
        group_name=source.group_name,
        group_id=source.group_id,
        enabled=source.enabled,
        requires_review=source.requires_review,
        config=source.config_json,
        last_success_at=source.last_success_at,
        last_error=source.last_error,
    )


def material_read(item: SourceItem, include_content: bool = False) -> MaterialRead | MaterialDetailRead:
    source = item.source
    values = {
        "id": item.id,
        "source_id": item.source_id,
        "source_name": source.name if source is not None else "Unknown source",
        "title": item.title,
        "url": item.url,
        "content_excerpt": item.content[:1200],
        "published_at": item.published_at,
        "created_at": item.created_at,
        "triage_status": item.triage_status,
        "category_id": item.category_id,
        "category_name": item.category.name if item.category is not None else None,
        "classification_status": item.classification_status,
        "classification_source": item.classification_source,
        "classification_confidence": item.classification_confidence,
        "classification_reason": item.classification_reason,
        "classification_error": item.classification_error,
    }
    if include_content:
        return MaterialDetailRead(**values, content=item.content)
    return MaterialRead(**values)


def strategy_read(strategy: Strategy) -> StrategyRead:
    return StrategyRead(
        id=strategy.id,
        name=strategy.name,
        objective=strategy.objective,
        schedule=strategy.schedule,
        automation_level=strategy.automation_level,
        enabled=strategy.enabled,
        config=strategy.config_json,
        version=strategy.version,
    )


def theme_read(theme: Theme) -> ThemeRead:
    version = next((item for item in theme.versions if item.version == theme.current_version), None)
    return ThemeRead(
        id=theme.id,
        name=theme.name,
        slug=theme.slug,
        description=theme.description,
        enabled=theme.enabled,
        is_builtin=theme.is_builtin,
        current_version=theme.current_version,
        tokens=version.tokens_json if version else {},
    )


def model_read(model: ModelConfig) -> ModelRead:
    return ModelRead(
        id=model.id,
        provider=model.provider,
        name=model.name,
        api_base_url=model.api_base_url,
        enabled=model.enabled,
        config=model.config_json,
        has_api_key=bool(model.encrypted_api_key),
    )
_TERMINAL_JOB_STATUSES = frozenset({"succeeded", "failed_terminal", "canceled"})


def _contains_model_id(value: object, model_id: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_model_id(item, model_id) for item in value.values())
    if isinstance(value, list):
        return any(_contains_model_id(item, model_id) for item in value)
    return value == model_id


def _model_delete_blockers(db: Session, model_id: str) -> list[str]:
    blockers = [
        f"策略「{strategy.name}」"
        for strategy in db.scalars(select(Strategy)).all()
        if _contains_model_id(strategy.config_json or {}, model_id)
    ]
    blockers.extend(
        f"运行中的任务 {job.id}"
        for job in db.scalars(select(Job).where(Job.status.not_in(_TERMINAL_JOB_STATUSES))).all()
        if _contains_model_id(job.payload_json or {}, model_id)
    )
    return blockers


def channel_account_read(account: ChannelAccount) -> ChannelAccountRead:
    return ChannelAccountRead(
        id=account.id,
        channel_type=account.channel_type,
        name=account.name,
        enabled=account.enabled,
        config=account.config_json,
        capabilities=account.capabilities_json,
        has_credentials=bool(account.encrypted_credentials),
    )


ENV_CHANNEL_ID = "env:default"


def resolve_channel_account(
    db: Session,
    account_id: str | None,
) -> tuple[ChannelAccount | None, str]:
    if not account_id or account_id == ENV_CHANNEL_ID:
        return None, ENV_CHANNEL_ID
    account = db.get(ChannelAccount, account_id)
    if not account or not account.enabled:
        raise HTTPException(status_code=404, detail="渠道账号不存在或已停用")
    return account, account.id


def wechat_client_for_account(account: ChannelAccount) -> WeChatClient:
    if not account.encrypted_credentials:
        raise ValueError("channel credentials are not configured")
    credentials = json.loads(decrypt_secret(account.encrypted_credentials) or "{}")
    app_id = str(credentials.get("app_id") or "")
    app_secret = str(credentials.get("app_secret") or "")
    if not app_id or not app_secret:
        raise ValueError("channel credentials are incomplete")
    return WeChatClient(app_id, app_secret)


def review_read(review: Review) -> ReviewRead:
    return ReviewRead(
        id=review.id,
        article_revision_id=review.article_revision_id,
        status=review.status,
        auto_result=review.auto_result_json,
        reviewer_id=review.reviewer_id,
        comment=review.comment,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def topic_read(topic: Topic) -> TopicRead:
    return TopicRead(
        id=topic.id,
        strategy_id=topic.strategy_id,
        job_id=topic.job_id,
        source_item_id=topic.source_item_id,
        title=topic.title,
        status=topic.status,
        score=topic.score,
        rationale=topic.rationale,
        scores=[
            TopicScoreRead(
                id=item.id,
                topic_id=item.topic_id,
                dimension=item.dimension,
                score=item.score,
                rationale=item.rationale,
            )
            for item in sorted(topic.scores, key=lambda value: value.dimension)
        ],
        materials=[
            TopicMaterialRead(
                source_item_id=link.source_item_id,
                source_name=link.material.source.name if link.material.source is not None else "Unknown source",
                title=link.material.title,
                url=link.material.url,
                role=link.role,
                relevance_score=link.relevance_score,
            )
            for link in sorted(
                topic.material_links, key=lambda value: (value.role != "primary", -value.relevance_score)
            )
            if link.material is not None
        ],
    )


def topic_algorithm_read(algorithm: TopicAlgorithm) -> TopicAlgorithmRead:
    values = topic_algorithm_values(algorithm)
    return TopicAlgorithmRead(
        id=algorithm.id,
        name=algorithm.name,
        instructions=values["instructions"],
        max_topics=values["max_topics"],
        weights=values["weights"],
        is_builtin=algorithm.is_builtin,
        enabled=algorithm.enabled,
    )


def evidence_package_read(package: EvidencePackage) -> EvidencePackageRead:
    return EvidencePackageRead(
        id=package.id,
        article_id=package.article_id,
        status=package.status,
        version=package.version,
        summary=package.summary,
        sources=[
            EvidenceSourceRead(
                id=item.id,
                source_item_id=item.source_item_id,
                title=item.title,
                url=item.url,
                snapshot_hash=item.snapshot_hash,
                credibility=item.credibility,
            )
            for item in package.sources
        ],
        claims=[
            EvidenceClaimRead(
                id=item.id,
                source_id=item.source_id,
                claim_type=item.claim_type,
                statement=item.statement,
                status=item.status,
            )
            for item in package.claims
        ],
    )


def job_event_read(event: JobEvent) -> JobEventRead:
    return JobEventRead(
        id=event.id,
        job_id=event.job_id,
        event_type=event.event_type,
        step_name=event.step_name,
        status=event.status,
        payload=event.payload_json,
        created_at=event.created_at,
    )


def add_audit(
    db: Session,
    user: User | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            payload_json=payload or {},
        )
    )


def article_read(article: Article) -> ArticleRead:
    revisions = sorted(article.revisions, key=lambda item: item.version)
    latest_review = review_read(revisions[-1].review) if revisions and revisions[-1].review else None
    return ArticleRead(
        id=article.id,
        job_id=article.job_id,
        title=article.title,
        status=article.status,
        evidence=article.evidence_json,
        runtime_snapshot=article.runtime_snapshot_json,
        revisions=[ArticleRevisionRead.model_validate(item) for item in revisions],
        review=latest_review,
    )


def _run_background(job_id: str) -> None:
    from .db import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        model_id = (job.payload_json or {}).get("model_id") if job else None
        model = db.get(ModelConfig, model_id) if model_id else None
        run_job(db, job_id, provider_for(model))
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/auth/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=make_session(user.id),
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    response_user = user
    return response_user


@app.post("/api/v1/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/v1/auth/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@app.get("/api/v1/users", response_model=list[UserRead])
def list_users(_: User = Depends(require_roles("admin")), db: Session = Depends(get_db)) -> list[UserRead]:
    return [UserRead.model_validate(item) for item in db.scalars(select(User).order_by(User.created_at.asc())).all()]


@app.post("/api/v1/users", response_model=UserRead)
def add_user(
    payload: UserCreate,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> UserRead:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="邮箱已存在")
    created = User(email=email, password_hash=hash_password(payload.password), role=payload.role)
    db.add(created)
    db.flush()
    add_audit(db, user, "user.create", "user", created.id, {"role": created.role})
    db.commit()
    db.refresh(created)
    return UserRead.model_validate(created)


@app.get("/api/v1/sources/groups", response_model=list[SourceGroupRead])
def list_source_groups(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SourceGroupRead]:
    groups = db.scalars(select(SourceGroup).order_by(SourceGroup.name)).all()
    return [SourceGroupRead.model_validate(item) for item in groups]


@app.post("/api/v1/sources/groups", response_model=SourceGroupRead)
def add_source_group(
    payload: SourceGroupCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SourceGroupRead:
    if db.scalar(select(SourceGroup).where(SourceGroup.name == payload.name)):
        raise HTTPException(status_code=409, detail="来源分组已存在")
    group = SourceGroup(name=payload.name, description=payload.description, enabled=payload.enabled)
    db.add(group)
    add_audit(db, user, "source_group.create", "source_group", payload={"name": payload.name})
    db.commit()
    db.refresh(group)
    return SourceGroupRead.model_validate(group)


@app.put("/api/v1/sources/groups/{group_id}", response_model=SourceGroupRead)
def update_source_group(
    group_id: str,
    payload: SourceGroupUpdate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SourceGroupRead:
    group = db.get(SourceGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="来源分组不存在")
    if payload.name is not None:
        duplicate = db.scalar(select(SourceGroup).where(SourceGroup.name == payload.name, SourceGroup.id != group_id))
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="来源分组已存在")
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    if payload.enabled is not None:
        group.enabled = payload.enabled
    add_audit(db, user, "source_group.update", "source_group", group.id)
    db.commit()
    db.refresh(group)
    return SourceGroupRead.model_validate(group)


@app.delete("/api/v1/sources/groups/{group_id}", response_model=SourceGroupRead)
def disable_source_group(
    group_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SourceGroupRead:
    group = db.get(SourceGroup, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="来源分组不存在")
    group.enabled = False
    add_audit(db, user, "source_group.disable", "source_group", group.id)
    db.commit()
    db.refresh(group)
    return SourceGroupRead.model_validate(group)


@app.get("/api/v1/sources", response_model=list[SourceRead])
def list_sources(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SourceRead]:
    return [source_read(item) for item in db.scalars(select(Source).order_by(Source.created_at.desc())).all()]


@app.post("/api/v1/sources", response_model=SourceRead)
def add_source(
    payload: SourceCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Sessio…17564 tokens truncated…        config={"source": "environment", "readonly": True},
                capabilities={"draft": True, "publish": False},
                has_credentials=True,
            )
        )
    return accounts


@app.post("/api/v1/channels", response_model=ChannelAccountRead)
def add_channel_account(
    payload: ChannelAccountCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ChannelAccountRead:
    publish_enabled = bool(payload.config.get("publish_enabled", False))
    if publish_enabled and user is not None and user.role != "admin":
        raise HTTPException(status_code=403, detail="只有管理员可以开启公众号发布权限")
    account = ChannelAccount(
        channel_type=payload.channel_type,
        name=payload.name,
        encrypted_credentials=encrypt_secret(json.dumps({"app_id": payload.app_id, "app_secret": payload.app_secret})),
        enabled=payload.enabled,
        config_json=payload.config,
        capabilities_json={"draft": True, "publish": publish_enabled},
    )
    db.add(account)
    add_audit(db, user, "channel.create", "channel_account", payload=payload.config)
    db.commit()
    db.refresh(account)
    return channel_account_read(account)


@app.put("/api/v1/channels/{account_id}", response_model=ChannelAccountRead)
def update_channel_account(
    account_id: str,
    payload: ChannelAccountUpdate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ChannelAccountRead:
    account = db.get(ChannelAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="渠道账号不存在")
    if payload.name is not None:
        account.name = payload.name
    if payload.app_id or payload.app_secret:
        existing = (
            json.loads(decrypt_secret(account.encrypted_credentials) or "{}") if account.encrypted_credentials else {}
        )
        credentials = {
            "app_id": payload.app_id or existing.get("app_id", ""),
            "app_secret": payload.app_secret or existing.get("app_secret", ""),
        }
        account.encrypted_credentials = encrypt_secret(json.dumps(credentials))
    if payload.enabled is not None:
        account.enabled = payload.enabled
    if payload.config is not None:
        publish_enabled = bool(payload.config.get("publish_enabled", False))
        if publish_enabled and user is not None and user.role != "admin":
            raise HTTPException(status_code=403, detail="只有管理员可以开启公众号发布权限")
        account.config_json = payload.config
        account.capabilities_json = {
            **(account.capabilities_json or {}),
            "publish": publish_enabled,
        }
    add_audit(db, user, "channel.update", "channel_account", account.id)
    db.commit()
    db.refresh(account)
    return channel_account_read(account)


@app.delete("/api/v1/channels/{account_id}", response_model=ChannelAccountRead)
def disable_channel_account(
    account_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ChannelAccountRead:
    account = db.get(ChannelAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="渠道账号不存在")
    account.enabled = False
    add_audit(db, user, "channel.disable", "channel_account", account.id)
    db.commit()
    db.refresh(account)
    return channel_account_read(account)


@app.post("/api/v1/channels/accounts/{account_id}/test", response_model=WechatConnectionRead)
def test_channel_account(
    account_id: str,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> WechatConnectionRead:
    account = db.get(ChannelAccount, account_id)
    if not account or not account.enabled:
        raise HTTPException(status_code=404, detail="渠道账号不存在或已停用")
    try:
        with wechat_client_for_account(account) as client:
            client.test_connection()
    except (WeChatAPIError, ValueError) as exc:
        return WechatConnectionRead(configured=True, connected=False, message=str(exc))
    return WechatConnectionRead(configured=True, connected=True, message="微信公众号接口连接成功")


@app.post("/api/v1/channels/wechat/test", response_model=WechatConnectionRead)
def test_wechat_connection(
    _: User = Depends(require_roles("admin", "operator")),
) -> WechatConnectionRead:
    settings = get_settings()
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        return WechatConnectionRead(configured=False, connected=False, message="微信公众号凭证未配置")
    try:
        with WeChatClient.from_settings(settings) as client:
            client.test_connection()
    except (WeChatAPIError, ValueError) as exc:
        return WechatConnectionRead(configured=True, connected=False, message=str(exc))
    return WechatConnectionRead(configured=True, connected=True, message="微信公众号接口连接成功")


@app.post("/api/v1/channels/wechat/materials/thumb", response_model=WechatMaterialRead)
async def upload_wechat_thumb(
    file: UploadFile = File(...),
    account_id: str | None = None,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> WechatMaterialRead:
    content_type = file.content_type or "image/jpeg"
    if content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="微信公众号封面缩略图必须是 JPG 图片")
    content = await file.read()
    filename = (file.filename or "cover.jpg").replace("\\", "/").rsplit("/", 1)[-1] or "cover.jpg"
    settings = get_settings()
    account, _ = resolve_channel_account(db, account_id)
    if account is None and (not settings.wechat_app_id or not settings.wechat_app_secret):
        raise HTTPException(status_code=503, detail="微信公众号凭证未配置")
    try:
        client = wechat_client_for_account(account) if account else WeChatClient.from_settings(settings)
        with client as client:
            result = client.upload_permanent_material(
                content=content,
                filename=filename,
                content_type=content_type,
                material_type="thumb",
            )
    except WeChatAPIError as exc:
        raise HTTPException(
            status_code=409 if exc.result_unknown else 502,
            detail=wechat_error_detail(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WechatMaterialRead(media_id=result.media_id, url=result.url)


@app.get("/api/v1/channels/wechat/drafts/{media_id}")
def get_wechat_draft(
    media_id: str,
    account_id: str | None = None,
    _: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    account, _ = resolve_channel_account(db, account_id)
    if account is None and (not settings.wechat_app_id or not settings.wechat_app_secret):
        raise HTTPException(status_code=503, detail="微信公众号凭证未配置")
    try:
        client = wechat_client_for_account(account) if account else WeChatClient.from_settings(settings)
        with client as client:
            return client.get_draft(media_id)
    except (WeChatAPIError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/v1/channels/wechat/publish/{publish_id}")
def get_wechat_publish_status(
    publish_id: str,
    account_id: str,
    _: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
) -> dict:
    account = db.get(ChannelAccount, account_id)
    if not account or not account.enabled:
        raise HTTPException(status_code=404, detail="渠道账号不存在或已停用")
    try:
        with wechat_client_for_account(account) as client:
            return client.get_publish_status(publish_id)
    except (WeChatAPIError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post(
    "/api/v1/articles/{article_id}/revisions/{revision_id}/wechat-draft/update",
    response_model=PublicationRead,
)
def update_wechat_draft(
    article_id: str,
    revision_id: str,
    payload: WechatDraftCreate,
    _: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
) -> Publication:
    article = db.get(Article, article_id)
    revision = db.get(ArticleRevision, revision_id)
    if not article or not revision or revision.article_id != article_id:
        raise HTTPException(status_code=404, detail="文章修订版本不存在")
    job = db.get(Job, article.job_id)
    strategy = db.get(Strategy, job.strategy_id) if job else None
    strategy_channel_id = (strategy.config_json or {}).get("channel_account_id") if strategy else None
    selected_channel_id = payload.channel_account_id or strategy_channel_id
    account, channel_id = resolve_channel_account(db, selected_channel_id)
    create_key = f"{revision.id}:{channel_id}:create_draft"
    created = db.scalar(select(Publication).where(Publication.idempotency_key == create_key))
    if not created or not created.remote_id or created.status != "succeeded":
        raise HTTPException(status_code=404, detail="该修订版本还没有已创建的微信公众号草稿")
    if not article.title.strip() or not revision.rendered_html.strip():
        raise HTTPException(status_code=400, detail="文章标题或正文不能为空")

    update_key = f"{revision.id}:{channel_id}:update_draft"
    publication = db.scalar(select(Publication).where(Publication.idempotency_key == update_key))
    if publication is not None:
        if publication.status == "succeeded":
            return publication
        if publication.status in {"running", "unknown"}:
            raise HTTPException(status_code=409, detail="该修订版本已有未确认的微信公众号更新请求")
        publication.status = "running"
        publication.error = None
    else:
        publication = Publication(
            article_revision_id=revision.id,
            channel_account_id=channel_id,
            action="update_draft",
            status="running",
            idempotency_key=update_key,
            remote_id=created.remote_id,
        )
        db.add(publication)
    db.commit()
    db.refresh(publication)

    settings = get_settings()
    if account is None and (not settings.wechat_app_id or not settings.wechat_app_secret):
        raise HTTPException(status_code=503, detail="微信公众号凭证未配置")
    client = wechat_client_for_account(account) if account else WeChatClient.from_settings(settings)
    try:
        with client as client:
            channel_html, theme_snapshot = _channel_html(db, article, revision, payload.theme_id)
            client.update_draft(
                media_id=created.remote_id,
                article=client._article_payload(
                    title=article.title,
                    content_html=channel_html,
                    thumb_media_id=payload.thumb_media_id,
                    author=payload.author,
                    digest=payload.digest,
                    content_source_url=payload.content_source_url,
                    need_open_comment=payload.need_open_comment,
                    only_fans_can_comment=payload.only_fans_can_comment,
                ),
            )
    except WeChatAPIError as exc:
        publication.status = (
            "unknown" if exc.result_unknown else ("failed_retryable" if exc.retryable else "failed_terminal")
        )
        publication.error = str(exc)
        db.commit()
        raise HTTPException(status_code=409 if exc.result_unknown else 502, detail=str(exc)) from exc
    except ValueError as exc:
        publication.status = "failed_terminal"
        publication.error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    publication.status = "succeeded"
    publication.response_json = theme_snapshot
    db.commit()
    db.refresh(publication)
    return publication


def _poll_wechat_publication(publication_id: str, account_id: str, attempts: int = 12) -> None:
    """Poll WeChat's asynchronous publication result before marking an article published."""
    from .db import SessionLocal

    db = SessionLocal()
    try:
        for attempt in range(attempts):
            publication = db.get(Publication, publication_id)
            account = db.get(ChannelAccount, account_id)
            if publication is None or account is None or not publication.remote_id:
                return
            try:
                with wechat_client_for_account(account) as client:
                    result = client.get_publish_status(publication.remote_id)
            except WeChatAPIError as exc:
                publication.status = (
                    "unknown" if exc.result_unknown else ("failed_retryable" if exc.retryable else "failed_terminal")
                )
                publication.error = str(exc)
                db.commit()
                if not exc.retryable:
                    return
                time.sleep(5)
                continue

            publication.response_json = {**(publication.response_json or {}), "status_response": result}
            status = result.get("publish_status")
            if status in {0, "0"}:
                publication.status = "succeeded"
                publication.error = None
                revision = db.get(ArticleRevision, publication.article_revision_id)
                if revision is not None:
                    article = db.get(Article, revision.article_id)
                    if article is not None:
                        article.status = "published"
                db.commit()
                return
            if status in {2, "2", 3, "3"}:
                publication.status = "failed_terminal"
                publication.error = str(result.get("fail_reason") or result.get("errmsg") or "微信发布失败")[:2000]
                db.commit()
                return
            publication.status = "submitted"
            db.commit()
            if attempt < attempts - 1:
                time.sleep(5)
        publication.status = "unknown"
        publication.error = "微信发布状态在轮询窗口内未最终确认"
        db.commit()
    finally:
        db.close()


@app.post(
    "/api/v1/articles/{article_id}/revisions/{revision_id}/wechat-publish",
    response_model=PublicationRead,
)
def publish_wechat_article(
    article_id: str,
    revision_id: str,
    payload: WechatPublishRequest,
    user: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
    background: BackgroundTasks = None,
) -> Publication:
    article = db.get(Article, article_id)
    revision = db.get(ArticleRevision, revision_id)
    account = db.get(ChannelAccount, payload.channel_account_id)
    if not article or not revision or revision.article_id != article_id:
        raise HTTPException(status_code=404, detail="文章修订版本不存在")
    if not account or not account.enabled:
        raise HTTPException(status_code=404, detail="渠道账号不存在或已停用")
    if not (account.capabilities_json or {}).get("publish"):
        raise HTTPException(status_code=403, detail="该公众号账号没有发布权限，系统只允许创建草稿")
    create_key = f"{revision.id}:{account.id}:create_draft"
    created = db.scalar(select(Publication).where(Publication.idempotency_key == create_key))
    if not created or created.status != "succeeded" or not created.remote_id:
        raise HTTPException(status_code=409, detail="请先创建成功的微信公众号草稿")
    publish_key = f"{revision.id}:{account.id}:publish"
    publication = db.scalar(select(Publication).where(Publication.idempotency_key == publish_key))
    if publication is not None:
        if publication.status in {"submitted", "succeeded"}:
            return publication
        if publication.status in {"running", "unknown"}:
            raise HTTPException(status_code=409, detail="该文章已有未确认的发布请求")
        publication.status = "running"
        publication.error = None
    else:
        publication = Publication(
            article_revision_id=revision.id,
            channel_account_id=account.id,
            action="publish",
            status="running",
            idempotency_key=publish_key,
        )
        db.add(publication)
    db.commit()
    db.refresh(publication)
    try:
        with wechat_client_for_account(account) as client:
            result = client.submit_publish(created.remote_id)
    except WeChatAPIError as exc:
        publication.status = (
            "unknown" if exc.result_unknown else ("failed_retryable" if exc.retryable else "failed_terminal")
        )
        publication.error = str(exc)
        db.commit()
        raise HTTPException(
            status_code=409 if exc.result_unknown else (502 if exc.retryable else 400), detail=str(exc)
        ) from exc
    except ValueError as exc:
        publication.status = "failed_terminal"
        publication.error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    publication.status = "submitted"
    publication.remote_id = result.publish_id
    publication.response_json = {"publish_id": result.publish_id, "status": "submitted"}
    article.status = "publishing"
    add_audit(db, user, "article.publish.submitted", "publication", publication.id, {"channel_account_id": account.id})
    db.commit()
    if background is not None:
        background.add_task(_poll_wechat_publication, publication.id, account.id)
    db.refresh(publication)
    return publication


@app.post(
    "/api/v1/articles/{article_id}/revisions/{revision_id}/review",
    response_model=ReviewRead,
)
def review_article(
    article_id: str,
    revision_id: str,
    payload: ReviewCreate,
    background: BackgroundTasks,
    user: User = Depends(require_roles("admin", "reviewer")),
    db: Session = Depends(get_db),
) -> ReviewRead:
    article = db.get(Article, article_id)
    revision = db.get(ArticleRevision, revision_id)
    if not article or not revision or revision.article_id != article_id:
        raise HTTPException(status_code=404, detail="文章修订版本不存在")

    review = db.scalar(select(Review).where(Review.article_revision_id == revision_id))
    if review is None:
        review = Review(article_revision_id=revision_id, auto_result_json={})
        db.add(review)
    status_by_decision = {
        "approve": "approved",
        "reject": "rejected",
        "request_changes": "changes_requested",
    }
    review.status = status_by_decision[payload.decision]
    review.reviewer_id = user.id
    review.comment = payload.comment or None
    article.status = review.status

    job = db.get(Job, article.job_id)
    add_audit(
        db, user, f"article.review.{payload.decision}", "article_revision", revision.id, {"comment": payload.comment}
    )
    should_resume = payload.decision == "approve" and job is not None and job.status == "waiting_review"
    if should_resume and job is not None:
        job_payload = dict(job.payload_json or {})
        job_payload["approved_revision_id"] = revision.id
        job_payload.pop("pending_revision_id", None)
        job.payload_json = job_payload
        job.status = "queued"
        job.available_at = datetime.now(timezone.utc)
        job.lease_until = None
        job.current_step = "review"
    db.commit()
    db.refresh(review)
    if should_resume and job is not None:
        notify_wake()
        background.add_task(_run_background, job.id)
    return review_read(review)