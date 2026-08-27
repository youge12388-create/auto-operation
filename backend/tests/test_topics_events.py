import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from content_ops import api
from content_ops.api import (
    calendar,
    create_topic,
    decide_topic,
    get_article_evidence,
    job_event_read,
    list_audit_logs,
    list_job_events,
    list_jobs,
    list_topics,
)
from content_ops.models import Article, AuditLog, Job, JobEvent, ModelConfig, Source, Strategy
from content_ops.providers import FakeProvider
from content_ops.schemas import TopicCreate, TopicDecision
from content_ops.workflow import create_job, run_job


class FiniteStreamRequest:
    def __init__(self, last_event_id: str | None = None, connected_cycles: int = 1):
        self.headers = {"last-event-id": last_event_id} if last_event_id else {}
        self._connected_cycles = connected_cycles

    async def is_disconnected(self) -> bool:
        if self._connected_cycles:
            self._connected_cycles -= 1
            return False
        return True


def make_event_job(db, name: str) -> Job:
    strategy = Strategy(name=f"event-stream-{name}", objective="test event stream")
    db.add(strategy)
    db.flush()
    job = Job(strategy_id=strategy.id, idempotency_key=f"event-stream-{name}")
    db.add(job)
    db.flush()
    return job


def add_events(db, job: Job, events: list[tuple[str, datetime]]) -> None:
    db.add_all(
        [
            JobEvent(
                id=event_id,
                job_id=job.id,
                event_type="step_succeeded",
                step_name="writing",
                status="succeeded",
                payload_json={"event_id": event_id},
                created_at=created_at,
            )
            for event_id, created_at in events
        ]
    )
    db.commit()


async def collect_stream_chunks(request: FiniteStreamRequest) -> list[str]:
    response = await api.job_events(request, None)
    return [chunk async for chunk in response.body_iterator]


def stream_chunks(
    db,
    monkeypatch,
    last_event_id: str | None = None,
    connected_cycles: int = 1,
) -> list[str]:
    stream_session = sessionmaker(bind=db.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(api, "ReadSessionLocal", stream_session)
    monkeypatch.setattr(api, "JOB_EVENT_POLL_SECONDS", 0)
    return asyncio.run(collect_stream_chunks(FiniteStreamRequest(last_event_id, connected_cycles)))


def stream_event_ids(chunks: list[str]) -> list[str]:
    return [line.removeprefix("id: ") for chunk in chunks for line in chunk.splitlines() if line.startswith("id: ")]


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


def test_job_event_stream_replays_the_newest_bounded_events_in_order(db, monkeypatch):
    job = make_event_job(db, "recent")
    start = datetime(2026, 8, 23, 9, 30)
    add_events(
        db,
        job,
        [(f"event-{index:03d}", start + timedelta(seconds=index)) for index in range(api.JOB_EVENT_REPLAY_LIMIT + 3)],
    )

    event_ids = stream_event_ids(stream_chunks(db, monkeypatch))

    assert len(event_ids) == api.JOB_EVENT_REPLAY_LIMIT
    assert event_ids[0] == "event-003"
    assert event_ids[-1] == "event-502"


def test_job_event_stream_resumes_after_last_event_id(db, monkeypatch):
    job = make_event_job(db, "resume")
    start = datetime(2026, 8, 23, 10, 0)
    add_events(
        db,
        job,
        [(f"resume-{index:03d}", start + timedelta(seconds=index)) for index in range(5)],
    )

    event_ids = stream_event_ids(stream_chunks(db, monkeypatch, "resume-001"))

    assert event_ids == ["resume-002", "resume-003", "resume-004"]


def test_job_event_stream_keeps_same_timestamp_events_after_reconnect(db, monkeypatch):
    job = make_event_job(db, "same-timestamp")
    timestamp = datetime(2026, 8, 23, 10, 15)
    add_events(
        db,
        job,
        [
            ("same-z", timestamp),
            ("same-a", timestamp),
            ("later", timestamp + timedelta(seconds=1)),
        ],
    )

    event_ids = stream_event_ids(stream_chunks(db, monkeypatch, "same-z", connected_cycles=2))

    assert event_ids == ["same-a", "later"]


def test_job_api_output_redacts_legacy_error_and_event_payloads(db):
    secret = "legacy-secret-value-123456"
    job = make_event_job(db, "legacy-redaction")
    job.last_error = f"legacy error: Bearer {secret}; api_key={secret}"
    event = JobEvent(
        job_id=job.id,
        event_type="render_fallback",
        status="warning",
        payload_json={
            "reason": f"legacy reason: access_token={secret}",
            "api_key": secret,
            "nested": {"authorization": f"Bearer {secret}"},
        },
    )
    db.add(event)
    db.commit()

    job_result = list_jobs(None, db)[0]
    event_result = job_event_read(event)

    assert secret not in (job_result.last_error or "")
    assert "[redacted]" in (job_result.last_error or "")
    assert secret not in str(event_result.payload)
    assert event_result.payload["api_key"] == "[redacted]"
    assert event_result.payload["nested"]["authorization"] == "[redacted]"
