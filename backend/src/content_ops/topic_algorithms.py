from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import TopicAlgorithm
from .strategy_config import DEFAULT_TOPIC_WEIGHTS, TOPIC_SCORE_DIMENSIONS

DEFAULT_TOPIC_ALGORITHM_NAME = "默认推荐算法"
DEFAULT_TOPIC_ALGORITHM_INSTRUCTIONS = (
    "优先推荐具备真实时效、读者价值和明确切入角度的选题；"
    "排除只有标题党、缺少依据或与当前内容目标无关的素材。"
)


def normalize_topic_algorithm(
    *,
    instructions: str,
    max_topics: int,
    weights: dict[str, float] | None,
) -> dict[str, Any]:
    if not isinstance(instructions, str) or len(instructions) > 2000:
        raise ValueError("选题算法说明必须是不超过 2000 字的文本")
    if isinstance(max_topics, bool) or not isinstance(max_topics, int) or not 1 <= max_topics <= 8:
        raise ValueError("每次推荐数量必须是 1-8 的整数")
    supplied_weights = weights or {}
    if set(supplied_weights) - set(TOPIC_SCORE_DIMENSIONS):
        raise ValueError("选题算法包含不支持的评分维度")
    normalized_weights: dict[str, float] = {}
    for dimension in TOPIC_SCORE_DIMENSIONS:
        value = supplied_weights.get(dimension, DEFAULT_TOPIC_WEIGHTS[dimension])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"{dimension} 的权重必须在 0-100 之间")
        normalized_weights[dimension] = float(value)
    if sum(normalized_weights.values()) <= 0:
        raise ValueError("选题评分权重不能全部为 0")
    return {
        "instructions": instructions.strip(),
        "max_topics": max_topics,
        "weights": normalized_weights,
    }


def ensure_builtin_topic_algorithm(db: Session) -> TopicAlgorithm:
    builtin = db.scalar(select(TopicAlgorithm).where(TopicAlgorithm.name == DEFAULT_TOPIC_ALGORITHM_NAME))
    if builtin is None:
        values = normalize_topic_algorithm(
            instructions=DEFAULT_TOPIC_ALGORITHM_INSTRUCTIONS,
            max_topics=4,
            weights=DEFAULT_TOPIC_WEIGHTS,
        )
        builtin = TopicAlgorithm(
            name=DEFAULT_TOPIC_ALGORITHM_NAME,
            instructions=values["instructions"],
            max_topics=values["max_topics"],
            weights_json=values["weights"],
            is_builtin=True,
            enabled=True,
        )
        db.add(builtin)
        db.commit()
        db.refresh(builtin)
    return builtin


def topic_algorithm_values(algorithm: TopicAlgorithm) -> dict[str, Any]:
    return normalize_topic_algorithm(
        instructions=algorithm.instructions,
        max_topics=algorithm.max_topics,
        weights=algorithm.weights_json,
    )


def topic_algorithm_snapshot(algorithm: TopicAlgorithm) -> dict[str, Any]:
    return {
        "id": algorithm.id,
        "name": algorithm.name,
        "is_builtin": algorithm.is_builtin,
        **topic_algorithm_values(algorithm),
    }