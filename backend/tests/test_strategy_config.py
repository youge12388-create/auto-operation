import pytest
from fastapi import BackgroundTasks
from sqlalchemy import select

from content_ops.api import add_revision, archive_article, review_article
from content_ops.channels import ENV_CHANNEL_ID
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
from content_ops.strategy_config import (
    StrategyConfigError,
    skill_for_stage,
    validate_strategy_config,
    validate_strategy_references,
)
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
    configured = validate_strategy_config(
        {
            "topic_algorithm": {
                "instructions": "优先具体用户价值，排除通稿",
                "max_topics": 6,
                "weights": {"heat": 10, "timeliness": 20, "reader_value": 50, "strategy_fit": 20},
            }
        }
    )
    assert configured["topic_algorithm"]["max_topics"] == 6
    assert configured["topic_algorithm"]["weights"]["reader_value"] == 50

    try:
        validate_strategy_config({"topic_algorithm": {"max_topics": 0}})
    except StrategyConfigError as exc:
        assert "1-8" in str(exc)
    else:
        raise AssertionError("topic recommendation count must be validated")


def test_local_draft_discards_irrelevant_wechat_delivery_fields():
    configured = validate_strategy_config(
        {
            "delivery_mode": "local_draft",
            "channel_account_id": "missing-account",
            "wechat_thumb_media_id": "unused-cover",
        }
    )

    assert configured["channel_account_id"] is None
    assert configured["wechat_thumb_media_id"] is None


def test_environment_channel_is_valid_for_automatic_draft_but_not_publish(db):
    configured = validate_strategy_config(
        {
            "delivery_mode": "wechat_draft",
            "channel_account_id": ENV_CHANNEL_ID,
            "wechat_thumb_media_id": "environment-thumb",
        }
    )
    validate_strategy_references(db, configured)

    publish_config = validate_strategy_config(
        {
            "delivery_mode": "auto_publish",
            "channel_account_id": ENV_CHANNEL_ID,
            "wechat_thumb_media_id": "environment-thumb",
        }
    )
    try:
        validate_strategy_references(db, publish_config)
    except StrategyConfigError as exc:
        assert "只有草稿权限" in str(exc)
    else:
        raise AssertionError("the environment channel must never gain publish capability")

def test_workflow_applies_stage_models_skills_and_optional_steps(db):
    outline_model = ModelConfig(provider="fake", name="outline-fake")
    writing_model = ModelConfig(provider="fake", name="writing-fake")
    rewrite_model = ModelConfig(provider="fake", name="rewrite-fake")
    outline_skill = Skill(
        name="outline-skill",
        skill_type="outline",
        version="1.0.0",
        status="published",
        manifest_json={"name": "outline-skill", "type": "outline", "version": "1.0.0"},
        prompt="Plan the reader problem, hook, evidence, and conclusion.",
    )
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
    db.add_all(
        [outline_model, writing_model, rewrite_model, outline_skill, writing_skill, rewrite_skill, source, other_source]
    )
    db.flush()
    strategy = Strategy(
        name="配置驱动策略",
        objective="验证阶段配置",
        config_json={
            "disabled_steps": ["style"],
            "source_ids": [source.id],
            "model_by_stage": {"outline": outline_model.id, "writing": writing_model.id, "rewrite": rewrite_model.id},
            "skill_by_stage": {"outline": outline_skill.id, "writing": writing_skill.id, "rewrite": rewrite_skill.id},
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
    assert article.model_snapshot["stages"]["outline"]["id"] == outline_model.id
    assert article.model_snapshot["stages"]["writing"]["id"] == writing_model.id
    assert article.model_snapshot["stages"]["rewrite"]["id"] == rewrite_model.id
    assert article.skill_snapshot["stages"]["outline"]["version"] == "1.0.0"
    assert article.skill_snapshot["stages"]["writing"]["version"] == "1.0.0"
    assert article.runtime_snapshot_json["strategy"]["disabled_steps"] == ["style"]
    assert article.runtime_snapshot_json["strategy"]["source_ids"] == [source.id]
    assert [item["id"] for item in article.runtime_snapshot_json["sources"]] == [source.id]

    style_step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "style"))
    assert style_step is not None
    assert style_step.status == "skipped"
    stages = [item.stage for item in db.scalars(select(ModelCallLog).where(ModelCallLog.job_id == job.id)).all()]
    assert stages == ["material_curation", "topic_recommendation", "outline", "writing", "rewrite", "review"]


