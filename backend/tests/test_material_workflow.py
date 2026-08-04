from fastapi import BackgroundTasks
from sqlalchemy import select

from content_ops.api import create_topic_from_material, decide_topic, list_materials, start_topic_writing
from content_ops.ingestion import collect_source
from content_ops.models import Article, EvidenceSource, Source, Strategy, Topic
from content_ops.providers import FakeProvider
from content_ops.schemas import MaterialTopicCreate, TopicDecision
from content_ops.workflow import create_job, run_job


def test_scan_job_collects_materials_and_waits_for_operator_selection(db):
    source = Source(
        name="scan source",
        source_type="manual",
        url="https://example.com/scan",
        config_json={"title": "Collected AI update", "content": "A verified collection result for material triage."},
    )
    strategy = Strategy(name="scan strategy", objective="Collect before writing")
    db.add_all([source, strategy])
    db.commit()

    job = create_job(db, strategy, "scan:one", payload={"mode": "scan"})
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "waiting_topic"
    assert db.scalar(select(Article).where(Article.job_id == job.id)) is None
    materials = list_materials(None, None, None, db)
    assert len(materials) == 1
    assert materials[0].triage_status == "inbox"


def test_operator_selected_material_is_the_evidence_for_writing(db):
    source = Source(
        name="selected source",
        source_type="manual",
        url="https://example.com/selected",
        config_json={
            "title": "The selected news",
            "content": "This is the exact source content selected by the operator.",
        },
    )
    strategy = Strategy(name="writing strategy", objective="Write from an explicitly selected material")
    db.add_all([source, strategy])
    db.commit()
    material = collect_source(db, source)[0]
    db.commit()

    topic = create_topic_from_material(
        material.id,
        MaterialTopicCreate(strategy_id=strategy.id),
        None,
        db,
    )
    assert topic.source_item_id == material.id
    assert db.get(Source, source.id) is not None
    assert db.get(type(material), material.id).triage_status == "selected"

    accepted = decide_topic(topic.id, TopicDecision(decision="accept", comment="Use this item"), None, db)
    job = start_topic_writing(accepted.id, BackgroundTasks(), None, db)
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "waiting_review"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None
    evidence_package_id = article.evidence_json["evidence_package_id"]
    evidence_source = db.scalar(
        select(EvidenceSource).where(EvidenceSource.evidence_package_id == evidence_package_id)
    )
    assert evidence_source is not None
    assert evidence_source.source_item_id == material.id
    assert db.get(Topic, topic.id).status == "writing"
