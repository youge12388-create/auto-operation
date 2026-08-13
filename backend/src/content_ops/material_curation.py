from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy.orm import Session

from .models import Job, ModelCallLog, ModelConfig, SourceItem, Strategy
from .providers import CompletionRequest, ModelProvider


def _score(value: Any) -> float:
    try:
        score = float(value)
        if 0 < score <= 1:
            score *= 100
        elif 1 < score <= 10:
            score *= 10
        return max(0.0, min(100.0, score))
    except (TypeError, ValueError):
        return 0.0


def parse_curation(text: str, available_ids: set[str], limit: int) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    object_start, object_end = cleaned.find("{"), cleaned.rfind("}")
    array_start, array_end = cleaned.find("["), cleaned.rfind("]")
    use_array = array_start >= 0 and array_end > array_start and (object_start < 0 or array_start < object_start)
    start, end = (array_start, array_end) if use_array else (object_start, object_end)
    if start < 0 or end <= start:
        raise ValueError("AI did not return a parseable curation result")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("AI curation result is not valid JSON") from exc
    raw_items = payload.get("materials") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError("Curation result must contain a materials array")
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        material_id = raw.get("id") or raw.get("material_id")
        if not isinstance(material_id, str) or material_id not in available_ids or material_id in seen:
            continue
        decision = str(raw.get("decision") or "select").lower()
        if decision in {"keep", "selected", "select", "yes", "true"}:
            decision = "select"
        else:
            decision = "review"
        decisions.append(
            {
                "id": material_id,
                "decision": decision,
                "score": round(_score(raw.get("score")), 1),
                "reason": str(raw.get("reason") or raw.get("rationale") or "").strip()[:500],
            }
        )
        seen.add(material_id)
        if len(decisions) >= limit:
            break
    if not decisions:
        raise ValueError("AI did not return usable curation decisions")
    return decisions


def curate_materials(
    db: Session,
    job: Job | None,
    strategy: Strategy,
    materials: list[SourceItem],
    provider: ModelProvider,
    model: ModelConfig | None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    candidates = [
        item
        for item in materials
        if item.status == "verified" and item.triage_status in {"inbox", "selected"}
    ][:limit]
    if not candidates:
        return []
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "source": item.source.name if item.source is not None else "unknown",
            "excerpt": item.content[:900],
        }
        for item in candidates
    ]
    request = CompletionRequest(
        system=(
            "You are an editorial material reviewer. Select only materials with clear facts, timely relevance, "
            "reader value, and fit for the current strategy. Do not rewrite or invent facts. Return JSON only."
        ),
        user="MATERIAL_CURATION_JSON\n" + json.dumps(
            {
                "strategy_objective": strategy.objective,
                "response_schema": {
                    "materials": [
                        {"id": "material id", "decision": "select or review", "score": 0, "reason": "reason"}
                    ]
                },
                "materials": payload,
            },
            ensure_ascii=False,
        ),
        max_tokens=1800,
    )
    started = time.perf_counter()
    provider_name = model.provider if model is not None else provider.__class__.__name__
    model_name = model.name if model is not None else provider.__class__.__name__
    try:
        response = provider.complete(request)
        decisions = parse_curation(response.text, {item.id for item in candidates}, limit)
    except Exception as exc:
        db.add(
            ModelCallLog(
                job_id=job.id if job is not None else None,
                stage="material_curation",
                provider=provider_name,
                model_name=model_name,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_summary=request.user[:1200],
                error=str(exc)[:2000],
            )
        )
        db.flush()
        selected: list[dict[str, Any]] = []
        reason = f"AI curation unavailable; deterministic fallback used: {exc}"[:500]
        for item in candidates[:limit]:
            if item.triage_status == "used":
                continue
            item.triage_status = "selected"
            selected.append(
                {
                    "id": item.id,
                    "decision": "select",
                    "score": 60.0,
                    "reason": reason,
                    "title": item.title,
                }
            )
        db.flush()
        return selected
    db.add(
        ModelCallLog(
            job_id=job.id if job is not None else None,
            stage="material_curation",
            provider=provider_name,
            model_name=model_name,
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
    selected: list[dict[str, Any]] = []
    for decision in decisions:
        item = by_id[decision["id"]]
        if decision["decision"] == "select" and item.triage_status != "used":
            item.triage_status = "selected"
            selected.append({**decision, "title": item.title})
    db.flush()
    return selected