def test_edited_revision_is_the_one_sent_to_local_draft_after_approval(db):
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/edit",
        config_json={"title": "旧标题", "content": "需要编辑的事实。"},
    )
    strategy = Strategy(name="编辑恢复", objective="验证新版本恢复")
    strategy.config_json = {"review_rules": {"human_review_required": True}}
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
        ArticleRevisionCreate(title="人工修订标题", content_markdown="# 人工修订版本\n\n保留已确认事实。"),
        reviewer,
        db,
    )
    render_step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "render"))
    draft_step = db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "draft"))
    assert render_step is not None and render_step.status == "queued"
    assert draft_step is not None and draft_step.status == "queued"
    db.refresh(article)
    assert article.title == "人工修订标题"
    assert article.status == "waiting_review"

    review_result = review_article(
        article.id,
        revision.id,
        ReviewCreate(decision="approve"),
        BackgroundTasks(),
        reviewer,
        db,
    )
    assert review_result.status == "approved"
    assert review_result.auto_result == {}
    resumed = run_job(db, job.id, FakeProvider())
    assert resumed.status == "succeeded"
    db.refresh(article)
    latest = db.scalar(
        select(ArticleRevision).where(ArticleRevision.article_id == article.id).order_by(ArticleRevision.version.desc())
    )
    assert latest is not None
    assert latest.id == revision.id
    expected_content = (
        "# \u4eba\u5de5\u4fee\u8ba2\u7248\u672c\n\n"
        "\u4fdd\u7559\u5df2\u786e\u8ba4\u4e8b\u5b9e\u3002"
    )
    assert latest.content_markdown == expected_content
    assert (
        db.scalar(select(JobStep).where(JobStep.job_id == job.id, JobStep.step_name == "draft")).output_json[
            "revision_id"
        ]
        == revision.id
    )
    archived = archive_article(article.id, reviewer, db)
    assert archived.status == "archived"


def test_unconfigured_strategy_does_not_fall_back_to_default_skill(db):
    default_skill = Skill(
        name="khazix-writer",
        skill_type="writing",
        version="1.0.0",
        status="published",
        manifest_json={"name": "khazix-writer", "type": "writing", "version": "1.0.0"},
        prompt="使用卡兹克公众号长文风格。",
    )
    strategy = Strategy(name="未配置写作 Skill", objective="验证不默认套用")
    db.add_all([default_skill, strategy])
    db.commit()

    assert skill_for_stage(db, strategy, "writing") is None
    assert skill_for_stage(db, strategy, "rewrite") is None
    assert skill_for_stage(db, strategy, "review") is None


def test_job_execution_override_sets_writing_skill_without_fallback(db):
    default_skill = Skill(
        name="khazix-writer",
        skill_type="writing",
        version="1.0.0",
        status="published",
        manifest_json={"name": "khazix-writer", "type": "writing", "version": "1.0.0"},
        prompt="使用卡兹克公众号长文风格。",
    )
    override_skill = Skill(
        name="my-writer",
        skill_type="writing",
        version="1.0.0",
        status="published",
        manifest_json={"name": "my-writer", "type": "writing", "version": "1.0.0"},
        prompt="使用我的通用写作风格。",
    )
    source = Source(
        name="手动资料",
        source_type="manual",
        url="https://example.com/skill-override",
        config_json={"title": "某 AI 产品更新", "content": "官方公告确认产品已发布。"},
    )
    strategy = Strategy(name="Skill 覆盖策略", objective="测试写作 Skill 覆盖")
    strategy.config_json = {"review_rules": {"human_review_required": True}}
    db.add_all([default_skill, override_skill, source, strategy])
    db.commit()

    plain_job = create_job(db, strategy, "skill-plain")
    plain = run_job(db, plain_job.id, FakeProvider())
    assert plain.status == "waiting_review"
    plain_article = db.scalar(select(Article).where(Article.job_id == plain_job.id))
    assert "writing" not in (plain_article.skill_snapshot or {}).get("stages", {})

    overridden_job = create_job(
        db,
        strategy,
        "skill-override",
        execution_config_override={"skill_by_stage": {"writing": override_skill.id}, "skill_ids": []},
    )
    overridden = run_job(db, overridden_job.id, FakeProvider())
    assert overridden.status == "waiting_review"
    overridden_article = db.scalar(select(Article).where(Article.job_id == overridden_job.id))
    assert overridden_article.skill_snapshot["stages"]["writing"]["name"] == "my-writer"
    assert overridden_article.skill_snapshot["stages"]["writing"]["id"] == override_skill.id


def test_theme_selection_mode_defaults_to_manual_and_validates_values():
    assert validate_strategy_config({})["theme_selection_mode"] == "manual"
    assert validate_strategy_config({"theme_selection_mode": "auto"})["theme_selection_mode"] == "auto"

    with pytest.raises(StrategyConfigError, match="theme_selection_mode"):
        validate_strategy_config({"theme_selection_mode": "rotate"})