from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone

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
from sqlalchemy.orm import Session

from .db import get_db
from .ingestion import collect_source
from .models import (
    Article,
    ArticleRevision,
    AuditLog,
    ChannelAccount,
    EvidencePackage,
    Job,
    JobEvent,
    JobStep,
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
    TopicScore,
    User,
)
from .providers import CompletionRequest, provider_for
from .queueing import wake_job
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
    ThemeCopy,
    ThemeCreate,
    ThemePreviewRead,
    ThemeRead,
    ThemeUpdate,
    TopicCreate,
    TopicDecision,
    TopicRead,
    TopicScoreRead,
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
from .strategy_config import StrategyConfigError, validate_strategy_config, validate_strategy_references
from .themes import ensure_builtin_themes, render_revision
from .wechat import WeChatAPIError, WeChatClient
from .workflow import create_job, run_job

app = FastAPI(title="AI 自动内容运营系统", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        items = collect_source(db, source)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"信息源采集失败：{exc}") from exc
    return SourceCollectRead(source_id=source.id, count=len(items), item_ids=[item.id for item in items])


@app.get("/api/v1/materials", response_model=list[MaterialRead])
def list_materials(
    triage_status: str | None = None,
    source_id: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MaterialRead]:
    query = select(SourceItem).where(SourceItem.status == "verified")
    if triage_status:
        query = query.where(SourceItem.triage_status == triage_status)
    if source_id:
        query = query.where(SourceItem.source_id == source_id)
    items = db.scalars(query.order_by(SourceItem.created_at.desc()).limit(300)).all()
    return [material_read(item) for item in items]


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
        raise HTTPException(status_code=409, detail="A material already used for writing cannot be reopened here")
    material.triage_status = "ignored" if payload.decision == "ignore" else "inbox"
    add_audit(db, user, f"material.{payload.decision}", "source_item", material.id)
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
        score=78,
        rationale="Created by an operator from a collected material",
    )
    db.add(topic)
    db.flush()
    for dimension, score, rationale in (
        ("recency", 80, "Collected material is available for review"),
        ("source_quality", 80, "Source material passed collection validation"),
        ("strategy_fit", 75, "Operator selected this material for the strategy"),
    ):
        db.add(TopicScore(topic_id=topic.id, dimension=dimension, score=score, rationale=rationale))
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


@app.post("/api/v1/topics/{topic_id}/start-writing", response_model=JobRead)
def start_topic_writing(
    topic_id: str,
    background: BackgroundTasks,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.status not in {"accepted", "writing"}:
        raise HTTPException(status_code=409, detail="Accept the topic before starting writing")
    if not topic.source_item_id:
        raise HTTPException(status_code=409, detail="The topic has no selected source material")
    material = db.get(SourceItem, topic.source_item_id)
    if material is None or material.status != "verified":
        raise HTTPException(status_code=409, detail="The selected source material is no longer available")
    strategy = db.get(Strategy, topic.strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail="Content strategy not found")
    job = create_job(db, strategy, f"write-topic:{topic.id}", payload={"mode": "write_topic", "topic_id": topic.id})
    topic.status = "writing"
    material.triage_status = "used"
    add_audit(db, user, "topic.start_writing", "topic", topic.id, {"job_id": job.id, "source_item_id": material.id})
    db.commit()
    wake_job(job.id)
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
        strategy_config = validate_strategy_config(payload.config)
        validate_strategy_references(db, strategy_config)
    except StrategyConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    strategy = Strategy(
        name=payload.name,
        objective=payload.objective,
        schedule=payload.schedule,
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
        strategy_config = validate_strategy_config(payload.config)
        validate_strategy_references(db, strategy_config)
    except StrategyConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    strategy.name = payload.name
    strategy.objective = payload.objective
    strategy.schedule = payload.schedule
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


@app.post("/api/v1/strategies/{strategy_id}/run", response_model=JobRead)
def run_strategy(
    strategy_id: str,
    background: BackgroundTasks,
    _: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> Job:
    strategy = db.get(Strategy, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="内容策略不存在")
    key = f"manual:{strategy.id}:{datetime.now(timezone.utc).isoformat()}"
    job = create_job(db, strategy, key, payload={"mode": "scan"})
    wake_job(job.id)
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


@app.delete("/api/v1/models/{model_id}", response_model=ModelRead)
def disable_model(
    model_id: str,
    user: User = Depends(require_roles("admin", "operator")),
    db: Session = Depends(get_db),
) -> ModelRead:
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
    if topic.source_item_id and payload.decision in {"reject", "merge"}:
        material = db.get(SourceItem, topic.source_item_id)
        if material is not None and material.triage_status == "selected":
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
    job = create_job(db, strategy, key, payload={"model_id": payload.model_id} if payload.model_id else {})
    wake_job(job.id)
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
    db.commit()
    wake_job(job.id)
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
    article.status = "edited"
    db.add(revision)
    db.flush()
    db.add(Review(article_revision_id=revision.id, status="pending", auto_result_json={}))
    job = db.get(Job, article.job_id)
    if job is not None and job.status not in {"canceled", "failed_terminal"}:
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
    rendered = render_revision(db, revision, theme)
    version = db.scalar(select(ThemeVersion).where(ThemeVersion.id == rendered.theme_version_id))
    if version is None:
        raise HTTPException(status_code=500, detail="排版主题版本不存在")
    db.commit()
    return ThemePreviewRead(theme=theme_read(theme), theme_version=version.version, html=rendered.html)


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
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
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
        raise HTTPException(status_code=409 if exc.result_unknown else 502, detail=str(exc)) from exc
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
                    "unknown"
                    if exc.result_unknown
                    else ("failed_retryable" if exc.retryable else "failed_terminal")
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
) -> Review:
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
        job.status = "queued"
        job.available_at = datetime.now(timezone.utc)
        job.lease_until = None
        job.current_step = "review"
    db.commit()
    db.refresh(review)
    if should_resume and job is not None:
        wake_job(job.id)
        background.add_task(_run_background, job.id)
    return review
