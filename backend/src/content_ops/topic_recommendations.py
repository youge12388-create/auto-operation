from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job, ModelCallLog, ModelConfig, SourceItem, Strategy, Topic, TopicMaterial, TopicScore
from .providers import CompletionRequest, ModelProvider
from .strategy_config import DEFAULT_TOPIC_WEIGHTS

SCORE_DIMENSIONS = ("heat", "timeliness", "reader_value", "strategy_fit")


def _clamp_score(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _weighted_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return sum(scores.values()) / len(SCORE_DIMENSIONS)
    return sum(scores[dimension] * weights.get(dimension, 0) for dimension in SCORE_DIMENSIONS) / total_weight


def parse_recommendations(
    text: str,
    available_ids: set[str],
    limit: int,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("The model did not return a JSON recommendation object")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("The model returned invalid recommendation JSON") from exc
    raw_topics = payload.get("topics") if isinstance(payload, dict) else None
    if not isinstance(raw_topics, list):
        raise ValueError("Recommendation JSON must contain a topics array")

    recommendations: list[dict[str, Any]] = []
    for raw in raw_topics:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()[:500]
        rationale = str(raw.get("rationale") or "").strip()[:2000]
        material_ids = list(
            dict.fromkeys(
                item for item in raw.get("material_ids", []) if isinstance(item, str) and item in available_ids
            )
        )[:6]
        if not title or not rationale or not material_ids:
            continue
        raw_scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
        scores = {dimension: _clamp_score(raw_scores.get(dimension)) for dimension in SCORE_DIMENSIONS}
        score = (
            _weighted_score(scores, weights)
            if weights is not None
            else (_clamp_score(raw.get("score")) or sum(scores.values()) / len(SCORE_DIMENSIONS))
        )
        recommendations.append(
            {
                "title": title,
                "rationale": rationale,
                "material_ids": material_ids,
                "score": round(score, 1),
                "scores": scores,
            }
        )
        if len(recommendations) >= limit:
            break
    if not recommendations:
        raise ValueError("The model did not return any usable topic recommendations")
    return recommendations


def recommend_topics(
    db: Session,
    job: Job,
    strategy: Strategy,
    materials: list[SourceItem],
    provider: ModelProvider,
    model: ModelConfig | None,
    strategy_objective: str | None = None,
    algorithm: dict[str, Any] | None = None,
    limit: int = 4,
) -> list[Topic]:
    candidates = [item for item in materials if item.status == "verified" and item.triage_status != "ignored"][:12]
    if not candidates:
        raise ValueError("No verified scan discoveries are available for topic recommendation")
    source_payload = [
        {
            "id": item.id,
            "title": item.title,
            "source": item.source.name if item.source is not None else "Unknown source",
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "excerpt": item.content[:700],
        }
        for item in candidates
    ]
    algorithm = algorithm or {}
    instructions = str(algorithm.get("instructions") or "").strip()
    raw_weights = algorithm.get("weights") if isinstance(algorithm.get("weights"), dict) else DEFAULT_TOPIC_WEIGHTS
    weights = {dimension: float(raw_weights.get(dimension, 25)) for dimension in SCORE_DIMENSIONS}
    request = CompletionRequest(
        system=(
            "You are a Chinese editorial strategist. Recommend genuinely newsworthy article topics from only the "
            "provided materials. Explain why each topic matters and score heat, timeliness, reader_value, and "
            "strategy_fit from 0 to 100. Follow the custom editorial criteria when provided. Return JSON only."
        ),
        user=json.dumps(
            {
                "strategy_objective": strategy_objective or strategy.objective,
                "custom_editorial_criteria": instructions,
                "score_weights": weights,
                "maximum_topics": limit,
                "response_schema": {
                    "topics": [
                        {
                            "title": "Chinese title",
                            "rationale": "Chinese explanation grounded in the materials",
                            "material_ids": ["one or more provided IDs"],
                            "score": 0,
                            "scores": {dimension: 0 for dimension in SCORE_DIMENSIONS},
                        }
                    ]
                },
                "materials": source_payload,
            },
            ensure_ascii=False,
        ),
        max_tokens=3200,
    )
    started = time.perf_counter()
    provider_name = model.provider if model is not None else provider.__class__.__name__
    model_name = model.name if model is not None else provider.__class__.__name__
    try:
        response = provider.complete(request)
        recommendations = parse_recommendations(response.text, {item.id for item in candidates}, limit, weights)
    except Exception as exc:
        db.add(
            ModelCallLog(
                job_id=job.id,
                stage="topic_recommendation",
                provider=provider_name,
                model_name=model_name,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_summary=request.user[:1000],
                error=str(exc)[:2000],
            )
        )
        db.flush()
        raise
    db.add(
        ModelCallLog(
            job_id=job.id,
            stage="topic_recommendation",
            provider=provider_name,
            model_name=model_name,
            status="succeeded",
            duration_ms=int((time.perf_counter() - started) * 1000),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost=response.cost,
            input_summary=request.user[:1000],
            output_summary=response.text[:1000],
        )
    )

    by_id = {item.id: item for item in candidates}
    created: list[Topic] = []
    for recommendation in recommendations:
        existing = db.scalar(
            select(Topic).where(
                Topic.strategy_id == strategy.id,
                Topic.title == recommendation["title"],
                Topic.status.in_(("candidate", "accepted", "writing")),
            )
        )
        if existing is not None:
            created.append(existing)
            continue
        primary_id = recommendation["material_ids"][0]
        topic = Topic(
            strategy_id=strategy.id,
            job_id=job.id,
            source_item_id=primary_id,
            title=recommendation["title"],
            status="candidate",
            score=recommendation["score"],
            rationale=recommendation["rationale"],
        )
        db.add(topic)
        db.flush()
        for position, material_id in enumerate(recommendation["material_ids"]):
            material = by_id[material_id]
            db.add(
                TopicMaterial(
                    topic_id=topic.id,
                    source_item_id=material.id,
                    role="primary" if position == 0 else "supporting",
                    relevance_score=recommendation["score"] if position == 0 else max(0, recommendation["score"] - 5),
                )
            )
        for dimension, score in recommendation["scores"].items():
            db.add(
                TopicScore(
                    topic_id=topic.id,
                    dimension=dimension,
                    score=score,
                    rationale=recommendation["rationale"],
                )
            )
        created.append(topic)
    db.flush()
    return created
