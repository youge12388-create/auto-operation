"""Regression tests for SQLite write-lock held across model network calls.

The collection pipeline must not keep a SQLite write transaction open while a
model call (translation/classification) is in flight: the API process and the
worker process share the same database file, and a long-held write lock makes
the other side fail with `sqlite3.OperationalError: database is locked` after
the busy timeout. These tests pin the fix: no lock during the model call, and
collection failures surface the original exception instead of a
PendingRollbackError.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time

import httpx
import pytest
from sqlalchemy import create_engine, event, insert, select
from sqlalchemy.orm import sessionmaker

from content_ops.db import Base
from content_ops.ingestion import collect_source
from content_ops.models import ModelCallLog, ModelConfig, Source, SourceItem
from content_ops.providers import CompletionRequest, CompletionResponse
from content_ops.translations import translate_source_items

_ENGLISH_MATERIAL = (
    "Google announced a new research workflow for AI agents. The release explains how the "
    "system coordinates tools, verifies intermediate results, and records sources for review."
)


class _SlowTranslationProvider:
    """Signals while the fake 'network' translation call is in flight."""

    def __init__(self, entered: threading.Event):
        self._entered = entered

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._entered.set()
        time.sleep(2.0)
        if request.user.startswith("MATERIAL_CLASSIFICATION_JSON"):
            payload = json.loads(request.user.split("\n", 1)[1])
            materials = payload.get("materials") or []
            categories = payload.get("categories") or []
            return CompletionResponse(
                text=json.dumps(
                    {
                        "materials": [
                            {
                                "id": item["id"],
                                "category_id": categories[0]["id"],
                                "confidence": 90,
                                "reason": "测试分类",
                            }
                            for item in materials
                        ]
                    },
                    ensure_ascii=False,
                ),
                input_tokens=10,
                output_tokens=20,
            )
        title = request.user.split("TITLE:", 1)[1].split("\nCONTENT:", 1)[0].strip()
        content = request.user.split("\nCONTENT:\n", 1)[1].strip()
        return CompletionResponse(
            text=json.dumps(
                {"title": f"中文译文：{title}", "content": f"中文译文：{content}"},
                ensure_ascii=False,
            ),
            input_tokens=10,
            output_tokens=20,
        )


class _SlowClassificationProvider:
    """Signals while the fake 'network' classification call is in flight."""

    def __init__(self, entered: threading.Event):
        self._entered = entered

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._entered.set()
        time.sleep(2.0)
        payload = json.loads(request.user.split("\n", 1)[1])
        materials = payload.get("materials") or []
        categories = payload.get("categories") or []
        return CompletionResponse(
            text=json.dumps(
                {
                    "materials": [
                        {
                            "id": item["id"],
                            "category_id": categories[0]["id"],
                            "confidence": 90,
                            "reason": "测试分类",
                        }
                        for item in materials
                    ]
                },
                ensure_ascii=False,
            ),
            input_tokens=10,
            output_tokens=20,
        )


class _FailingProvider:
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise RuntimeError("translation backend unavailable")


def _file_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'lock.db'}",
        connect_args={"check_same_thread": False, "timeout": 0.5},
    )
    Base.metadata.create_all(engine)
    return engine


def _seed_source(session, name: str = "english-source") -> Source:
    source = Source(
        name=name,
        source_type="manual",
        url=f"https://example.com/{name}",
        config_json={"title": "AI agent workflow", "content": _ENGLISH_MATERIAL},
    )
    model = ModelConfig(name="translation-model", provider="fake", enabled=True)
    session.add_all([source, model])
    session.commit()
    return source


def test_translation_does_not_hold_write_lock_during_model_call(tmp_path):
    engine = _file_engine(tmp_path)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session_a = session_factory()
    source = _seed_source(session_a)

    entered = threading.Event()
    thread_error: list[Exception] = []

    def run_collect() -> None:
        try:
            collect_source(session_a, source, _SlowTranslationProvider(entered))
        except Exception as exc:  # pragma: no cover - failure path for diagnosis
            thread_error.append(exc)

    thread = threading.Thread(target=run_collect)
    thread.start()
    try:
        assert entered.wait(timeout=10), "translation provider was not called"

        # While the model call is in flight another connection must still be
        # able to write. Before the fix this raised OperationalError after the
        # 0.5s busy timeout because the collect session held the write lock.
        session_b = session_factory()
        try:
            session_b.add(
                Source(
                    name="other",
                    source_type="manual",
                    url="https://example.com/other",
                    config_json={"title": "其他", "content": "其他内容"},
                )
            )
            session_b.commit()
        finally:
            session_b.close()
    finally:
        thread.join(timeout=15)

    assert not thread_error, f"collect_source failed: {thread_error[0]}"
    session_a.close()
    engine.dispose()


def test_collect_source_failure_preserves_original_exception_and_sets_last_error(db):
    source = _seed_source(db)
    with pytest.raises(RuntimeError, match="translation backend unavailable"):
        collect_source(db, source, _FailingProvider())
    db.rollback()
    assert source.last_error == "translation backend unavailable"


def test_aihot_classification_does_not_hold_write_lock_during_model_call(tmp_path, monkeypatch):
    engine = _file_engine(tmp_path)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session_a = session_factory()

    def fake_get(url, params=None, timeout=None):
        return httpx.Response(
            200,
            request=httpx.Request("GET", str(url)),
            json={
                "items": [
                    {
                        "id": "item-1",
                        "title": "NVIDIA 发布新模型",
                        "summary": "NVIDIA 发布面向 Robotaxi 的开源视觉语言动作模型。",
                        "category": "ai-models",
                        "publishedAt": "2026-08-05T01:00:00Z",
                        "links": {"original": "https://example.com/nvidia"},
                    },
                    {
                        "id": "item-2",
                        "title": "某产品发布",
                        "summary": "某公司发布新产品。",
                        "category": None,
                        "publishedAt": "2026-08-05T02:00:00Z",
                        "links": {"original": "https://example.com/product"},
                    },
                ]
            },
        )

    monkeypatch.setattr("content_ops.ingestion.httpx.get", fake_get)
    source = Source(
        name="AI HOT",
        source_type="aihot_api",
        url="https://aihot.virxact.com/api/v1/items",
        config_json={"window": "24h", "limit": 100},
    )
    model = ModelConfig(name="classification-model", provider="fake", enabled=True)
    session_a.add_all([source, model])
    session_a.commit()

    entered = threading.Event()
    thread_error: list[Exception] = []

    def run_collect() -> None:
        try:
            collect_source(session_a, source, _SlowClassificationProvider(entered), model)
        except Exception as exc:  # pragma: no cover - failure path for diagnosis
            thread_error.append(exc)

    thread = threading.Thread(target=run_collect)
    thread.start()
    try:
        assert entered.wait(timeout=10), "classification provider was not called"

        # Creating the AI HOT category flushed a write transaction; it must not
        # stay open across the classification model call.
        session_b = session_factory()
        try:
            session_b.add(
                Source(
                    name="other",
                    source_type="manual",
                    url="https://example.com/other",
                    config_json={"title": "其他", "content": "其他内容"},
                )
            )
            session_b.commit()
        finally:
            session_b.close()
    finally:
        thread.join(timeout=15)

    assert not thread_error, f"collect_source failed: {thread_error[0]}"
    session_a.close()
    engine.dispose()


def test_translation_partial_failure_keeps_succeeded_items_and_failed_log(db):
    source = Source(name="english", source_type="manual", url="https://example.com/english", config_json={})
    db.add(source)
    db.commit()
    items: list[SourceItem] = []
    for index in range(2):
        text = (
            f"Research team {index} released a detailed workflow for evaluating AI agents "
            "across real tool-use tasks."
        )
        item = SourceItem(
            source_id=source.id,
            title=f"Agent workflow {index}",
            url=f"https://example.com/article-{index}",
            canonical_url=f"https://example.com/article-{index}",
            content=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            status="verified",
            classification_status="pending",
        )
        db.add(item)
        items.append(item)
    db.commit()

    class FlakyProvider:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: CompletionRequest) -> CompletionResponse:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("translation backend unavailable")
            title = request.user.split("TITLE:", 1)[1].split("\nCONTENT:", 1)[0].strip()
            content = request.user.split("\nCONTENT:\n", 1)[1].strip()
            return CompletionResponse(
                text=json.dumps(
                    {"title": f"中文译文：{title}", "content": f"中文译文：{content}"},
                    ensure_ascii=False,
                ),
                input_tokens=10,
                output_tokens=20,
            )

    with pytest.raises(RuntimeError, match="translation backend unavailable"):
        translate_source_items(db, None, items, FlakyProvider(), None)
    db.rollback()

    # The first item was committed before the second one failed; a caller that
    # rolls back must still see it and the failed call log.
    assert items[0].content.startswith("\u3010\u4e2d\u6587\u8bd1\u6587\u3011")
    failed_log = db.scalar(
        select(ModelCallLog).where(
            ModelCallLog.stage == "translation", ModelCallLog.status == "failed"
        )
    )
    assert failed_log is not None
    assert failed_log.error == "translation backend unavailable"


def _immediate_engine(tmp_path, timeout: float = 5.0):
    """A file-backed engine configured exactly like db.py's SQLite engine:
    connect-event disables pysqlite auto-begin and every transaction starts
    with BEGIN IMMEDIATE."""
    from content_ops.db import _begin_immediate, _configure_sqlite

    engine = create_engine(
        f"sqlite:///{tmp_path / 'immediate.db'}",
        connect_args={"check_same_thread": False, "timeout": timeout},
    )
    event.listen(engine, "connect", _configure_sqlite)
    event.listen(engine, "begin", _begin_immediate)
    Base.metadata.create_all(engine)
    return engine


def test_begin_immediate_queues_writer_behind_held_write_lock(tmp_path):
    """With BEGIN IMMEDIATE a second writer queues under busy_timeout instead
    of failing immediately on a deferred read->write lock upgrade (the failure
    mode that surfaced as `database is locked` under the API/worker pair)."""
    engine = _immediate_engine(tmp_path)

    conn_a = engine.connect()
    trans_a = conn_a.begin()
    conn_a.execute(
        insert(Source.__table__).values(
            name="a", source_type="manual", url="https://example.com/a", config_json={}
        )
    )

    thread_error: list[Exception] = []

    def write_b() -> None:
        try:
            with engine.begin() as conn:
                conn.execute(
                    insert(Source.__table__).values(
                        name="b", source_type="manual", url="https://example.com/b", config_json={}
                    )
                )
        except Exception as exc:  # pragma: no cover - failure path for diagnosis
            thread_error.append(exc)

    thread = threading.Thread(target=write_b)
    thread.start()
    # Give the second writer time to attempt its write. Before BEGIN IMMEDIATE
    # (deferred transactions) this raises `database is locked` immediately.
    time.sleep(0.5)
    assert not thread_error, f"second writer failed instead of waiting: {thread_error[0]}"

    trans_a.commit()
    thread.join(timeout=10)
    assert not thread_error, f"second writer failed after lock release: {thread_error[0]}"
    conn_a.close()
    engine.dispose()


def test_worker_collect_releases_write_lock_before_translation_call(tmp_path, monkeypatch):
    """The worker path passes no provider, so collect_source looks the model up
    in the database first. That lookup opens a BEGIN IMMEDIATE transaction; it
    must be committed before the translation model call, otherwise the write
    lock is held across the network request and blocks the API process."""
    engine = _immediate_engine(tmp_path, timeout=1.0)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session_a = session_factory()

    source = Source(
        name="english",
        source_type="manual",
        url="https://example.com/worker-english",
        config_json={"title": "AI agent workflow", "content": _ENGLISH_MATERIAL},
    )
    model = ModelConfig(name="translation-model", provider="fake", enabled=True)
    session_a.add_all([source, model])
    session_a.commit()

    entered = threading.Event()
    monkeypatch.setattr(
        "content_ops.ingestion.provider_for",
        lambda model_config: _SlowTranslationProvider(entered),
    )
    thread_error: list[Exception] = []

    def run_collect() -> None:
        try:
            collect_source(session_a, source)
        except Exception as exc:  # pragma: no cover - failure path for diagnosis
            thread_error.append(exc)

    thread = threading.Thread(target=run_collect)
    thread.start()
    try:
        assert entered.wait(timeout=10), "translation provider was not called"

        # While the translation call is in flight another connection must still
        # be able to write. Before the fix the model lookup left a BEGIN
        # IMMEDIATE transaction (write lock) open across the model call.
        session_b = session_factory()
        try:
            session_b.add(
                Source(
                    name="other",
                    source_type="manual",
                    url="https://example.com/other",
                    config_json={"title": "其他", "content": "其他内容"},
                )
            )
            session_b.commit()
        finally:
            session_b.close()
    finally:
        thread.join(timeout=15)

    assert not thread_error, f"collect_source failed: {thread_error[0]}"
    session_a.close()
    engine.dispose()
