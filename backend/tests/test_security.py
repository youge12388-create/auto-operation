from content_ops.security import decrypt_secret, encrypt_secret, hash_password, verify_password


def test_password_and_secret_round_trip():
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong", password_hash)
    encrypted = encrypt_secret("provider-secret")
    assert encrypted != "provider-secret"
    assert decrypt_secret(encrypted) == "provider-secret"


def test_user_creation_hashes_password_and_exposes_role_only(db):
    from content_ops.api import add_user, list_users
    from content_ops.schemas import UserCreate

    created = add_user(
        UserCreate(email="reviewer@example.com", password="long-reviewer-password", role="reviewer"),
        None,
        db,
    )

    assert created.email == "reviewer@example.com"
    assert created.role == "reviewer"
    assert "long-reviewer-password" not in str(created.model_dump())
    assert list_users(None, db)[0].role == "reviewer"
