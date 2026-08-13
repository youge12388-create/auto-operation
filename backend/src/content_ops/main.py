from pathlib import Path

from .db import SessionLocal, init_db
from .default_resource_seeding import ensure_default_resources
from .material_categories import ensure_builtin_material_categories
from .models import User
from .security import hash_password
from .settings import get_settings
from .themes import ensure_builtin_themes


def bootstrap() -> None:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    ensure_default_resources(db)
    ensure_builtin_material_categories(db)
    ensure_builtin_themes(db)
    db.commit()
    try:
        if db.query(User).filter(User.email == settings.admin_email.lower()).first() is None:
            db.add(
                User(
                    email=settings.admin_email.lower(),
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            db.commit()
    finally:
        db.close()


def main() -> None:
    import uvicorn

    bootstrap()
    uvicorn.run("content_ops.api:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
