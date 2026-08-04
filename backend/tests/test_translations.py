from sqlalchemy import select

from content_ops.models import ModelCallLog, ModelConfig, Source, SourceItem, Strategy
from content_ops.providers import FakeProvider
from content_ops.workflow import create_job, run_job


def test_automation_translates_foreign_material_before_writing(db):
    original = (
        "Google announced a new research workflow for AI agents. The release explains how the system "
        "coordinates tools, verifies intermediate results, and records sources for later review."
    )
    source = Source(
        name="English source",
        source_type="manual",
        url="https://example.com/english-source",
        config_json={"title": "AI agent workflow", "content": original},
    )
    strategy = Strategy(name="translation-strategy", objective="Chinese editorial workflow")
    model = ModelConfig(name="translation-model", provider="fake", enabled=True)
    db.add_all([source, strategy, model])
    db.commit()

    job = create_job(db, strategy, "translation-job")
    run_job(db, job.id, FakeProvider())

    item = db.scalar(select(SourceItem).where(SourceItem.source_id == source.id))
    assert item is not None
    assert item.title.startswith("\u4e2d\u6587\u8bd1\u6587\uff1a")
    assert item.content.startswith("\u3010\u4e2d\u6587\u8bd1\u6587\u3011")
    assert item.content != original
    assert item.content.endswith(original)
    translation_log = db.scalar(
        select(ModelCallLog).where(ModelCallLog.job_id == job.id, ModelCallLog.stage == "translation")
    )
    assert translation_log is not None
    assert translation_log.status == "succeeded"