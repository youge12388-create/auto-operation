from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.orm import Session

from .models import Job, MaterialCategory, ModelCallLog, ModelConfig, SourceItem
from .providers import CompletionRequest, ModelProvider


def _confidence(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def parse_classifications(
    text: str,
    available_material_ids: set[str],
    available_category_ids: set[str],
) -> list[dict[str, Any]]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI 未返回可解析的分类结果")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("AI 分类结果不是有效 JSON") from exc
    rows = payload.get("materials") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("AI 分类结果必须包含 materials 数组")
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        material_id = row.get("id") or row.get("material_id")
        category_id = row.get("category_id")
        if (
            not isinstance(material_id, str)
            or material_id not in available_material_ids
            or material_id in seen
            or not isinstance(category_id, str)
            or category_id not in available_category_ids
        ):
            continue
        decisions.append(
            {
                "id": material_id,
                "category_id": category_id,
                "confidence": round(_confidence(row.get("confidence")), 1),
                "reason": str(row.get("reason") or "").strip()[:1000],
            }
        )
        seen.add(material_id)
    if not decisions:
        raise ValueError("AI 未返回可用的素材分类")
    return decisions


def classify_materials(
    db: Session,
    job: Job | None,
    materials: list[SourceItem],
    categories: list[MaterialCategory],
    provider: ModelProvider | None,
    model: ModelConfig | None,
) -> dict[str, int]:
    candidates = [item for item in materials if item.status == "verified"]
    enabled_categories = [category for category in categories if category.enabled]
    if not candidates:
        return {"candidate_count": 0, "classified_count": 0, "failed_count": 0}
    if not enabled_categories:
        for item in candidates:
            item.category_id = None
            item.classification_status = "unclassified"
            item.classification_source = None
            item.classification_confidence = None
            item.classification_reason = None
            item.classification_error = "没有启用的素材分类"
        db.flush()
        return {"candidate_count": len(candidates), "classified_count": 0, "failed_count": 0}
    if provider is None or model is None:
        for item in candidates:
            item.category_id = None
            item.classification_status = "failed"
            item.classification_source = "ai"
            item.classification_confidence = None
            item.classification_reason = None
            item.classification_error = "没有可用的 AI 分类模型"
        db.flush()
        return {
            "candidate_count": len(candidates),
            "classified_count": 0,
            "failed_count": len(candidates),
        }

    request = CompletionRequest(
        system=(
            "你是内容素材分类员。只能把每条素材归入给定分类中的一个，不得创造新分类。"
            "根据标题和正文含义判断，返回 JSON，不要输出解释性文本。"
        ),
        user="MATERIAL_CLASSIFICATION_JSON\n"
        + json.dumps(
            {
                "response_schema": {
                    "materials": [
                        {
                            "id": "素材 ID",
                            "category_id": "分类 ID",
                            "confidence": 0,
                            "reason": "简短理由",
                        }
                    ]
                },
                "categories": [
                    {
                        "id": category.id,
                        "name": category.name,
                        "description": category.description,
                        "instructions": category.classification_instructions,
                    }
                    for category in enabled_categories
                ],
                "materials": [
                    {"id": item.id, "title": item.title, "content": item.content[:1600]}
                    for item in candidates
                ],
            },
            ensure_ascii=False,
        ),
        max_tokens=min(4000, max(800, len(candidates) * 120)),
    )
    started = time.perf_counter()
    try:
        response = provider.complete(request)
        decisions = parse_classifications(
            response.text,
            {item.id for item in candidates},
            {category.id for category in enabled_categories},
        )
    except Exception as exc:
        error = str(exc)[:2000]
        for item in candidates:
            item.classification_status = "failed"
            item.classification_source = "ai"
            item.classification_error = error
        db.add(
            ModelCallLog(
                job_id=job.id if job is not None else None,
                stage="material_classification",
                provider=model.provider,
                model_name=model.name,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_summary=request.user[:1200],
                error=error,
            )
        )
        db.flush()
        return {
            "candidate_count": len(candidates),
            "classified_count": 0,
            "failed_count": len(candidates),
        }

    db.add(
        ModelCallLog(
            job_id=job.id if job is not None else None,
            stage="material_classification",
            provider=model.provider,
            model_name=model.name,
            status="succeeded",
            duration_ms=int((time.perf_counter() - started) * 1000),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost=response.cost,
            input_summary=request.user[:1200],
            output_summary=response.text[:1200],
        )
    )
    by_id = {item.id: item for item in candidates}
    classified_ids: set[str] = set()
    for decision in decisions:
        item = by_id[decision["id"]]
        item.category_id = decision["category_id"]
        item.classification_status = "classified"
        item.classification_source = "ai"
        item.classification_confidence = decision["confidence"]
        item.classification_reason = decision["reason"]
        item.classification_error = None
        classified_ids.add(item.id)
    for item in candidates:
        if item.id not in classified_ids:
            item.classification_status = "failed"
            item.classification_source = "ai"
            item.classification_error = "AI 未返回这条素材的分类"
    db.flush()
    return {
        "candidate_count": len(candidates),
        "classified_count": len(classified_ids),
        "failed_count": len(candidates) - len(classified_ids),
    }