from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Job, Strategy
from .strategy_config import StrategyConfigError, validate_strategy_config, validate_strategy_references

SELECTION_MODES = frozenset({"fixed", "round_robin"})
META_KEYS = frozenset({"selection_mode", "default_combination_id", "strategy_combinations"})
MERGED_MAPPING_KEYS = frozenset({"model_by_stage", "skill_by_stage", "review_rules"})


@dataclass(frozen=True)
class ResolvedStrategyConfig:
    config: dict[str, Any]
    combination: dict[str, Any]


def execution_config(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key not in META_KEYS}


def merge_execution_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in MERGED_MAPPING_KEYS and isinstance(value, dict):
            merged[key] = {**(merged.get(key) or {}), **value}
        else:
            merged[key] = value
    return validate_strategy_config(merged)


def _normalized_override(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    if set(override) & META_KEYS:
        raise StrategyConfigError("Strategy combinations cannot contain nested combinations")
    merged = merge_execution_config(base, override)
    normalized: dict[str, Any] = {}
    for key, value in override.items():
        if key in MERGED_MAPPING_KEYS and isinstance(value, dict):
            normalized[key] = dict(value)
        else:
            normalized[key] = merged.get(key)
    return normalized


def validate_strategy_definition(config: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(config or {})
    base = validate_strategy_config(execution_config(raw))
    selection_mode = raw.get("selection_mode", "fixed")
    if selection_mode not in SELECTION_MODES:
        raise StrategyConfigError("selection_mode must be fixed or round_robin")

    raw_combinations = raw.get("strategy_combinations", [])
    if not isinstance(raw_combinations, list):
        raise StrategyConfigError("strategy_combinations must be a list")

    combinations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_combinations):
        if not isinstance(item, dict):
            raise StrategyConfigError(f"Strategy combination #{index + 1} must be an object")
        combination_id = item.get("id")
        if not isinstance(combination_id, str) or not combination_id.strip() or len(combination_id.strip()) > 64:
            raise StrategyConfigError(f"Strategy combination #{index + 1} id must contain 1-64 characters")
        combination_id = combination_id.strip()
        if combination_id in seen_ids:
            raise StrategyConfigError(f"Duplicate strategy combination id: {combination_id}")
        seen_ids.add(combination_id)

        name = item.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            raise StrategyConfigError(f"Strategy combination {combination_id} name must contain 1-100 characters")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise StrategyConfigError(f"Strategy combination {combination_id} enabled must be a boolean")
        override = item.get("config", {})
        if not isinstance(override, dict):
            raise StrategyConfigError(f"Strategy combination {combination_id} config must be an object")
        combinations.append(
            {
                "id": combination_id,
                "name": name.strip(),
                "enabled": enabled,
                "config": _normalized_override(base, override),
            }
        )

    enabled = [item for item in combinations if item["enabled"]]
    if combinations and not enabled:
        raise StrategyConfigError("At least one strategy combination must be enabled")

    default_combination_id = raw.get("default_combination_id")
    if default_combination_id is not None and not isinstance(default_combination_id, str):
        raise StrategyConfigError("default_combination_id must be a string")
    if enabled:
        enabled_ids = {item["id"] for item in enabled}
        default_combination_id = default_combination_id or enabled[0]["id"]
        if default_combination_id not in enabled_ids:
            raise StrategyConfigError("The default strategy combination must exist and be enabled")
    else:
        default_combination_id = None

    return {
        **base,
        "selection_mode": selection_mode,
        "default_combination_id": default_combination_id,
        "strategy_combinations": combinations,
    }


def validate_strategy_definition_references(db: Session, config: dict[str, Any]) -> None:
    normalized = validate_strategy_definition(config)
    base = execution_config(normalized)
    enabled = [item for item in normalized["strategy_combinations"] if item["enabled"]]
    if not enabled:
        validate_strategy_references(db, base)
        return
    for combination in enabled:
        validate_strategy_references(db, merge_execution_config(base, combination["config"]))


def resolve_strategy_definition(
    db: Session,
    strategy: Strategy,
    idempotency_key: str,
    requested_combination_id: str | None = None,
) -> ResolvedStrategyConfig:
    normalized = validate_strategy_definition(strategy.config_json)
    base = execution_config(normalized)
    enabled = [item for item in normalized["strategy_combinations"] if item["enabled"]]
    if not enabled:
        validate_strategy_references(db, base)
        return ResolvedStrategyConfig(
            config=base,
            combination={
                "id": "default",
                "name": strategy.name,
                "selection_mode": "legacy",
                "selection_reason": "Legacy single-combination strategy",
            },
        )

    if requested_combination_id:
        selected = next((item for item in enabled if item["id"] == requested_combination_id), None)
        if selected is None:
            raise StrategyConfigError("The requested strategy combination does not exist or is disabled")
        selection_mode = "manual"
        selection_reason = "Manually selected for this run"
    elif normalized["selection_mode"] == "round_robin":
        previous_jobs = (
            db.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.strategy_id == strategy.id,
                    Job.payload_json["runtime_snapshot"]["combination"]["selection_mode"].as_string() == "round_robin",
                )
            )
            or 0
        )
        selected = enabled[previous_jobs % len(enabled)]
        selection_mode = "round_robin"
        selection_reason = f"Round-robin selection for run {previous_jobs + 1}"
    else:
        selected = next(item for item in enabled if item["id"] == normalized["default_combination_id"])
        selection_mode = "fixed"
        selection_reason = "Production line default combination"

    resolved_config = merge_execution_config(base, selected["config"])
    validate_strategy_references(db, resolved_config)
    return ResolvedStrategyConfig(
        config=resolved_config,
        combination={
            "id": selected["id"],
            "name": selected["name"],
            "selection_mode": selection_mode,
            "selection_reason": selection_reason,
            "idempotency_key": idempotency_key,
        },
    )
