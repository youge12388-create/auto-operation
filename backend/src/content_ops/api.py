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
    db: Session = Depends(get_db),
) -> SourceRead:
    if payload.group_id and not db.get(SourceGroup, payload.group_id):
        raise HTTPException(status_code=404, detail="来源分组不存在")
    source = Source(
        name=payload.name,
        source_type=payload.source_type,
        url=payload.url,
        group_name=payload.group_name,
        group_id=payload.group_id,
        enabled=payload.enabled,
        requires_review=payload.requires_review,
        config_json=payload.config,
    )
    db.add(source)
    add_audit(db, user, "source.create", "source", source.id)
    db.commit()
    db.refresh(source)
    return source_read(source)


@app.put("/api/v1/sources/{source_id}", response_model=SourceRead)
def update_source(
    source_id: str,
    payload: SourceCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SourceRead:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="信息源不存在")
    if payload.group_id and not db.get(SourceGroup, payload.group_id):
        raise HTTPException(status_code=404, detail="来源分组不存在")
    source.name = payload.name
    source.source_type = payload.source_type
    source.url = payload.url
    source.group_name = payload.group_name
    source.group_id = payload.group_id
    source.enabled = payload.enabled
    source.requires_review = payload.requires_review
    source.config_json = payload.config
    add_audit(db, user, "source.update", "source", source.id)
    db.commit()
    db.refresh(source)
    return source_read(source)


@app.delete("/api/v1/sources/{source_id}", response_model=SourceRead)
def disable_source(
    source_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SourceRead:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="信息源不存在")
    source.enabled = False
    add_audit(db, user, "source.disable", "source", source.id)
    db.commit()
    db.refresh(source)
    return source_read(source)


