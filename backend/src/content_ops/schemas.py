from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=200)
    role: Literal["admin", "operator", "reviewer"] = "operator"

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str


class SourceGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    enabled: bool = True


class SourceGroupRead(SourceGroupCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str


class SourceGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None

class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(default="rss", pattern="^(rss|url|manual)$")
    url: str = ""
    group_name: str = "default"
    group_id: str | None = None
    enabled: bool = True
    requires_review: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class SourceRead(SourceCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    last_success_at: datetime | None = None
    last_error: str | None = None


class MaterialRead(BaseModel):
    id: str
    source_id: str
    source_name: str
    title: str
    url: str
    content_excerpt: str
    published_at: datetime | None = None
    created_at: datetime | None = None
    triage_status: Literal["inbox", "selected", "ignored", "used"]


class MaterialDetailRead(MaterialRead):
    content: str


class MaterialTopicCreate(BaseModel):
    strategy_id: str
    title: str | None = Field(default=None, max_length=500)


class MaterialTriage(BaseModel):
    decision: Literal["ignore", "reopen"]


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1)
    schedule: str = "manual"
    automation_level: str = Field(default="L2", pattern="^L[1-4]$")
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class StrategyRead(StrategyCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int


class SkillRead(BaseModel):
    id: str
    name: str
    skill_type: str
    version: str
    status: str
    manifest: dict[str, Any]


class ModelCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    api_base_url: str | None = None
    api_key: str | None = None
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ModelUpdate(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    api_base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None

class ModelRead(BaseModel):
    id: str
    provider: str
    name: str
    api_base_url: str | None
    enabled: bool
    config: dict[str, Any]
    has_api_key: bool


class JobCreate(BaseModel):
    strategy_id: str
    idempotency_key: str | None = None
    model_id: str | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    strategy_id: str
    status: str
    current_step: str | None
    attempt_count: int
    max_attempts: int
    available_at: datetime | None = None
    lease_until: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int
    idempotency_key: str
    last_error: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ArticleRevisionCreate(BaseModel):
    content_markdown: str = Field(min_length=1)


class ArticleRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    article_id: str
    version: int
    content_markdown: str
    rendered_html: str
    created_by: str | None


class ArticleRead(BaseModel):
    id: str
    job_id: str
    title: str
    status: str
    evidence: dict[str, Any]
    runtime_snapshot: dict[str, Any]
    revisions: list[ArticleRevisionRead]
    review: ReviewRead | None = None


class WechatDraftCreate(BaseModel):
    channel_account_id: str | None = None
    theme_id: str | None = None
    thumb_media_id: str = Field(min_length=1, max_length=255)
    author: str = Field(default="", max_length=20)
    digest: str = Field(default="", max_length=120)
    content_source_url: str = Field(default="", max_length=2000)
    need_open_comment: bool = False
    only_fans_can_comment: bool = False


class WechatPublishRequest(BaseModel):
    channel_account_id: str = Field(min_length=1, max_length=100)

class PublicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    article_revision_id: str
    channel_account_id: str
    action: str
    status: str
    remote_id: str | None
    error: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

class WechatConnectionRead(BaseModel):
    configured: bool
    connected: bool
    message: str


class WechatMaterialRead(BaseModel):
    media_id: str
    url: str | None = None

class ReviewCreate(BaseModel):
    decision: Literal["approve", "reject", "request_changes"]
    comment: str = Field(default="", max_length=2000)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    article_revision_id: str
    status: str
    auto_result: dict[str, Any]
    reviewer_id: str | None
    comment: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None

class SourceCollectRead(BaseModel):
    source_id: str
    count: int
    item_ids: list[str]

class SkillVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    skill_id: str
    version: str
    skill_type: str
    status: str
    manifest: dict[str, Any]


class ModelTestRead(BaseModel):
    ok: bool
    message: str
class ThemeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern="^[a-z0-9-]+$")
    description: str = Field(default="", max_length=500)
    enabled: bool = True
    tokens: dict[str, Any] = Field(default_factory=dict)
    css: str = ""


class ThemeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None
    tokens: dict[str, Any] | None = None
    css: str | None = None


class ThemeCopy(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern="^[a-z0-9-]+$")

class ThemeRead(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    enabled: bool
    is_builtin: bool
    current_version: int
    tokens: dict[str, Any]


class ThemePreviewRead(BaseModel):
    theme: ThemeRead
    theme_version: int
    html: str
class TopicScoreRead(BaseModel):
    id: str
    topic_id: str
    dimension: str
    score: float
    rationale: str


class TopicRead(BaseModel):
    id: str
    strategy_id: str
    job_id: str | None
    source_item_id: str | None
    title: str
    status: str
    score: float
    rationale: str
    scores: list[TopicScoreRead]


class EvidenceSourceRead(BaseModel):
    id: str
    source_item_id: str | None
    title: str
    url: str
    snapshot_hash: str
    credibility: float


class EvidenceClaimRead(BaseModel):
    id: str
    source_id: str | None
    claim_type: str
    statement: str
    status: str


class EvidencePackageRead(BaseModel):
    id: str
    article_id: str
    status: str
    version: int
    summary: str
    sources: list[EvidenceSourceRead]
    claims: list[EvidenceClaimRead]


class JobEventRead(BaseModel):
    id: str
    job_id: str
    event_type: str
    step_name: str | None
    status: str | None
    payload: dict[str, Any]
    created_at: datetime | None = None


class AuditLogRead(BaseModel):
    id: str
    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    payload: dict[str, Any]
    ip_address: str | None
    created_at: datetime | None = None
class TopicCreate(BaseModel):
    strategy_id: str
    title: str = Field(min_length=1, max_length=500)
    rationale: str = ""
    score: float = Field(default=0.0, ge=0, le=100)


class TopicDecision(BaseModel):
    decision: Literal["accept", "reject", "merge"]
    comment: str = Field(default="", max_length=2000)
class ChannelAccountCreate(BaseModel):
    channel_type: Literal["wechat"] = "wechat"
    name: str = Field(min_length=1, max_length=200)
    app_id: str = Field(min_length=1, max_length=100)
    app_secret: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ChannelAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    app_id: str | None = Field(default=None, min_length=1, max_length=100)
    app_secret: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    config: dict[str, Any] | None = None

class ChannelAccountRead(BaseModel):
    id: str
    channel_type: str
    name: str
    enabled: bool
    config: dict[str, Any]
    capabilities: dict[str, Any]
    has_credentials: bool
class CalendarItemRead(BaseModel):
    job_id: str
    strategy_id: str
    article_id: str | None
    title: str
    status: str
    scheduled_at: datetime | None