from collections.abc import Generator

from fastapi.testclient import TestClient

from content_ops import api, security
from content_ops.models import AuditLog, User
from content_ops.security import SESSION_COOKIE, hash_password


def test_password_change_invalidates_all_existing_sessions(db) -> None:
    user = User(email="password-change@example.com", password_hash=hash_password("old-password-123"), role="admin")
    db.add(user)
    db.commit()

    def override_get_db() -> Generator:
        yield db

    api.app.dependency_overrides[api.get_db] = override_get_db
    api.app.dependency_overrides[security.get_db] = override_get_db
    try:
        legacy_session = security._serializer().dumps({"user_id": user.id})
        with TestClient(api.app) as legacy_client:
            legacy_client.cookies.set(SESSION_COOKIE, legacy_session)
            assert legacy_client.get("/api/v1/auth/me").status_code == 200

        with TestClient(api.app) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "old-password-123"},
            )
            assert login.status_code == 200
            old_session = login.cookies.get(SESSION_COOKIE)
            assert old_session

            rejected = client.post(
                "/api/v1/auth/password",
                json={
                    "current_password": "old-password-123",
                    "new_password": "new-password-123",
                    "confirm_password": "different-password-123",
                },
            )
            assert rejected.status_code == 400

            changed = client.post(
                "/api/v1/auth/password",
                json={
                    "current_password": "old-password-123",
                    "new_password": "new-password-123",
                    "confirm_password": "new-password-123",
                },
            )
            assert changed.status_code == 200
            assert changed.json() == {"ok": True}
            assert client.get("/api/v1/auth/me").status_code == 401

        with TestClient(api.app) as stale_client:
            stale_client.cookies.set(SESSION_COOKIE, old_session)
            assert stale_client.get("/api/v1/auth/me").status_code == 401
            stale_client.cookies.set(SESSION_COOKIE, legacy_session)
            assert stale_client.get("/api/v1/auth/me").status_code == 401

        with TestClient(api.app) as fresh_client:
            assert fresh_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "old-password-123"},
            ).status_code == 401
            assert fresh_client.post(
                "/api/v1/auth/login",
                json={"email": user.email, "password": "new-password-123"},
            ).status_code == 200

        db.refresh(user)
        assert user.session_version == 2
        assert db.query(AuditLog).filter_by(action="user.password.change", user_id=user.id).count() == 1
    finally:
        api.app.dependency_overrides.clear()
