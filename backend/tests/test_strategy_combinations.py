import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from content_ops.api import JOB_PRIORITY_MIGRATION_DETAIL, raise_job_schema_error, run_strategy
from content_ops.models import Article, ModelConfig, Source, Strategy
from content_ops.providers import FakeProvider
from content_ops.schemas import StrategyRunRequest
from content_ops.strategy_combinations import validate_strategy_definition
from content_ops.workflow import create_job, run_job


def combination(
    combination_id: str,
    name: str,
    source_id: str,
    model_id: str | None = None,
) -> dict:
    config: dict = {"source_ids": [source_id], "review_rules": {"human_review_required": False}}
    if model_id:
        config["model_by_stage"] = {"writing": model_id}
    return {"id": combination_id, "name": name, "enabled": True, "config": config}


def test_fixed_combination_is_frozen_when_job_is_created(db):
    first_source = Source(
        name="first-source",
        source_type="manual",
        url="https://example.com/first",
        config_json={"title": "First title", "content": "First facts"},
    )
    second_source = Source(
        name="second-source",
        source_type="manual",
        url="https://example.com/second",
        config_json={"title": "Second title", "content": "Second facts"},
    )
    model = ModelConfig(provider="fake", name="combination-model")
    db.add_all([first_source, second_source, model])
    db.flush()
    strategy = Strategy(
        name="combination-line",
        objective="test combination snapshot",
        config_json=validate_strategy_definition(
            {
                "selection_mode": "fixed",
                "default_combination_id": "fast",
                "strategy_combinations": [
                    combination("fast", "Fast news", first_source.id, model.id),
                    combination("deep", "Deep analysis", second_source.id),
                ],
            }
        ),
    )
    db.add(strategy)
    db.commit()

    original_version = strategy.version
    original_name = strategy.name
    job = create_job(db, strategy, "combination-fixed")
    assert job.runtime_snapshot["combination"]["id"] == "fast"
    assert job.runtime_snapshot["execution_config"]["source_ids"] == [first_source.id]

    strategy.config_json = validate_strategy_definition(
        {
            "selection_mode": "fixed",
            "default_combination_id": "deep",
            "strategy_combinations": [
                combination("fast", "Fast news", first_source.id, model.id),
                combination("deep", "Deep analysis", second_source.id),
            ],
        }
    )
    strategy.version += 1
    strategy.name = "changed-after-queueing"
    db.commit()

    result = run_job(db, job.id, FakeProvider())
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert result.status == "succeeded"
    assert article is not None
    assert article.title == "\u4e2d\u6587\u8bd1\u6587\uff1aFirst title"
    assert article.strategy_version == original_version
    assert article.skill_snapshot["strategy_version"] == original_version
    assert article.runtime_snapshot_json["strategy"]["version"] == original_version
    assert article.runtime_snapshot_json["strategy"]["name"] == original_name
    assert article.runtime_snapshot_json["combination"]["id"] == "fast"
    assert article.runtime_snapshot_json["execution_config"]["source_ids"] == [first_source.id]


def test_round_robin_and_manual_combination_selection(db):
    first_source = Source(
        name="round-source-one",
        source_type="manual",
        url="https://example.com/round-one",
        config_json={"title": "One", "content": "One facts"},
    )
    second_source = Source(
        name="round-source-two",
        source_type="manual",
        url="https://example.com/round-two",
        config_json={"title": "Two", "content": "Two facts"},
    )
    db.add_all([first_source, second_source])
    db.flush()
    strategy = Strategy(
        name="round-robin-line",
        objective="test rotation",
        config_json=validate_strategy_definition(
            {
                "selection_mode": "round_robin",
                "strategy_combinations": [
                    combination("one", "One", first_source.id),
                    combination("two", "Two", second_source.id),
                ],
            }
        ),
    )
    db.add(strategy)
    db.commit()

    manual = create_job(db, strategy, "round-manual", payload={"mode": "scan"}, combination_id="one")
    first = create_job(db, strategy, "round-1", payload={"mode": "scan"})
    second = create_job(db, strategy, "round-2", payload={"mode": "scan"})

    assert manual.runtime_snapshot["combination"]["id"] == "one"
    assert manual.runtime_snapshot["combination"]["selection_mode"] == "manual"
    assert first.runtime_snapshot["combination"]["id"] == "one"
    assert second.runtime_snapshot["combination"]["id"] == "two"


def test_missing_job_priority_schema_has_actionable_error():
    error = OperationalError(
        "SELECT automation_jobs.priority FROM automation_jobs",
        {},
        Exception("no such column: automation_jobs.priority"),
    )

    with pytest.raises(Exception) as caught:
        raise_job_schema_error(error)

    assert getattr(caught.value, "status_code", None) == 503
    assert getattr(caught.value, "detail", None) == JOB_PRIORITY_MIGRATION_DETAIL


def test_run_strategy_reports_missing_job_priority_migration(db, monkeypatch):
    strategy = Strategy(name="schema-error-line", objective="test route error")
    db.add(strategy)
    db.commit()

    def fail_create_job(*args, **kwargs):
        raise OperationalError(
            "INSERT INTO automation_jobs (priority)",
            {},
            Exception("no such column: automation_jobs.priority"),
        )

    monkeypatch.setattr("content_ops.api.create_job", fail_create_job)

    with pytest.raises(HTTPException) as caught:
        run_strategy(
            strategy.id,
            BackgroundTasks(),
            StrategyRunRequest(combination_id="manual-combination"),
            None,
            db,
        )

    assert caught.value.status_code == 503
    assert caught.value.detail == JOB_PRIORITY_MIGRATION_DETAIL
