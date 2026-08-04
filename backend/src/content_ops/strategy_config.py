from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ChannelAccount, ModelConfig, Skill, Source, Strategy, Theme

OPTIONAL_STEPS = frozenset({"style", "rewrite"})
MODEL_STAGES = ("writing", "style", "rewrite")
SKILL_STAGES = ("writing", "style", "rewrite", "review")
DEFAULT_WRITING_SKILL_NAME = "khazix-writer"
TOPIC_SCORE_DIMENSIONS = ("heat", "timeliness", "reader_value", "strategy_fit")
DEFAULT_TOPIC_WEIGHTS = {dimension: 25 for dimension in TOPIC_SCORE_DIMENSIONS}


class StrategyConfigError(ValueError):
    pass


def validate_strategy_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(config or {})
    disabled_steps = normalized.get("disabled_steps", [])
    if not isinstance(disabled_steps, list) or any(not isinstance(item, str) for item in disabled_steps):
        raise StrategyConfigError("disabled_steps 必须是字符串数组")
    invalid_steps = sorted(set(disabled_steps) - OPTIONAL_STEPS)
    if invalid_steps:
        raise StrategyConfigError(f"不能关闭核心步骤：{', '.join(invalid_steps)}")
    normalized["disabled_steps"] = sorted(set(disabled_steps))

    source_ids = normalized.get("source_ids", [])
    if not isinstance(source_ids, list) or any(not isinstance(item, str) for item in source_ids):
        raise StrategyConfigError("source_ids 必须是字符串数组")
    normalized["source_ids"] = sorted(set(source_ids))

    translate_foreign_sources = normalized.get("translate_foreign_sources", True)
    if not isinstance(translate_foreign_sources, bool):
        raise StrategyConfigError("translate_foreign_sources must be a boolean")
    normalized["translate_foreign_sources"] = translate_foreign_sources

    channel_account_id = normalized.get("channel_account_id")
    if channel_account_id is not None and not isinstance(channel_account_id, str):
        raise StrategyConfigError("channel_account_id 必须是字符串")
    normalized["channel_account_id"] = channel_account_id

    theme_id = normalized.get("theme_id")
    if theme_id is not None and not isinstance(theme_id, str):
        raise StrategyConfigError("theme_id 必须是字符串")
    normalized["theme_id"] = theme_id

    model_by_stage = normalized.get("model_by_stage", {})
    if not isinstance(model_by_stage, dict) or any(
        not isinstance(stage, str) or not isinstance(model_id, str) for stage, model_id in model_by_stage.items()
    ):
        raise StrategyConfigError("model_by_stage 必须是阶段到模型 ID 的对象")
    unknown_model_stages = sorted(set(model_by_stage) - set(MODEL_STAGES))
    if unknown_model_stages:
        raise StrategyConfigError(f"不支持的模型阶段：{', '.join(unknown_model_stages)}")
    normalized["model_by_stage"] = model_by_stage

    skill_by_stage = normalized.get("skill_by_stage", {})
    if not isinstance(skill_by_stage, dict) or any(
        not isinstance(stage, str) or not isinstance(skill_id, str) for stage, skill_id in skill_by_stage.items()
    ):
        raise StrategyConfigError("skill_by_stage 必须是阶段到 Skill ID 的对象")
    unknown_skill_stages = sorted(set(skill_by_stage) - set(SKILL_STAGES))
    if unknown_skill_stages:
        raise StrategyConfigError(f"不支持的 Skill 阶段：{', '.join(unknown_skill_stages)}")
    normalized["skill_by_stage"] = skill_by_stage

    skill_ids = normalized.get("skill_ids", [])
    if not isinstance(skill_ids, list) or any(not isinstance(item, str) for item in skill_ids):
        raise StrategyConfigError("skill_ids 必须是字符串数组")
    normalized["skill_ids"] = skill_ids

    review_rules = normalized.get("review_rules", {})
    if not isinstance(review_rules, dict):
        raise StrategyConfigError("review_rules 必须是对象")
    if "human_review_required" in review_rules and not isinstance(review_rules["human_review_required"], bool):
        raise StrategyConfigError("review_rules.human_review_required 必须是布尔值")
    normalized["review_rules"] = {"human_review_required": True, **review_rules}

    topic_algorithm = normalized.get("topic_algorithm", {})
    if not isinstance(topic_algorithm, dict):
        raise StrategyConfigError("topic_algorithm 必须是对象")
    instructions = topic_algorithm.get("instructions", "")
    if not isinstance(instructions, str) or len(instructions) > 2000:
        raise StrategyConfigError("topic_algorithm.instructions 必须是不超过 2000 字的字符串")
    max_topics = topic_algorithm.get("max_topics", 4)
    if isinstance(max_topics, bool) or not isinstance(max_topics, int) or not 1 <= max_topics <= 8:
        raise StrategyConfigError("topic_algorithm.max_topics 必须是 1-8 的整数")
    weights = topic_algorithm.get("weights", DEFAULT_TOPIC_WEIGHTS)
    if not isinstance(weights, dict) or set(weights) - set(TOPIC_SCORE_DIMENSIONS):
        raise StrategyConfigError("topic_algorithm.weights 包含不支持的评分维度")
    normalized_weights: dict[str, float] = {}
    for dimension in TOPIC_SCORE_DIMENSIONS:
        value = weights.get(dimension, DEFAULT_TOPIC_WEIGHTS[dimension])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise StrategyConfigError(f"topic_algorithm.weights.{dimension} 必须在 0-100 之间")
        normalized_weights[dimension] = float(value)
    if sum(normalized_weights.values()) <= 0:
        raise StrategyConfigError("选题评分权重不能全部为 0")
    normalized["topic_algorithm"] = {
        "instructions": instructions.strip(),
        "max_topics": max_topics,
        "weights": normalized_weights,
    }
    return normalized


