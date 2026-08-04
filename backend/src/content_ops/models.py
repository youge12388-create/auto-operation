from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="operator")
    is_active: Mapped[bool] = mapped_column(default=True)


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))

class ChannelAccount(TimestampMixin, Base):
    __tablename__ = "channel_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    channel_type: Mapped[str] = mapped_column(String(32), default="wechat")
    name: Mapped[str] = mapped_column(String(200), unique=True)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    capabilities_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

class SourceGroup(TimestampMixin, Base):
    __tablename__ = "source_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(default=True)

    sources: Mapped[list["Source"]] = relationship(back_populates="group")

class Source(TimestampMixin, Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(32), default="rss")
    url: Mapped[str] = mapped_column(String(2000))
    group_name: Mapped[str] = mapped_column(String(100), default="default")
    group_id: Mapped[str | None] = mapped_column(ForeignKey("source_groups.id"), index=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    requires_review: Mapped[bool] = mapped_column(default=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    group: Mapped[SourceGroup | None] = relationship(back_populates="sources")
    items: Mapped[list[SourceItem]] = relationship(back_populates="source")


class SourceItem(TimestampMixin, Base):
    __tablename__ = "source_items"
    __table_args__ = (UniqueConstraint("source_id", "canonical_url", name="uq_source_item_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000))
    canonical_url: Mapped[str] = mapped_column(String(2000), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="verified")
    triage_status: Mapped[str] = mapped_column(String(32), default="inbox", index=True)

    source: Mapped[Source] = relationship(back_populates="items")


class Strategy(TimestampMixin, Base):
    __tablename__ = "content_strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    objective: Mapped[str] = mapped_column(Text)
    schedule: Mapped[str] = mapped_column(String(100), default="manual")
    automation_level: Mapped[str] = mapped_column(String(8), default="L2")
    enabled: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class StrategyVersion(TimestampMixin, Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("content_strategies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(Text)
    schedule: Mapped[str] = mapped_column(String(100))
    automation_level: Mapped[str] = mapped_column(String(8))
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Skill(TimestampMixin, Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    skill_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prompt: Mapped[str] = mapped_column(Text)


class SkillVersion(TimestampMixin, Base):
    __tablename__ = "skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version", name="uq_skill_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"), index=True)
    version: Mapped[str] = mapped_column(String(32))
    skill_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prompt: Mapped[str] = mapped_column(Text)


class ModelConfig(TimestampMixin, Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    api_base_url: Mapped[str | None] = mapped_column(String(2000))
    encrypted_api_key: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("content_strategies.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("automation_jobs.id"), index=True)
    source_item_id: Mapped[str | None] = mapped_column(ForeignKey("source_items.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="candidate", index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    duplicate_group: Mapped[str | None] = mapped_column(String(100))

    scores: Mapped[list[TopicScore]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TopicScore(TimestampMixin, Base):
    __tablename__ = "topic_scores"
    __table_args__ = (UniqueConstraint("topic_id", "dimension", name="uq_topic_score_dimension"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id"), index=True)
    dimension: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")

    topic: Mapped[Topic] = relationship(back_populates="scores")

class ModelCallLog(TimestampMixin, Base):
    __tablename__ = "model_call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("automation_jobs.id"), index=True)
    article_id: Mapped[str | None] = mapped_column(ForeignKey("articles.id"), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(default=0.0)
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text)

class Job(TimestampMixin, Base):
    __tablename__ = "automation_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_job_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    strategy_id: Mapped[str] = mapped_column(ForeignKey("content_strategies.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    current_step: Mapped[str | None] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)

    steps: Mapped[list[JobStep]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (UniqueConstraint("job_id", "step_name", name="uq_job_step"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("automation_jobs.id"), index=True)
    step_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[Job] = relationship(back_populates="steps")


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("automation_jobs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    step_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class Article(TimestampMixin, Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("automation_jobs.id"), unique=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(32), default="generating")
    strategy_version: Mapped[int] = mapped_column(Integer, default=1)
    model_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    skill_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    runtime_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    revisions: Mapped[list[ArticleRevision]] = relationship(back_populates="article", cascade="all, delete-orphan")


class EvidencePackage(TimestampMixin, Base):
    __tablename__ = "evidence_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(Text, default="")

    sources: Mapped[list[EvidenceSource]] = relationship(back_populates="package", cascade="all, delete-orphan")
    claims: Mapped[list[EvidenceClaim]] = relationship(back_populates="package", cascade="all, delete-orphan")


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evidence_package_id: Mapped[str] = mapped_column(ForeignKey("evidence_packages.id"), index=True)
    source_item_id: Mapped[str | None] = mapped_column(ForeignKey("source_items.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2000))
    snapshot_hash: Mapped[str] = mapped_column(String(64), default="")
    snapshot_text: Mapped[str] = mapped_column(Text, default="")
    credibility: Mapped[float] = mapped_column(Float, default=0.0)

    package: Mapped[EvidencePackage] = relationship(back_populates="sources")


class EvidenceClaim(Base):
    __tablename__ = "evidence_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    evidence_package_id: Mapped[str] = mapped_column(ForeignKey("evidence_packages.id"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("evidence_sources.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(32))
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="confirmed")

    package: Mapped[EvidencePackage] = relationship(back_populates="claims")

class ArticleRevision(Base):
    __tablename__ = "article_revisions"
    __table_args__ = (UniqueConstraint("article_id", "version", name="uq_article_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content_markdown: Mapped[str] = mapped_column(Text)
    rendered_html: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    article: Mapped[Article] = relationship(back_populates="revisions")
    review: Mapped[Review | None] = relationship(back_populates="revision", uselist=False, cascade="all, delete-orphan")
    rendered_versions: Mapped[list[RenderedVersion]] = relationship(
        back_populates="article_revision", cascade="all, delete-orphan"
    )


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("article_revision_id", name="uq_review_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_revision_id: Mapped[str] = mapped_column(ForeignKey("article_revisions.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    auto_result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reviewer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)

    revision: Mapped[ArticleRevision] = relationship(back_populates="review")


class Theme(TimestampMixin, Base):
    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    is_builtin: Mapped[bool] = mapped_column(default=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)

    versions: Mapped[list[ThemeVersion]] = relationship(back_populates="theme", cascade="all, delete-orphan")


class ThemeVersion(TimestampMixin, Base):
    __tablename__ = "theme_versions"
    __table_args__ = (UniqueConstraint("theme_id", "version", name="uq_theme_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    theme_id: Mapped[str] = mapped_column(ForeignKey("themes.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    tokens_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    css_text: Mapped[str] = mapped_column(Text, default="")

    theme: Mapped[Theme] = relationship(back_populates="versions")


class RenderedVersion(TimestampMixin, Base):
    __tablename__ = "rendered_versions"
    __table_args__ = (UniqueConstraint("article_revision_id", "theme_version_id", name="uq_rendered_revision_theme"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_revision_id: Mapped[str] = mapped_column(ForeignKey("article_revisions.id"), index=True)
    theme_version_id: Mapped[str] = mapped_column(ForeignKey("theme_versions.id"), index=True)
    html: Mapped[str] = mapped_column(Text)

    article_revision: Mapped[ArticleRevision] = relationship(back_populates="rendered_versions")
    theme_version: Mapped[ThemeVersion] = relationship()

class Publication(TimestampMixin, Base):
    __tablename__ = "publications"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_publication_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    article_revision_id: Mapped[str] = mapped_column(ForeignKey("article_revisions.id"), index=True)
    channel_account_id: Mapped[str] = mapped_column(String(100), default="env:default")
    action: Mapped[str] = mapped_column(String(32), default="create_draft")
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    remote_id: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)