def material_category_read(db: Session, category: MaterialCategory) -> MaterialCategoryRead:
    try:
        material_count = db.scalar(
            select(func.count()).select_from(SourceItem).where(SourceItem.category_id == category.id)
        ) or 0
    except OperationalError as exc:
        raise_material_schema_error(exc)
        raise
    return MaterialCategoryRead(
        id=category.id,
        name=category.name,
        description=category.description,
        classification_instructions=category.classification_instructions,
        enabled=category.enabled,
        is_builtin=category.is_builtin,
        material_count=material_count,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@app.get("/api/v1/material-categories", response_model=list[MaterialCategoryRead])
def list_material_categories(
    include_disabled: bool = True,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MaterialCategoryRead]:
    query = select(MaterialCategory)
    if not include_disabled:
        query = query.where(MaterialCategory.enabled.is_(True))
    categories = db.scalars(query.order_by(MaterialCategory.enabled.desc(), MaterialCategory.name)).all()
    return [material_category_read(db, category) for category in categories]


@app.post("/api/v1/material-categories", response_model=MaterialCategoryRead)
def create_material_category(
    payload: MaterialCategoryCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialCategoryRead:
    name = payload.name.strip()
    duplicate = db.scalar(select(MaterialCategory).where(func.lower(MaterialCategory.name) == name.lower()))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="素材分类名称已存在")
    category = MaterialCategory(
        name=name,
        description=payload.description.strip(),
        classification_instructions=payload.classification_instructions.strip(),
        enabled=payload.enabled,
        is_builtin=False,
    )
    db.add(category)
    db.flush()
    add_audit(db, user, "material_category.create", "material_category", category.id)
    db.commit()
    db.refresh(category)
    return material_category_read(db, category)


@app.put("/api/v1/material-categories/{category_id}", response_model=MaterialCategoryRead)
def update_material_category(
    category_id: str,
    payload: MaterialCategoryUpdate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialCategoryRead:
    category = db.get(MaterialCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="素材分类不存在")
    if payload.name is not None:
        name = payload.name.strip()
        duplicate = db.scalar(
            select(MaterialCategory).where(
                func.lower(MaterialCategory.name) == name.lower(),
                MaterialCategory.id != category.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="素材分类名称已存在")
        category.name = name
    if payload.description is not None:
        category.description = payload.description.strip()
    if payload.classification_instructions is not None:
        category.classification_instructions = payload.classification_instructions.strip()
    if payload.enabled is not None:
        category.enabled = payload.enabled
    add_audit(db, user, "material_category.update", "material_category", category.id)
    db.commit()
    db.refresh(category)
    return material_category_read(db, category)


@app.delete("/api/v1/material-categories/{category_id}", response_model=MaterialCategoryRead)
def disable_material_category(
    category_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialCategoryRead:
    category = db.get(MaterialCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="素材分类不存在")
    category.enabled = False
    add_audit(db, user, "material_category.disable", "material_category", category.id)
    db.commit()
    db.refresh(category)
    return material_category_read(db, category)


@app.post("/api/v1/material-categories/{category_id}/restore", response_model=MaterialCategoryRead)
def restore_material_category(
    category_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialCategoryRead:
    category = db.get(MaterialCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="素材分类不存在")
    category.enabled = True
    add_audit(db, user, "material_category.restore", "material_category", category.id)
    db.commit()
    db.refresh(category)
    return material_category_read(db, category)


@app.post("/api/v1/sources/{source_id}/collect", response_model=SourceCollectRead)
def collect_source_now(
    source_id: str,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SourceCollectRead:
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="信息源不存在")
    try:
        translation_model = db.scalar(
            select(ModelConfig).where(ModelConfig.enabled.is_(True)).order_by(ModelConfig.created_at.desc())
        )
        translation_provider = provider_for(translation_model) if translation_model else None
        items = collect_source(db, source, translation_provider, translation_model)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"信息源采集失败：{exc}") from exc
    return SourceCollectRead(
        source_id=source.id,
        count=len(items),
        item_ids=[item.id for item in items],
        classified_count=sum(item.classification_status == "classified" for item in items),
        classification_failed_count=sum(item.classification_status == "failed" for item in items),
    )


@app.get("/api/v1/materials", response_model=list[MaterialRead])
def list_materials(
    triage_status: str | None = None,
    source_id: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    category_id: str | None = None,
) -> list[MaterialRead]:
    query = select(SourceItem).where(SourceItem.status == "verified")
    if triage_status:
        query = query.where(SourceItem.triage_status == triage_status)
    if source_id:
        query = query.where(SourceItem.source_id == source_id)
    if category_id:
        query = query.where(SourceItem.category_id == category_id)
    try:
        items = db.scalars(query.order_by(SourceItem.created_at.desc()).limit(300)).all()
    except OperationalError as exc:
        raise_material_schema_error(exc)
        raise
    return [material_read(item) for item in items]


@app.post("/api/v1/materials/classify", response_model=MaterialClassifyRead)
def classify_materials_now(
    payload: MaterialClassifyRequest,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialClassifyRead:
    query = select(SourceItem).where(SourceItem.status == "verified")
    if payload.material_ids:
        query = query.where(SourceItem.id.in_(list(dict.fromkeys(payload.material_ids))))
    else:
        statuses = ["pending", "unclassified"]
        if payload.retry_failed:
            statuses.append("failed")
        query = query.where(SourceItem.classification_status.in_(statuses))
    candidates = db.scalars(query.order_by(SourceItem.created_at.desc()).limit(300)).all()
    if not candidates:
        return MaterialClassifyRead(
            candidate_count=0,
            classified_count=0,
            failed_count=0,
            message="当前没有等待分类的素材。",
        )
    categories = db.scalars(
        select(MaterialCategory).where(MaterialCategory.enabled.is_(True)).order_by(MaterialCategory.name)
    ).all()
    model = db.scalar(
        select(ModelConfig).where(ModelConfig.enabled.is_(True)).order_by(ModelConfig.created_at.desc())
    )
    try:
        result = run_material_classification(
            db,
            None,
            candidates,
            categories,
            provider_for(model) if model is not None else None,
            model,
        )
        add_audit(
            db,
            user,
            "material.classify",
            "source_item",
            payload.material_ids[0] if len(payload.material_ids) == 1 else None,
            result,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"素材分类失败：{exc}") from exc
    return MaterialClassifyRead(
        **result,
        message=(
            f"AI 已分类 {result['classified_count']} 条素材，{result['failed_count']} 条需要重试或人工纠正。"
        ),
    )


@app.put("/api/v1/materials/{material_id}/category", response_model=MaterialRead)
def assign_material_category(
    material_id: str,
    payload: MaterialCategoryAssign,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialRead:
    material = db.get(SourceItem, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    category = db.get(MaterialCategory, payload.category_id) if payload.category_id else None
    if payload.category_id and category is None:
        raise HTTPException(status_code=404, detail="素材分类不存在")
    if category is not None and not category.enabled:
        raise HTTPException(status_code=409, detail="素材分类已停用，请先恢复后再使用")
    material.category_id = category.id if category is not None else None
    material.classification_status = "classified" if category is not None else "unclassified"
    material.classification_source = "manual"
    material.classification_confidence = 100.0 if category is not None else None
    material.classification_reason = "人工纠正" if category is not None else "人工取消分类"
    material.classification_error = None
    add_audit(
        db,
        user,
        "material.category_assign",
        "source_item",
        material.id,
        {"category_id": material.category_id},
    )
    db.commit()
    db.refresh(material)
    return material_read(material)


@app.post("/api/v1/materials/curate", response_model=MaterialCurateRead)
def curate_materials_now(
    payload: MaterialCurateRequest,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialCurateRead:
    strategy = db.get(Strategy, payload.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="内容策略不存在")
    query = select(SourceItem).where(
        SourceItem.status == "verified",
        SourceItem.triage_status.in_(["inbox", "selected"]),
    )
    if payload.material_ids:
        query = query.where(SourceItem.id.in_(payload.material_ids))
    candidates = db.scalars(query.order_by(SourceItem.created_at.desc()).limit(payload.limit)).all()
    if not candidates:
        return MaterialCurateRead(
            candidate_count=0,
            selected_count=0,
            selected_ids=[],
            selected_titles=[],
            message="当前没有等待 AI 精选的素材。",
        )
    model_id = model_id_for_stage(strategy.config_json or {}, "writing")
    model = db.get(ModelConfig, model_id) if model_id else None
    if model is None:
        model = db.scalar(
            select(ModelConfig).where(ModelConfig.enabled.is_(True)).order_by(ModelConfig.created_at.desc())
        )
    if model is None or not model.enabled:
        raise HTTPException(status_code=400, detail="请先在模型中心配置一个启用的模型，再进行 AI 精选")
    try:
        selected = run_material_curation(
            db,
            None,
            strategy,
            candidates,
            provider_for(model),
            model,
            payload.limit,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"AI 精选失败：{exc}") from exc
    return MaterialCurateRead(
        candidate_count=len(candidates),
        selected_count=len(selected),
        selected_ids=[item["id"] for item in selected],
        selected_titles=[item["title"] for item in selected],
        message=f"AI 已审核 {len(candidates)} 条素材，精选 {len(selected)} 条进入已保留素材。",
    )

@app.get("/api/v1/materials/{material_id}", response_model=MaterialDetailRead)
def get_material(
    material_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaterialDetailRead:
    material = db.get(SourceItem, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    return material_read(material, include_content=True)


@app.post("/api/v1/materials/{material_id}/triage", response_model=MaterialRead)
def triage_material(
    material_id: str,
    payload: MaterialTriage,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialRead:
    material = db.get(SourceItem, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    if material.triage_status == "used":
        if payload.decision == "save":
            return material_read(material)
        raise HTTPException(status_code=409, detail="A material already used for writing cannot be reopened here")
    material.triage_status = {
        "save": "selected",
        "ignore": "ignored",
        "reopen": "inbox",
    }[payload.decision]
    add_audit(db, user, f"material.{payload.decision}", "source_item", material.id)
    db.commit()
    db.refresh(material)
    return material_read(material)


@app.post("/api/v1/materials/manual", response_model=MaterialRead)
def add_manual_material(
    payload: ManualMaterialCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> MaterialRead:
    source = db.scalar(
        select(Source).where(Source.source_type == "manual", Source.name == payload.source_name.strip())
    )
    if source is None:
        source = Source(
            name=payload.source_name.strip(),
            source_type="manual",
            url="",
            config_json={},
        )
        db.add(source)
        db.flush()
    content = payload.content.strip()
    material = SourceItem(
        source_id=source.id,
        title=payload.title.strip(),
        url="",
        canonical_url=f"manual://{source.id}/{uuid4()}",
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        status="verified",
        triage_status="selected",
    )
    db.add(material)
    db.flush()
    categories = db.scalars(
        select(MaterialCategory).where(MaterialCategory.enabled.is_(True)).order_by(MaterialCategory.name)
    ).all()
    model = db.scalar(
        select(ModelConfig).where(ModelConfig.enabled.is_(True)).order_by(ModelConfig.created_at.desc())
    )
    run_material_classification(
        db,
        None,
        [material],
        categories,
        provider_for(model) if model is not None else None,
        model,
    )
    add_audit(db, user, "material.manual_create", "source_item", material.id, {"source_id": source.id})
    db.commit()
    db.refresh(material)
    return material_read(material)


@app.post("/api/v1/materials/{material_id}/topics", response_model=TopicRead)
def create_topic_from_material(
    material_id: str,
    payload: MaterialTopicCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> TopicRead:
    material = db.get(SourceItem, material_id)
    if material is None or material.status != "verified":
        raise HTTPException(status_code=404, detail="Verified material not found")
    strategy = db.get(Strategy, payload.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Content strategy not found")
    existing = db.scalar(
        select(Topic).where(
            Topic.strategy_id == strategy.id,
            Topic.source_item_id == material.id,
            Topic.status.in_(("candidate", "accepted", "writing")),
        )
    )
    if existing is not None:
        return topic_read(existing)
    topic = Topic(
        strategy_id=strategy.id,
        source_item_id=material.id,
        title=(payload.title or material.title).strip(),
        status="candidate",
        score=0,
        rationale="Created by an operator from a collected material",
    )
    db.add(topic)
    db.flush()
    db.add(
        TopicMaterial(
            topic_id=topic.id,
            source_item_id=material.id,
            role="primary",
            relevance_score=100,
        )
    )
    material.triage_status = "selected"
    add_audit(
        db,
        user,
        "material.create_topic",
        "source_item",
        material.id,
        {"topic_id": topic.id, "strategy_id": strategy.id},
    )
    db.commit()
    db.refresh(topic)
    return topic_read(topic)


@app.post("/api/v1/topics/from-materials", response_model=TopicRead)
def create_topic_from_materials(
    payload: MaterialBatchTopicCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> TopicRead:
    strategy = db.get(Strategy, payload.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Content strategy not found")
    material_ids = list(dict.fromkeys(payload.material_ids))
    materials_by_id = {
        item.id: item
        for item in db.scalars(
            select(SourceItem).where(SourceItem.id.in_(material_ids), SourceItem.status == "verified")
        ).all()
    }
    if len(materials_by_id) != len(material_ids):
        raise HTTPException(status_code=409, detail="One or more selected materials are no longer available")
    materials = [materials_by_id[item_id] for item_id in material_ids]
    topic = Topic(
        strategy_id=strategy.id,
        source_item_id=materials[0].id,
        title=(payload.title or materials[0].title).strip(),
        status="candidate",
        score=0,
        rationale=f"Created by an operator from {len(materials)} retained materials",
    )
    db.add(topic)
    db.flush()
    for index, material in enumerate(materials):
        db.add(
            TopicMaterial(
                topic_id=topic.id,
                source_item_id=material.id,
                role="primary" if index == 0 else "supporting",
                relevance_score=100 if index == 0 else 90,
            )
        )
        material.triage_status = "selected"
    add_audit(
        db,
        user,
        "material.create_topic_batch",
        "topic",
        topic.id,
        {"material_ids": material_ids, "strategy_id": strategy.id},
    )
    db.commit()
    db.refresh(topic)
    return topic_read(topic)


@app.post("/api/v1/topics/{topic_id}/start-writing", response_model=JobRead)
def start_topic_writing(
    topic_id: str,
    background: BackgroundTasks,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
    payload: TopicStartWriting = TopicStartWriting(),
) -> Job:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status not in {"accepted", "writing"}:
        raise HTTPException(status_code=409, detail="Accept the topic before starting writing")
    materials = [link.material for link in topic.material_links if link.material is not None]
    if not materials and topic.source_item_id:
        legacy_material = db.get(SourceItem, topic.source_item_id)
        materials = [legacy_material] if legacy_material is not None else []
    if not materials or any(material.status != "verified" for material in materials):
        raise HTTPException(status_code=409, detail="One or more selected materials are no longer available")
    strategy = db.get(Strategy, topic.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Content strategy not found")
    execution_config_override: dict[str, Any] | None = None
    if payload.disable_writing_skill:
        execution_config_override = {"skill_by_stage": {}, "skill_ids": []}
    elif payload.writing_skill_id:
        skill = db.get(Skill, payload.writing_skill_id)
        if skill is None or skill.status != "published" or skill.skill_type != "writing":
            raise HTTPException(status_code=400, detail="写作 Skill 不存在或未发布")
        execution_config_override = {"skill_by_stage": {"writing": skill.id}, "skill_ids": []}
    job = create_job(
        db,
        strategy,
        f"write-topic:{topic.id}",
        payload={"mode": "write_topic", "topic_id": topic.id},
        execution_config_override=execution_config_override,
    )
    topic.status = "writing"
    for material in materials:
        material.triage_status = "used"
    add_audit(
        db,
        user,
        "topic.start_writing",
        "topic",
        topic.id,
        {"job_id": job.id, "material_ids": [material.id for material in materials]},
    )
    db.commit()
    notify_wake()
    background.add_task(_run_background, job.id)
    return job


@app.get("/api/v1/strategies", response_model=list[StrategyRead])
def list_strategies(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[StrategyRead]:
    return [strategy_read(item) for item in db.scalars(select(Strategy).order_by(Strategy.created_at.desc())).all()]


@app.post("/api/v1/strategies", response_model=StrategyRead)
def add_strategy(
    payload: StrategyCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> StrategyRead:
    try:
        schedule = normalize_schedule(payload.schedule)
        strategy_config = validate_strategy_definition(payload.config)
        validate_strategy_definition_references(db, strategy_config)
    except (StrategyConfigError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    strategy = Strategy(
        name=payload.name,
        objective=payload.objective,
        schedule=schedule,
        automation_level=payload.automation_level,
        enabled=payload.enabled,
        config_json=strategy_config,
    )
    db.add(strategy)
    db.flush()
    db.add(
        StrategyVersion(
            strategy_id=strategy.id,
            version=strategy.version,
            name=strategy.name,
            objective=strategy.objective,
            schedule=strategy.schedule,
            automation_level=strategy.automation_level,
            config_json=strategy.config_json,
        )
    )
    add_audit(db, user, "strategy.create", "strategy", strategy.id)
    db.commit()
    db.refresh(strategy)
    return strategy_read(strategy)


@app.put("/api/v1/strategies/{strategy_id}", response_model=StrategyRead)
def update_strategy(
    strategy_id: str,
    payload: StrategyCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> StrategyRead:
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="内容策略不存在")
    try:
        strategy_config = validate_strategy_definition(payload.config)
        schedule = normalize_schedule(payload.schedule)
        validate_strategy_definition_references(db, strategy_config)
    except (StrategyConfigError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    strategy.name = payload.name
    strategy.objective = payload.objective
    strategy.schedule = schedule
    strategy.automation_level = payload.automation_level
    strategy.enabled = payload.enabled
    strategy.config_json = strategy_config
    strategy.version += 1
    add_audit(db, user, "strategy.update", "strategy", strategy.id)
    db.add(
        StrategyVersion(
            strategy_id=strategy.id,
            version=strategy.version,
            name=strategy.name,
            objective=strategy.objective,
            schedule=strategy.schedule,
            automation_level=strategy.automation_level,
            config_json=strategy.config_json,
        )
    )
    add_audit(db, user, "strategy.create", "strategy", strategy.id)
    db.commit()
    db.refresh(strategy)
    return strategy_read(strategy)


@app.post("/api/v1/strategies/{strategy_id}/scan", response_model=JobRead)
def scan_strategy_for_topics(
    strategy_id: str,
    background: BackgroundTasks,
    payload: TopicScanRequest | None = None,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    strategy = db.get(Strategy, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Content strategy not found")
    if payload and payload.topic_algorithm_id:
        algorithm = db.get(TopicAlgorithm, payload.topic_algorithm_id)
        if algorithm is None or not algorithm.enabled:
            raise HTTPException(status_code=404, detail="选题算法不存在或已停用")
    else:
        algorithm = ensure_builtin_topic_algorithm(db)
    key = f"scan:{strategy.id}:{datetime.now(timezone.utc).isoformat()}"
    try:
        job = create_job(
            db,
            strategy,
            key,
            payload={"mode": "scan"},
            execution_config_override={"topic_algorithm": topic_algorithm_values(algorithm)},
            runtime_snapshot_extra={"topic_algorithm": topic_algorithm_snapshot(algorithm)},
        )
    except StrategyConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        raise_job_schema_error(exc)
    notify_wake()
    background.add_task(_run_background, job.id)
    return job


@app.post("/api/v1/strategies/{strategy_id}/run", response_model=JobRead)
def run_strategy(
    strategy_id: str,
    background: BackgroundTasks,
    payload: StrategyRunRequest | None = None,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="内容策略不存在")
    key = f"manual:{strategy.id}:{datetime.now(timezone.utc).isoformat()}"
    try:
        job = create_job(
            db,
            strategy,
            key,
            payload={"mode": "automation"},
            combination_id=payload.combination_id if payload else None,
        )
    except StrategyConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        raise_job_schema_error(exc)
    notify_wake()
    background.add_task(_run_background, job.id)
    return job


@app.get("/api/v1/skills", response_model=list[SkillRead])
def list_skills(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SkillRead]:
    return [
        SkillRead(
            id=item.id,
            name=item.name,
            skill_type=item.skill_type,
            version=item.version,
            status=item.status,
            manifest=item.manifest_json,
        )
        for item in db.scalars(select(Skill).order_by(Skill.created_at.desc())).all()
    ]


@app.post("/api/v1/skills/import", response_model=SkillRead)
async def import_skill(
    package: UploadFile = File(...),
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SkillRead:
    try:
        result = validate_skill_package(await package.read())
    except SkillPackageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    manifest = result["manifest"]
    skill = db.scalar(select(Skill).where(Skill.name == manifest["name"]))
    if skill is None:
        skill = Skill(
            name=manifest["name"],
            skill_type=manifest["type"],
            version=manifest["version"],
            manifest_json=manifest,
            prompt=result["prompt"],
            status="draft",
        )
        db.add(skill)
        db.flush()
    else:
        skill.skill_type = manifest["type"]
        skill.version = manifest["version"]
        skill.manifest_json = manifest
        skill.prompt = result["prompt"]
        skill.status = "draft"
    version = db.scalar(
        select(SkillVersion).where(SkillVersion.skill_id == skill.id, SkillVersion.version == manifest["version"])
    )
    if version is None:
        version = SkillVersion(
            skill_id=skill.id,
            version=manifest["version"],
            skill_type=manifest["type"],
            status="draft",
            manifest_json=manifest,
            prompt=result["prompt"],
        )
        db.add(version)
    else:
        version.skill_type = manifest["type"]
        version.manifest_json = manifest
        version.prompt = result["prompt"]
        version.status = "draft"
    db.commit()
    db.refresh(skill)
    return SkillRead(
        id=skill.id,
        name=skill.name,
        skill_type=skill.skill_type,
        version=skill.version,
        status=skill.status,
        manifest=skill.manifest_json,
    )


@app.get("/api/v1/skills/{skill_id}/versions", response_model=list[SkillVersionRead])
def list_skill_versions(
    skill_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SkillVersionRead]:
    if not db.get(Skill, skill_id):
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return [
        SkillVersionRead(
            id=item.id,
            skill_id=item.skill_id,
            version=item.version,
            skill_type=item.skill_type,
            status=item.status,
            manifest=item.manifest_json,
        )
        for item in db.scalars(
            select(SkillVersion).where(SkillVersion.skill_id == skill_id).order_by(SkillVersion.version.desc())
        ).all()
    ]


@app.post("/api/v1/skills/{skill_id}/publish", response_model=SkillRead)
def publish_skill(
    skill_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SkillRead:
    skill = db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    skill.status = "published"
    version = db.scalar(
        select(SkillVersion).where(
            SkillVersion.skill_id == skill.id,
            SkillVersion.version == skill.version,
        )
    )
    if version:
        version.status = "published"
    add_audit(db, user, "skill.publish", "skill", skill.id, {"version": skill.version})
    db.commit()
    return SkillRead(
        id=skill.id,
        name=skill.name,
        skill_type=skill.skill_type,
        version=skill.version,
        status=skill.status,
        manifest=skill.manifest_json,
    )


@app.post("/api/v1/skills/{skill_id}/disable", response_model=SkillRead)
def disable_skill(
    skill_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SkillRead:
    skill = db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    skill.status = "disabled"
    version = db.scalar(
        select(SkillVersion).where(
            SkillVersion.skill_id == skill.id,
            SkillVersion.version == skill.version,
        )
    )
    if version:
        version.status = "disabled"
    add_audit(db, user, "skill.disable", "skill", skill.id, {"version": skill.version})
    db.commit()
    return SkillRead(
        id=skill.id,
        name=skill.name,
        skill_type=skill.skill_type,
        version=skill.version,
        status=skill.status,
        manifest=skill.manifest_json,
    )


@app.post("/api/v1/skills/{skill_id}/rollback/{version}", response_model=SkillRead)
def rollback_skill(
    skill_id: str,
    version: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> SkillRead:
    skill = db.get(Skill, skill_id)
    selected = db.scalar(select(SkillVersion).where(SkillVersion.skill_id == skill_id, SkillVersion.version == version))
    if not skill or not selected:
        raise HTTPException(status_code=404, detail="Skill 版本不存在")
    skill.version = selected.version
    skill.skill_type = selected.skill_type
    skill.manifest_json = selected.manifest_json
    skill.prompt = selected.prompt
    skill.status = "published" if selected.status == "published" else "draft"
    add_audit(db, user, "skill.rollback", "skill", skill.id, {"version": version})
    db.commit()
    db.refresh(skill)
    return SkillRead(
        id=skill.id,
        name=skill.name,
        skill_type=skill.skill_type,
        version=skill.version,
        status=skill.status,
        manifest=skill.manifest_json,
    )


@app.get("/api/v1/models", response_model=list[ModelRead])
def list_models(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ModelRead]:
    return [model_read(item) for item in db.scalars(select(ModelConfig).order_by(ModelConfig.created_at.desc())).all()]


@app.post("/api/v1/models", response_model=ModelRead)
def add_model(
    payload: ModelCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ModelRead:
    model = ModelConfig(
        provider=payload.provider,
        name=payload.name,
        api_base_url=payload.api_base_url,
        encrypted_api_key=encrypt_secret(payload.api_key),
        enabled=payload.enabled,
        config_json=payload.config,
    )
    db.add(model)
    db.flush()
    add_audit(db, user, "model.create", "model", model.id)
    db.commit()
    db.refresh(model)
    return model_read(model)


@app.put("/api/v1/models/{model_id}", response_model=ModelRead)
def update_model(
    model_id: str,
    payload: ModelUpdate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ModelRead:
    model = db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    if payload.provider is not None:
        model.provider = payload.provider
    if payload.name is not None:
        model.name = payload.name
    if payload.api_base_url is not None:
        model.api_base_url = payload.api_base_url
    if payload.api_key:
        model.encrypted_api_key = encrypt_secret(payload.api_key)
    if payload.enabled is not None:
        model.enabled = payload.enabled
    if payload.config is not None:
        model.config_json = payload.config
    add_audit(db, user, "model.update", "model", model.id)
    db.commit()
    db.refresh(model)
    return model_read(model)


@app.delete("/api/v1/models/{model_id}")
def delete_model(
    model_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    model = db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    blockers = _model_delete_blockers(db, model_id)
    if blockers:
        names = "、".join(blockers[:3])
        suffix = "等" if len(blockers) > 3 else ""
        raise HTTPException(
            status_code=409,
            detail=f"该模型仍被{names}{suffix}引用。请先替换模型或等待任务结束后再删除。",
        )
    db.delete(model)
    add_audit(db, user, "model.delete", "model", model_id)
    db.commit()
    return {"deleted": True}


def disable_model(
    model_id: str,
    user: User | None,
    db: Session,
) -> ModelRead:
    """Compatibility helper for legacy callers; browser clients use PUT enabled=false."""
    model = db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    model.enabled = False
    add_audit(db, user, "model.disable", "model", model.id)
    db.commit()
    db.refresh(model)
    return model_read(model)

@app.post("/api/v1/models/{model_id}/test", response_model=ModelTestRead)
def model_connection_test(
    model_id: str,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ModelTestRead:
    model = db.get(ModelConfig, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    try:
        provider_for(model).complete(CompletionRequest(system="只返回 OK。", user="连接测试", max_tokens=4))
    except Exception as exc:
        return ModelTestRead(ok=False, message=str(exc))
    return ModelTestRead(ok=True, message="模型连接成功")


@app.get("/api/v1/topic-algorithms", response_model=list[TopicAlgorithmRead])
def list_topic_algorithms(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TopicAlgorithmRead]:
    ensure_builtin_topic_algorithm(db)
    algorithms = db.scalars(
        select(TopicAlgorithm).order_by(TopicAlgorithm.is_builtin.desc(), TopicAlgorithm.created_at)
    ).all()
    return [topic_algorithm_read(item) for item in algorithms]


@app.post("/api/v1/topic-algorithms", response_model=TopicAlgorithmRead)
def create_topic_algorithm(
    payload: TopicAlgorithmCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> TopicAlgorithmRead:
    if db.scalar(select(TopicAlgorithm).where(TopicAlgorithm.name == payload.name.strip())):
        raise HTTPException(status_code=409, detail="同名选题算法已存在")
    try:
        values = normalize_topic_algorithm(
            instructions=payload.instructions,
            max_topics=payload.max_topics,
            weights=payload.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    algorithm = TopicAlgorithm(
        name=payload.name.strip(),
        instructions=values["instructions"],
        max_topics=values["max_topics"],
        weights_json=values["weights"],
    )
    db.add(algorithm)
    add_audit(db, user, "topic_algorithm.create", "topic_algorithm", algorithm.id)
    db.commit()
    db.refresh(algorithm)
    return topic_algorithm_read(algorithm)


@app.put("/api/v1/topic-algorithms/{algorithm_id}", response_model=TopicAlgorithmRead)
def update_topic_algorithm(
    algorithm_id: str,
    payload: TopicAlgorithmUpdate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> TopicAlgorithmRead:
    algorithm = db.get(TopicAlgorithm, algorithm_id)
    if algorithm is None:
        raise HTTPException(status_code=404, detail="选题算法不存在")
    if algorithm.is_builtin:
        raise HTTPException(status_code=409, detail="默认推荐算法不可编辑")
    data = payload.model_dump(exclude_unset=True)
    name = str(data.get("name", algorithm.name)).strip()
    if name != algorithm.name and db.scalar(select(TopicAlgorithm).where(TopicAlgorithm.name == name)):
        raise HTTPException(status_code=409, detail="同名选题算法已存在")
    try:
        values = normalize_topic_algorithm(
            instructions=str(data.get("instructions", algorithm.instructions)),
            max_topics=int(data.get("max_topics", algorithm.max_topics)),
            weights=data.get("weights", algorithm.weights_json),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    algorithm.name = name
    algorithm.instructions = values["instructions"]
    algorithm.max_topics = values["max_topics"]
    algorithm.weights_json = values["weights"]
    if "enabled" in data:
        algorithm.enabled = bool(data["enabled"])
    add_audit(db, user, "topic_algorithm.update", "topic_algorithm", algorithm.id)
    db.commit()
    db.refresh(algorithm)
    return topic_algorithm_read(algorithm)


@app.delete("/api/v1/topic-algorithms/{algorithm_id}", response_model=TopicAlgorithmRead)
def delete_topic_algorithm(
    algorithm_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> TopicAlgorithmRead:
    algorithm = db.get(TopicAlgorithm, algorithm_id)
    if algorithm is None:
        raise HTTPException(status_code=404, detail="选题算法不存在")
    if algorithm.is_builtin:
        raise HTTPException(status_code=409, detail="默认推荐算法不可删除")
    result = topic_algorithm_read(algorithm)
    add_audit(db, user, "topic_algorithm.delete", "topic_algorithm", algorithm.id)
    db.delete(algorithm)
    db.commit()
    return result


@app.get("/api/v1/topics", response_model=list[TopicRead])
def list_topics(
    status: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TopicRead]:
    query = select(Topic).order_by(Topic.created_at.desc())
    if status:
        query = query.where(Topic.status == status)
    return [topic_read(item) for item in db.scalars(query.limit(200)).all()]


@app.post("/api/v1/topics", response_model=TopicRead)
def create_topic(
    payload: TopicCreate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> TopicRead:
    if not db.get(Strategy, payload.strategy_id):
        raise HTTPException(status_code=404, detail="策略不存在")
    topic = Topic(
        strategy_id=payload.strategy_id,
        title=payload.title,
        status="candidate",
        score=payload.score,
        rationale=payload.rationale,
    )
    db.add(topic)
    add_audit(db, user, "topic.create", "topic")
    db.commit()
    db.refresh(topic)
    return topic_read(topic)


@app.post("/api/v1/topics/{topic_id}/decision", response_model=TopicRead)
def decide_topic(
    topic_id: str,
    payload: TopicDecision,
    user: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
) -> TopicRead:
    topic = db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="选题不存在")
    topic.status = {"accept": "accepted", "reject": "rejected", "merge": "merged"}[payload.decision]
    if payload.decision in {"reject", "merge"}:
        materials = [link.material for link in topic.material_links if link.material is not None]
        if not materials and topic.source_item_id:
            legacy_material = db.get(SourceItem, topic.source_item_id)
            materials = [legacy_material] if legacy_material is not None else []
        for material in materials:
            if material.triage_status == "selected":
                material.triage_status = "inbox"
    if payload.comment:
        topic.rationale = f"{topic.rationale}\n{payload.comment}".strip()
    add_audit(db, user, f"topic.{payload.decision}", "topic", topic.id)
    db.commit()
    db.refresh(topic)
    return topic_read(topic)


@app.get("/api/v1/articles/{article_id}/evidence", response_model=EvidencePackageRead)
def get_article_evidence(
    article_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EvidencePackageRead:
    if not db.get(Article, article_id):
        raise HTTPException(status_code=404, detail="文章不存在")
    package = db.scalar(select(EvidencePackage).where(EvidencePackage.article_id == article_id))
    if not package:
        raise HTTPException(status_code=404, detail="事实包不存在")
    return evidence_package_read(package)


@app.get("/api/v1/jobs/{job_id}/events", response_model=list[JobEventRead])
def list_job_events(
    job_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[JobEventRead]:
    if not db.get(Job, job_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    events = db.scalars(
        select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.created_at.asc(), JobEvent.id.asc())
    ).all()
    return [job_event_read(item) for item in events]


@app.get("/api/v1/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[AuditLogRead]:
    return [
        AuditLogRead(
            id=item.id,
            user_id=item.user_id,
            action=item.action,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            payload=item.payload_json,
            ip_address=item.ip_address,
            created_at=item.created_at,
        )
        for item in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()
    ]


@app.get("/api/v1/jobs", response_model=list[JobRead])
def list_jobs(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[JobRead]:
    return list(db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all())


@app.post("/api/v1/jobs", response_model=JobRead)
def add_job(
    payload: JobCreate,
    background: BackgroundTasks,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    strategy = db.get(Strategy, payload.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="内容策略不存在")
    key = payload.idempotency_key or f"manual:{strategy.id}:{datetime.now(timezone.utc).isoformat()}"
    try:
        job = create_job(
            db,
            strategy,
            key,
            payload={"model_id": payload.model_id} if payload.model_id else {},
            combination_id=payload.combination_id,
        )
    except StrategyConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        raise_job_schema_error(exc)
    notify_wake()
    background.add_task(_run_background, job.id)
    return job


@app.post("/api/v1/jobs/{job_id}/retry", response_model=JobRead)
def retry_job(
    job_id: str,
    background: BackgroundTasks,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status not in {"failed_retryable", "failed_terminal"}:
        raise HTTPException(status_code=409, detail="只有失败任务可以重试")
    job.status = "queued"
    job.attempt_count = 0
    job.available_at = datetime.now(timezone.utc)
    job.lease_until = None
    job.started_at = None
    job.completed_at = None
    job.duration_ms = 0
    job.last_error = None
    for attempt in range(3):
        try:
            db.commit()
            break
        except OperationalError as exc:
            db.rollback()
            if attempt == 2:
                raise HTTPException(status_code=503, detail="数据库正忙，请稍后重试") from exc
            time.sleep(0.5 * (attempt + 1))
    notify_wake()
    background.add_task(_run_background, job.id)
    return job


@app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    job_id: str,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in {"succeeded", "canceled"}:
        raise HTTPException(status_code=409, detail="任务当前状态不可取消")
    job.status = "canceled"
    job.lease_until = None
    job.available_at = None
    job.completed_at = datetime.now(timezone.utc)
    if job.started_at is not None:
        started = job.started_at if job.started_at.tzinfo is not None else job.started_at.replace(tzinfo=timezone.utc)
        job.duration_ms = max(0, int((job.completed_at - started).total_seconds() * 1000))
    db.commit()
    return job


@app.get("/api/v1/articles", response_model=list[ArticleRead])
def list_articles(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ArticleRead]:
    return [article_read(item) for item in db.scalars(select(Article).order_by(Article.created_at.desc())).all()]


@app.get("/api/v1/articles/{article_id}", response_model=ArticleRead)
def get_article(article_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ArticleRead:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return article_read(article)


@app.delete("/api/v1/articles/{article_id}", response_model=ArticleRead)
def archive_article(
    article_id: str,
    user: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
) -> ArticleRead:
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    if article.status not in {"approved", "drafted", "wechat_draft", "published"}:
        raise HTTPException(status_code=409, detail="只有成稿库中的文章可以归档")
    previous_status = article.status
    article.status = "archived"
    add_audit(
        db,
        user,
        "article.archive",
        "article",
        article.id,
        {"previous_status": previous_status, "remote_content_preserved": True},
    )
    db.commit()
    db.refresh(article)
    return article_read(article)


@app.get("/api/v1/publications", response_model=list[PublicationRead])
def list_publications(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Publication]:
    return list(db.scalars(select(Publication).order_by(Publication.created_at.desc()).limit(200)).all())


@app.post("/api/v1/articles/{article_id}/revisions", response_model=ArticleRevisionRead)
def add_revision(
    article_id: str,
    payload: ArticleRevisionCreate,
    user: User = Depends(require_roles("admin", "operator", "reviewer")),
    db: Session = Depends(get_db),
) -> ArticleRevision:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    latest = db.scalar(
        select(ArticleRevision).where(ArticleRevision.article_id == article_id).order_by(ArticleRevision.version.desc())
    )
    revision = ArticleRevision(
        article_id=article_id,
        version=(latest.version + 1 if latest else 1),
        content_markdown=payload.content_markdown,
        rendered_html=MarkdownIt("commonmark", {"breaks": True}).render(payload.content_markdown),
        created_by=user.id,
    )
    if payload.title is not None:
        article.title = payload.title.strip()
    article.status = "waiting_review"
    db.add(revision)
    db.flush()
    db.add(Review(article_revision_id=revision.id, status="pending", auto_result_json={}))
    job = db.get(Job, article.job_id)
    if job is not None and job.status not in {"canceled", "failed_terminal"}:
        job_payload = dict(job.payload_json or {})
        job_payload["pending_revision_id"] = revision.id
        job_payload.pop("approved_revision_id", None)
        job.payload_json = job_payload
        job.status = "waiting_review"
        job.current_step = "review"
        job.available_at = None
        job.lease_until = None
        for step_name in ("render", "draft"):
            step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == step_name))
            if step is None:
                db.add(JobStep(job_id=job.id, step_name=step_name, status="queued"))
            else:
                step.status = "queued"
                step.output_json = {}
                step.error = None
                step.completed_at = None
    db.commit()
    db.refresh(revision)
    return revision


@app.get("/api/v1/themes", response_model=list[ThemeRead])
def list_themes(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ThemeRead]:
    ensure_builtin_themes(db)
    db.commit()
    return [theme_read(item) for item in db.scalars(select(Theme).order_by(Theme.created_at.asc())).all()]


def _ai_layout_preview(
    db: Session,
    article: Article,
    revision: ArticleRevision,
    theme: Theme,
    version: ThemeVersion,
) -> str:
    from .themes import extract_html, layout_instruction, validate_gzh_html

    execution: dict[str, Any] = {}
    if article.job_id:
        job = db.get(Job, article.job_id)
        if job is not None:
            snapshot = (job.payload_json or {}).get("runtime_snapshot") or {}
            execution = snapshot.get("execution_config") or {}
    model_id = model_id_for_stage(execution, "render", None) or execution.get("default_model_id")
    model = db.get(ModelConfig, model_id) if isinstance(model_id, str) else None
    if model is None or not model.enabled:
        raise HTTPException(
            status_code=400,
            detail="AI 排版预览需要策略配置 render 阶段模型（model_by_stage.render 或 default_model_id）",
        )
    provider = provider_for(model)
    response = provider.complete(
        CompletionRequest(
            system=layout_instruction(theme, version),
            user=f"文章标题：{article.title}\n\n文章正文（Markdown）：\n{revision.content_markdown}",
            max_tokens=8000,
        )
    )
    html = extract_html(response.text)
    errors = validate_gzh_html(html)
    if errors:
        raise HTTPException(status_code=502, detail=f"AI 排版输出不合规：{', '.join(errors[:4])}")
    return html


@app.post(
    "/api/v1/articles/{article_id}/revisions/{revision_id}/themes/{theme_id}/preview",
    response_model=ThemePreviewRead,
)
def preview_article_theme(
    article_id: str,
    revision_id: str,
    theme_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    mode: str = "deterministic",
) -> ThemePreviewRead:
    ensure_builtin_themes(db)
    db.flush()
    article = db.get(Article, article_id)
    revision = db.get(ArticleRevision, revision_id)
    theme = db.get(Theme, theme_id)
    if not article or not revision or revision.article_id != article_id:
        raise HTTPException(status_code=404, detail="文章修订版本不存在")
    if not theme:
        raise HTTPException(status_code=404, detail="排版主题不存在")
    if not theme.enabled:
        raise HTTPException(status_code=400, detail="排版主题已停用")
    version = db.scalar(
        select(ThemeVersion).where(
            ThemeVersion.theme_id == theme.id,
            ThemeVersion.version == theme.current_version,
        )
    )
    if version is None:
        raise HTTPException(status_code=500, detail="排版主题版本不存在")
    if mode == "ai":
        html = _ai_layout_preview(db, article, revision, theme, version)
    elif mode == "deterministic":
        rendered = render_revision(db, revision, theme)
        html = rendered.html
    else:
        raise HTTPException(status_code=400, detail="mode 只能是 deterministic 或 ai")
    db.commit()
    return ThemePreviewRead(theme=theme_read(theme), theme_version=version.version, html=html)


@app.post("/api/v1/themes", response_model=ThemeRead)
def add_theme(
    payload: ThemeCreate, user: User = Depends(require_roles("admin", "operator")), db: Session = Depends(get_db)
) -> ThemeRead:
    if db.scalar(select(Theme).where((Theme.slug == payload.slug) | (Theme.name == payload.name))):
        raise HTTPException(status_code=409, detail="排版主题名称或标识已存在")
    theme = Theme(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        enabled=payload.enabled,
        is_builtin=False,
        current_version=1,
    )
    db.add(theme)
    db.flush()
    db.add(ThemeVersion(theme_id=theme.id, version=1, tokens_json=payload.tokens, css_text=payload.css))
    add_audit(db, user, "theme.create", "theme", theme.id)
    db.commit()
    db.refresh(theme)
    return theme_read(theme)


@app.put("/api/v1/themes/{theme_id}", response_model=ThemeRead)
def update_theme(
    theme_id: str,
    payload: ThemeUpdate,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ThemeRead:
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="排版主题不存在")
    if payload.name is not None:
        theme.name = payload.name
    if payload.description is not None:
        theme.description = payload.description
    if payload.enabled is not None:
        theme.enabled = payload.enabled
    if payload.tokens is not None or payload.css is not None:
        current = db.scalar(
            select(ThemeVersion).where(ThemeVersion.theme_id == theme.id, ThemeVersion.version == theme.current_version)
        )
        next_version = theme.current_version + 1
        db.add(
            ThemeVersion(
                theme_id=theme.id,
                version=next_version,
                tokens_json=payload.tokens if payload.tokens is not None else (current.tokens_json if current else {}),
                css_text=payload.css if payload.css is not None else (current.css_text if current else ""),
            )
        )
        theme.current_version = next_version
    add_audit(db, user, "theme.update", "theme", theme.id)
    db.commit()
    db.refresh(theme)
    return theme_read(theme)


@app.post("/api/v1/themes/{theme_id}/copy", response_model=ThemeRead)
def copy_theme(
    theme_id: str,
    payload: ThemeCopy,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ThemeRead:
    source = db.get(Theme, theme_id)
    if not source:
        raise HTTPException(status_code=404, detail="排版主题不存在")
    if db.scalar(select(Theme).where((Theme.slug == payload.slug) | (Theme.name == payload.name))):
        raise HTTPException(status_code=409, detail="排版主题名称或标识已存在")
    current = db.scalar(
        select(ThemeVersion).where(ThemeVersion.theme_id == source.id, ThemeVersion.version == source.current_version)
    )
    copied = Theme(
        name=payload.name,
        slug=payload.slug,
        description=source.description,
        enabled=True,
        is_builtin=False,
        current_version=1,
    )
    db.add(copied)
    db.flush()
    db.add(
        ThemeVersion(
            theme_id=copied.id,
            version=1,
            tokens_json=current.tokens_json if current else {},
            css_text=current.css_text if current else "",
        )
    )
    add_audit(db, user, "theme.copy", "theme", copied.id, {"source_theme_id": source.id})
    db.commit()
    db.refresh(copied)
    return theme_read(copied)


@app.delete("/api/v1/themes/{theme_id}", response_model=ThemeRead)
def disable_theme(
    theme_id: str, user: User = Depends(require_roles("admin", "operator")), db: Session = Depends(get_db)
) -> ThemeRead:
    theme = db.get(Theme, theme_id)
    if not theme:
        raise HTTPException(status_code=404, detail="排版主题不存在")
    theme.enabled = False
    add_audit(db, user, "theme.disable", "theme", theme.id)
    db.commit()
    db.refresh(theme)
    return theme_read(theme)


@app.get("/api/v1/calendar", response_model=list[CalendarItemRead])
def calendar(
    start: datetime | None = None,
    end: datetime | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarItemRead]:
    query = select(Job).order_by(Job.created_at.asc())
    if start:
        query = query.where(Job.created_at >= start)
    if end:
        query = query.where(Job.created_at <= end)
    jobs = db.scalars(query.limit(500)).all()
    articles = {item.job_id: item for item in db.scalars(select(Article)).all()}
    return [
        CalendarItemRead(
            job_id=job.id,
            strategy_id=job.strategy_id,
            article_id=articles[job.id].id if job.id in articles else None,
            title=articles[job.id].title if job.id in articles else "",
            status=job.status,
            scheduled_at=job.created_at,
        )
        for job in jobs
    ]


@app.get("/api/v1/dashboard")
def dashboard(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "sources": db.scalar(select(func.count()).select_from(Source)) or 0,
        "strategies": db.scalar(select(func.count()).select_from(Strategy)) or 0,
        "jobs": db.scalar(select(func.count()).select_from(Job)) or 0,
        "articles": db.scalar(select(func.count()).select_from(Article)) or 0,
    }


@app.get("/api/v1/events/jobs")
async def job_events(request: Request, _: User = Depends(get_current_user)) -> StreamingResponse:
    async def stream():
        from .db import SessionLocal

        seen: set[str] = set()
        while not await request.is_disconnected():
            db = SessionLocal()
            try:
                events = db.scalars(
                    select(JobEvent).order_by(JobEvent.created_at.asc(), JobEvent.id.asc()).limit(500)
                ).all()
            finally:
                db.close()
            emitted = False
            for event in events:
                if event.id in seen:
                    continue
                seen.add(event.id)
                emitted = True
                payload = json.dumps(job_event_read(event).model_dump(mode="json"), default=str)
                yield f"data: {payload}\n\n"
            if not emitted:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream")


def _channel_html(
    db: Session,
    article: Article,
    revision: ArticleRevision,
    theme_id: str | None,
) -> tuple[str, dict[str, object]]:
    selected_theme_id = theme_id or (article.runtime_snapshot_json.get("theme") or {}).get("id")
    if not selected_theme_id:
        default_theme = db.scalar(select(Theme).where(Theme.enabled.is_(True)).order_by(Theme.created_at.asc()))
        if default_theme is not None:
            selected_theme_id = default_theme.id
        else:
            return revision.rendered_html, {}
    theme = db.get(Theme, selected_theme_id)
    if theme is None:
        raise HTTPException(status_code=404, detail="排版主题不存在")
    try:
        rendered = render_revision(db, revision, theme)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return rendered.html, {"theme_id": theme.id, "theme_version": theme.current_version}


@app.post(
    "/api/v1/articles/{article_id}/revisions/{revision_id}/wechat-draft",
    response_model=PublicationRead,
)
def create_wechat_draft(
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
    if not article.title.strip():
        raise HTTPException(status_code=400, detail="文章标题不能为空")
    if not revision.rendered_html.strip():
        raise HTTPException(status_code=400, detail="文章还没有可发布的 HTML 正文")
    if article.status not in {"approved", "drafted", "wechat_draft"}:
        raise HTTPException(status_code=409, detail="文章尚未通过人工审核")

    settings = get_settings()
    job = db.get(Job, article.job_id)
    strategy = db.get(Strategy, job.strategy_id) if job else None
    strategy_channel_id = (strategy.config_json or {}).get("channel_account_id") if strategy else None
    selected_channel_id = payload.channel_account_id or strategy_channel_id
    account, channel_id = resolve_channel_account(db, selected_channel_id)
    if account is None and (not settings.wechat_app_id or not settings.wechat_app_secret):
        raise HTTPException(status_code=503, detail="微信公众号凭证未配置")

    idempotency_key = f"{revision.id}:{channel_id}:create_draft"
    publication = db.scalar(select(Publication).where(Publication.idempotency_key == idempotency_key))
    if publication is not None:
        if publication.status == "succeeded":
            return publication
        if publication.status in {"running", "unknown"}:
            raise HTTPException(status_code=409, detail="该修订版本已有未确认的微信公众号草稿请求")
        publication.status = "running"
        publication.error = None
    else:
        publication = Publication(
            article_revision_id=revision.id,
            channel_account_id=channel_id,
            action="create_draft",
            status="running",
            idempotency_key=idempotency_key,
        )
        db.add(publication)
    db.commit()
    db.refresh(publication)

    channel_html, theme_snapshot = _channel_html(db, article, revision, payload.theme_id)
    client = wechat_client_for_account(account) if account else WeChatClient.from_settings(settings)
    try:
        with client as client:
            result = client.create_draft(
                title=article.title,
                content_html=channel_html,
                thumb_media_id=payload.thumb_media_id,
                author=payload.author,
                digest=payload.digest,
                content_source_url=payload.content_source_url,
                need_open_comment=payload.need_open_comment,
                only_fans_can_comment=payload.only_fans_can_comment,
            )
    except WeChatAPIError as exc:
        publication.status = (
            "unknown" if exc.result_unknown else ("failed_retryable" if exc.retryable else "failed_terminal")
        )
        publication.error = str(exc)
        db.commit()
        status_code = 409 if exc.result_unknown else (502 if exc.retryable else 400)
        raise HTTPException(status_code=status_code, detail=wechat_error_detail(exc)) from exc
    except ValueError as exc:
        publication.status = "failed_terminal"
        publication.error = str(exc)
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    publication.status = "succeeded"
    publication.remote_id = result.media_id
    publication.response_json = {"media_id": result.media_id, **theme_snapshot}
    article.status = "wechat_draft"
    db.commit()
    db.refresh(publication)
    return publication


@app.get("/api/v1/channels", response_model=list[ChannelAccountRead])
def list_channel_accounts(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChannelAccountRead]:
    accounts = [
        channel_account_read(item)
        for item in db.scalars(select(ChannelAccount).order_by(ChannelAccount.created_at.desc())).all()
    ]
    settings = get_settings()
    if settings.wechat_app_id and settings.wechat_app_secret:
        accounts.append(
            ChannelAccountRead(
                id=ENV_CHANNEL_ID,
                channel_type="wechat",
                name="环境默认公众号",
                enabled=True,
                config={"source": "environment", "readonly": True},
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