def validate_strategy_references(db: Session, config: dict[str, Any]) -> None:
    for source_id in config.get("source_ids", []):
        source = db.get(Source, source_id)
        if source is None:
            raise StrategyConfigError(f"信息源不存在：{source_id}")
        if not source.enabled:
            raise StrategyConfigError(f"信息源已停用：{source_id}")

    channel_account_id = config.get("channel_account_id")
    if channel_account_id:
        channel_account = db.get(ChannelAccount, channel_account_id)
        if channel_account is None:
            raise StrategyConfigError(f"发布账号不存在：{channel_account_id}")
        if not channel_account.enabled:
            raise StrategyConfigError(f"发布账号已停用：{channel_account_id}")

    theme_id = config.get("theme_id")
    if theme_id:
        theme = db.get(Theme, theme_id)
        if theme is None:
            raise StrategyConfigError(f"排版主题不存在：{theme_id}")
        if not theme.enabled:
            raise StrategyConfigError(f"排版主题已停用：{theme_id}")
    model_ids = set(config.get("model_by_stage", {}).values())
    if config.get("default_model_id"):
        model_ids.add(config["default_model_id"])
    for model_id in model_ids:
        model = db.get(ModelConfig, model_id)
        if model is None:
            raise StrategyConfigError(f"模型不存在：{model_id}")
        if not model.enabled:
            raise StrategyConfigError(f"模型已停用：{model_id}")

    skill_ids = set(config.get("skill_ids", [])) | set(config.get("skill_by_stage", {}).values())
    for skill_id in skill_ids:
        skill = db.get(Skill, skill_id)
        if skill is None:
            raise StrategyConfigError(f"Skill 不存在：{skill_id}")
        if skill.status != "published":
            raise StrategyConfigError(f"Skill 尚未发布：{skill_id}")


def model_id_for_stage(config: dict[str, Any], stage: str, job_model_id: str | None = None) -> str | None:
    model_by_stage = config.get("model_by_stage", {})
    return model_by_stage.get(stage) or config.get("default_model_id") or job_model_id


def skill_for_stage_config(db: Session, config: dict[str, Any], stage: str) -> Skill | None:
    explicit_id = (config.get("skill_by_stage") or {}).get(stage)
    if explicit_id:
        skill = db.get(Skill, explicit_id)
        if skill is None or skill.status != "published":
            raise StrategyConfigError(f"阶段 {stage} 的 Skill 不可用")
        return skill

    for skill_id in config.get("skill_ids", []):
        skill = db.get(Skill, skill_id)
        if skill and skill.status == "published" and skill.skill_type == stage:
            return skill

    if stage == "writing":
        return db.scalar(
            select(Skill).where(
                Skill.name == DEFAULT_WRITING_SKILL_NAME,
                Skill.status == "published",
            )
        )
    return None


def skill_for_stage(db: Session, strategy: Strategy, stage: str) -> Skill | None:
    return skill_for_stage_config(db, strategy.config_json or {}, stage)


def model_snapshot(model: ModelConfig | None, fallback_provider: str) -> dict[str, Any]:
    if model is None:
        return {"id": None, "provider": fallback_provider, "name": None, "api_base_url": None}
    return {
        "id": model.id,
        "provider": model.provider,
        "name": model.name,
        "api_base_url": model.api_base_url,
        "config": model.config_json or {},
    }


def skill_snapshot(skill: Skill | None) -> dict[str, Any] | None:
    if skill is None:
        return None
    return {
        "id": skill.id,
        "name": skill.name,
        "type": skill.skill_type,
        "version": skill.version,
        "status": skill.status,
        "manifest": skill.manifest_json or {},
    }
