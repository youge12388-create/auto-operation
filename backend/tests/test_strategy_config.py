from fastapi import BackgroundTasks
from sqlalchemy import select

from content_ops.api import add_revision, review_article
from content_ops.models import (
    Article,
    ArticleRevision,
    JobStep,
    ModelCallLog,
    ModelConfig,
    Skill,
    Source,
    Strategy,
    User,
)
from content_ops.providers import FakeProvider
from content_ops.schemas import ArticleRevisionCreate, ReviewCreate
from content_ops.security import hash_password
from content_ops.strategy_config import StrategyConfigError, skill_for_stage, validate_strategy_config
from content_ops.workflow import create_job, run_job


def test_strategy_config_rejects_core_step_and_invalid_review_rule():
    try:
        validate_strategy_config({"disabled_steps": ["writing"]})
    except StrategyConfigError as exc:
        assert "核心步骤" in str(exc)
    else:
        raise AssertionError("core steps must not be disableable")

    try:
        validate_strategy_config({"review_rules": {"human_review_required": "yes"}})
    except StrategyConfigError as exc:
        assert "布尔值" in str(exc)
    else:
        raise AssertionError("review rule type must be validated")


def test_workflow_applies_stage_models_skills_and_optional_steps(db):
    writing_model = ModelConfig(provider="fake", name="writing-fake")
    rewrite_model = ModelConfig(provider="fake", name="rewrite-fake")
    writing_skill = Skill(
        name="writing-skill",
        skill_type="writing",
        version="1.0.0",
        status="published",
        manifest_json={"name": "writing-skill", "type": "writing", "version": "1.0.0"},
        prompt="先核对事实，再组织结构。",
    )
    rewrite_skill = Skill(
        name="rewrite-skill",
        skill_type="rewrite",
        version="1.0.0",
        status="published",
        manifest_json={"name": "rewrite-skill", "type": "rewrite", "version": "1.0.0"},
        prompt="保持事实不变，删除空泛表达。",
    )
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/configured",
        config_json={"title": "配置驱动选题", "content": "配置驱动流程的事实。"},
    )
    other_source = Source(
        name="未选资料",
        source_type="manual",
        url="https://example.com/not-selected",
        config_json={"title": "不应被选中", "content": "这条内容不属于当前组合。"},
    )
    db.add_all([writing_model, rewrite_model, writing_skill, rewrite_skill, source, other_source])
    db.flush()
    strategy = Strategy(
        name="配置驱动策略",
        objective="验证阶段配置",
        config_json={
            "disabled_steps": ["style"],
            "source_ids": [source.id],
            "model_by_stage": {"writing": writing_model.id, "rewrite": rewrite_model.id},
            "skill_by_stage": {"writing": writing_skill.id, "rewrite": rewrite_skill.id},
            "review_rules": {"human_review_required": False},
        },
    )
    db.add(strategy)
    db.commit()

    job = create_job(db, strategy, "configured-workflow")
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "succeeded"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None
    assert article.status == "drafted"
    assert article.model_snapshot["stages"]["writing"]["id"] == writing_model.id
    assert article.model_snapshot["stages"]["rewrite"]["id"] == rewrite_model.id
    assert article.skill_snapshot["stages"]["writing"]["version"] == "1.0.0"
    assert article.runtime_snapshot_json["strategy"]["disabled_steps"] == ["style"]
    assert article.runtime_snapshot_json["strategy"]["source_ids"] == [source.id]
    assert [item["id"] for item in article.runtime_snapshot_json["sources"]] == [source.id]

    style_step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "style"))
    assert style_step is not None
    assert style_step.status == "skipped"
    stages = [item.stage for item in db.scalars(select(ModelCallLog).where(ModelCallLog.job_id == job.id)).all()]
    assert stages == ["writing", "rewrite"]


def test_edited_revision_is_the_one_sent_to_local_draft_after_approval(db):
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/edit",
        config_json={"title": "旧标题", "content": "需要编辑的事实。"},
    )
    strategy = Strategy(name="编辑恢复", objective="验证新版本恢复")
    reviewer = User(email="reviewer@example.com", password_hash=hash_password("reviewer-password-123"), role="reviewer")
    db.add_all([source, strategy, reviewer])
    db.commit()

    job = create_job(db, strategy, "edited-revision")
    first = run_job(db, job.id, FakeProvider())
    assert first.status == "waiting_review"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None

    revision = add_revision(
        article.id,
        ArticleRevisionCreate(content_markdown="# 人工修订版本\n\n保留已确认事实。"),
        reviewer,
        db,
    )
    render_step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "render"))
    draft_step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "draft"))
    assert render_step is not None and render_step.status == "queued"
    assert draft_step is not None and draft_step.status == "queued"

    review_article(
        article.id,
        revision.id,
        ReviewCreate(decision="approve"),
        BackgroundTasks(),
        reviewer,
        db,
    )
    resumed = run_job(db, job.id, FakeProvider())
    assert resumed.status == "succeeded"
    db.refresh(article)
    latest = db.scalar(
        select(ArticleRevision).where(ArticleRevision.article_id == article.id).order_by(ArticleRevision.version.desc())
    )
    assert latest is not None
    assert latest.id == revision.id
    assert db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "draft")).output_json[
        "revision_id"
    ] == revision.id

def test_published_khazix_writer_is_the_default_writing_skill(db):
    default_skill = Skill(
        name="khazix-writer",
        skill_type="writing",
        version="1.0.0",
        status="published",
        manifest_json={"name": "khazix-writer", "type": "writing", "version": "1.0.0"},
        prompt="使用卡兹克公众号长文风格。",
    )
    strategy = Strategy(name="默认写作 Skill", objective="验证默认 Skill")
    db.add_all([default_skill, strategy])
    db.commit()

    assert skill_for_stage(db, strategy, "writing") is default_skill
    assert skill_for_stage(db, strategy, "rewrite") is default_skill
    assert skill_for_stage(db, strategy, "review") is None
