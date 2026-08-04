import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import select

from content_ops.api import (
    add_model,
    delete_model,
    disable_skill,
    import_skill,
    list_skill_versions,
    model_connection_test,
    publish_skill,
)
from content_ops.models import Job, ModelConfig, SkillVersion, Strategy
from content_ops.schemas import ModelCreate


def skill_zip(version: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("skill.yaml", f"name: rewrite-demo\ntype: rewrite\nversion: {version}\n")
        archive.writestr("prompt.md", "保留事实并减少模板化表达")
    return buffer.getvalue()


def test_skill_import_keeps_versions_and_status_transitions(db):
    first = asyncio.run(import_skill(UploadFile(filename="skill.zip", file=io.BytesIO(skill_zip("1.0.0"))), None, db))
    second = asyncio.run(import_skill(UploadFile(filename="skill.zip", file=io.BytesIO(skill_zip("1.1.0"))), None, db))

    versions = db.scalars(
        select(SkillVersion).where(SkillVersion.skill_id == first.id).order_by(SkillVersion.version)
    ).all()
    listed = list_skill_versions(first.id, None, db)
    published = publish_skill(first.id, None, db)
    disabled = disable_skill(first.id, None, db)

    assert second.version == "1.1.0"
    assert [item.version for item in versions] == ["1.0.0", "1.1.0"]
    assert [item.version for item in listed] == ["1.1.0", "1.0.0"]
    assert published.status == "published"
    assert disabled.status == "disabled"


def test_fake_model_connection_test_is_local_and_redacted(db):
    model = add_model(ModelCreate(provider="fake", name="fake-test"), None, db)
    result = model_connection_test(model.id, None, db)

    assert result.ok is True
    assert "api_key" not in result.message.lower()


def test_model_delete_blocks_references_but_preserves_completed_history(db):
    model = add_model(ModelCreate(provider="fake", name="deletable-model"), None, db)
    strategy = Strategy(name="model-reference", objective="test", config_json={"model_by_stage": {"writing": model.id}})
    db.add(strategy)
    db.commit()

    with pytest.raises(HTTPException) as strategy_error:
        delete_model(model.id, None, db)
    assert strategy_error.value.status_code == 409
    assert "策略" in str(strategy_error.value.detail)

    strategy.config_json = {}
    job = Job(
        strategy_id=strategy.id,
        idempotency_key="model-delete-active-job",
        status="queued",
        payload_json={"runtime_snapshot": {"execution_config": {"model_by_stage": {"writing": model.id}}}},
    )
    db.add(job)
    db.commit()

    with pytest.raises(HTTPException) as job_error:
        delete_model(model.id, None, db)
    assert job_error.value.status_code == 409
    assert "任务" in str(job_error.value.detail)

    job.status = "succeeded"
    db.commit()
    result = delete_model(model.id, None, db)

    assert result == {"deleted": True}
    assert db.get(ModelConfig, model.id) is None
    assert db.get(Job, job.id) is not None