from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from content_ops import api, delivery, security, worker
from content_ops.channels import ENV_CHANNEL_ID
from content_ops.db import Base
from content_ops.material_categories import ensure_builtin_material_categories
from content_ops.models import Article, Job, Publication, User
from content_ops.scheduler import enqueue_due_jobs
from content_ops.security import hash_password
from content_ops.settings import Settings


def test_http_scheduler_worker_automatic_wechat_draft_e2e(tmp_path, monkeypatch):
    settings = Settings(
        app_env="development",
        app_secret="e2e-only-secret-1234567890",
        database_url=f"sqlite:///{(tmp_path / 'e2e.db').as_posix()}",
        admin_email="e2e@example.com",
        admin_password="e2e-password-123456",
        cookie_secure=False,
        storage_dir=tmp_path / "storage",
    )
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    db.add(
        User(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
    ensure_builtin_material_categories(db)
    db.commit()
    db.close()

    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(delivery, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    api.app.dependency_overrides[api.get_db] = override_get_db
    api.app.dependency_overrides[security.get_db] = override_get_db

    draft_calls: list[str] = []

    class FakeWechatClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def create_draft(self, **_):
            draft_calls.append("create_draft")
            return SimpleNamespace(media_id="e2e-draft-media-id")

    monkeypatch.setattr(delivery.WeChatClient, "from_settings", lambda _: FakeWechatClient())

    try:
        with TestClient(api.app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok", "database": "ok"}

            login = client.post(
                "/api/v1/auth/login",
                json={"email": settings.admin_email, "password": settings.admin_password},
            )
            assert login.status_code == 200
            assert login.json()["role"] == "admin"

            model_response = client.post(
                "/api/v1/models",
                json={"provider": "fake", "name": "e2e-fake-model", "enabled": True},
            )
            assert model_response.status_code == 200
            model_id = model_response.json()["id"]

            source_response = client.post(
                "/api/v1/sources",
                json={
                    "name": "e2e-manual-source",
                    "source_type": "manual",
                    "url": "https://example.com/e2e-source",
                    "config": {
                        "title": "E2E source title",
                        "content": (
                            "A deterministic source body with enough factual content for the automated workflow."
                        ),
                    },
                },
            )
            assert source_response.status_code == 200
            source_id = source_response.json()["id"]

            strategy_response = client.post(
                "/api/v1/strategies",
                json={
                    "name": "e2e-automatic-draft",
                    "objective": "Validate the complete scheduled draft workflow",
                    "schedule": "daily@09:00",
                    "automation_level": "L2",
                    "enabled": True,
                    "config": {
                        "selection_mode": "fixed",
                        "default_combination_id": "draft",
                        "strategy_combinations": [
                            {
                                "id": "draft",
                                "name": "自动草稿组合",
                                "enabled": True,
                                "config": {
                                    "source_ids": [source_id],
                                    "model_by_stage": {"writing": model_id},
                                    "delivery_mode": "wechat_draft",
                                    "channel_account_id": ENV_CHANNEL_ID,
                                    "wechat_thumb_media_id": "e2e-thumb-media-id",
                                    "review_rules": {"human_review_required": False},
                                },
                            }
                        ],
                    },
                },
            )
            assert strategy_response.status_code == 200
            strategy_id = strategy_response.json()["id"]

        schedule_db = session_factory()
        try:
            jobs = enqueue_due_jobs(
                schedule_db,
                datetime(2026, 8, 19, 8, 30, tzinfo=timezone.utc),
            )
            assert len(jobs) == 1
            assert jobs[0].strategy_id == strategy_id
            schedule_db.commit()
            queued_job_id = jobs[0].id
        finally:
            schedule_db.close()

        assert worker.claim_and_run_once() is True

        result_db = session_factory()
        try:
            job = result_db.get(Job, queued_job_id)
            assert job is not None
            assert job.status == "succeeded"

            article = result_db.scalar(select(Article).where(Article.job_id == queued_job_id))
            assert article is not None
            assert article.status == "wechat_draft"
            assert article.revisions

            publication = result_db.scalar(
                select(Publication).where(Publication.article_revision_id == article.revisions[0].id)
            )
            assert publication is not None
            assert publication.action == "create_draft"
            assert publication.status == "succeeded"
            assert publication.remote_id == "e2e-draft-media-id"
            assert draft_calls == ["create_draft"]
        finally:
            result_db.close()
    finally:
        api.app.dependency_overrides.pop(api.get_db, None)
        api.app.dependency_overrides.pop(security.get_db, None)
        engine.dispose()
