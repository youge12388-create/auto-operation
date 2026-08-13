from sqlalchemy import select

from content_ops.api import (
    calendar,
    create_topic,
    decide_topic,
    get_article_evidence,
    list_audit_logs,
    list_job_events,
    list_topics,
)
from content_ops.models import Article, AuditLog, ModelConfig, Source, Strategy
from content_ops.providers import FakeProvider
from content_ops.schemas import TopicCreate, TopicDecision
from content_ops.workflow import create_job, run_job


def test_topic_evidence_events_and_audit_api(db):
    source = Source(
        name="manual",
        source_type="manual",
        url="https://example.com/item",
        config_json={"title": "API test", "content": "verified content"},
    )
    strategy = Strategy(name="topic-api", objective="test topics")
    model = ModelConfig(provider="fake", name="topic-api-translation-model")
    db.add_all([source, strategy, model])
    db.commit()
    job = create_job(db, strategy, "topic-api-job")
    run_job(db, job.id, FakeProvider())

    topics = list_topics(None, None, db)
    assert topics and topics[0].status == "writing"
    changed = decide_topic(topics[0].id, TopicDecision(decision="reject", comment="manual"), None, db)
    assert changed.status == "rejected"

    article = db.scalar(select(Article).where(Article.job_id == job.id))
    assert article is not None
    evidence = get_article_evidence(article.id, None, db)
    assert evidence.claims and evidence.sources
    events = list_job_events(job.id, None, db)
    assert any(event.event_type == "step_started" for event in events)
    assert any(event.event_type == "step_succeeded" for event in events)
    assert db.query(AuditLog).count() >= 1
    assert list_audit_logs(None, db)
    assert calendar(None, None, None, db)[0].job_id == job.id


def test_manual_topic_creation_is_visible_in_list(db):
    strategy = Strategy(name="manual-topic", objective="test manual topic")
    db.add(strategy)
    db.commit()

    created = create_topic(
        TopicCreate(strategy_id=strategy.id, title="人工选题", score=72, rationale="人工补充"),
        None,
        db,
    )

    assert created.title == "人工选题"
    assert created.status == "candidate"
    assert any(item.id == created.id for item in list_topics(None, None, db))