import json

from fastapi import BackgroundTasks
from sqlalchemy import select

from content_ops.api import (
    create_topic_from_material,
    create_topic_from_materials,
    decide_topic,
    list_materials,
    start_topic_writing,
)
from content_ops.ingestion import collect_source
from content_ops.models import Article, EvidenceSource, ModelConfig, Source, Strategy, Topic
from content_ops.providers import CompletionResponse, FakeProvider
from content_ops.schemas import MaterialBatchTopicCreate, MaterialTopicCreate, TopicDecision
from content_ops.workflow import create_job, run_job


class TopicRecommendationProvider:
    def complete(self, request):
        material_id = json.loads(request.user)["materials"][0]["id"]
        return CompletionResponse(
            text=json.dumps(
                {
                    "topics": [
                        {
                            "title": "A real recommendation",
                            "rationale": "Timely and useful",
                            "material_ids": [material_id],
                            "score": 91,
                            "scores": {"heat": 92, "timeliness": 94, "reader_value": 90, "strategy_fit": 88},
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
        )


def test_scan_job_collects_materials_and_waits_for_operator_selection(db):
    source = Source(
        name="scan source",
        source_type="manual",
        url="https://example.com/scan",
        config_json={"title": "Collected AI update", "content": "A verified collection result for material triage."},
    )
    model = ModelConfig(provider="fake", name="topic-test-model")
    db.add_all([source, model])
    db.flush()
    strategy = Strategy(
        name="scan strategy",
        objective="Collect before writing",
        config_json={"default_model_id": model.id},
    )
    db.add(strategy)
    db.commit()

    job = create_job(db, strategy, "scan:one", payload={"mode": "scan"})
    result = run_job(db, job.id, TopicRecommendationProvider())

    assert result.status == "waiting_topic"
    assert db.scalar(select(Article).where(Article.job_id == job.id)) is None
    materials = list_materials(None, None, None, db)
    assert len(materials) == 1
    assert materials[0].triage_status == "inbox"
    topic = db.scalar(select(Topic).where(Topic.strategy_id == strategy.id))
    assert topic is not None
    assert topic.score == 91
    assert [link.source_item_id for link in topic.material_links] == [materials[0].id]


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
    strategy.config_json = {"review_rules": {"human_review_required": True}}
    model = ModelConfig(provider="fake", name="material-translation-model")
    db.add_all([source, strategy, model])
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
    evidence_source = db.scalar(select(EvidenceSource).where(EvidenceSource.evidence_package_id == evidence_package_id))
    assert evidence_source is not None
    assert evidence_source.source_item_id == material.id
    assert db.get(Topic, topic.id).status == "writing"


def test_multiple_retained_materials_are_frozen_into_the_evidence_package(db):
    sources = [
        Source(
            name=f"supporting source {index}",
            source_type="manual",
            url=f"https://example.com/supporting-{index}",
            config_json={"title": f"Evidence {index}", "content": f"Verified fact {index}"},
        )
        for index in range(2)
    ]
    strategy = Strategy(name="multi-material strategy", objective="Use every selected source")
    strategy.config_json = {"review_rules": {"human_review_required": True}}
    model = ModelConfig(provider="fake", name="multi-material-translation-model")
    db.add_all([*sources, strategy, model])
    db.commit()
    materials = [collect_source(db, source)[0] for source in sources]
    db.commit()

    topic = create_topic_from_materials(
        MaterialBatchTopicCreate(
            strategy_id=strategy.id,
            material_ids=[material.id for material in materials],
            title="Combined evidence article",
        ),
        None,
        db,
    )
    accepted = decide_topic(topic.id, TopicDecision(decision="accept"), None, db)
    job = start_topic_writing(accepted.id, BackgroundTasks(), None, db)
    result = run_job(db, job.id, FakeProvider())

    assert result.status == "waiting_review"
    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None
    evidence_sources = db.scalars(
        select(EvidenceSource).where(EvidenceSource.evidence_package_id == article.evidence_json["evidence_package_id"])
    ).all()
    assert {source.source_item_id for source in evidence_sources} == {material.id for material in materials}
    assert all(material.triage_status == "used" for material in materials)