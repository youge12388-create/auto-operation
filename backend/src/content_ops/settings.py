from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    app_env: str = "development"
    app_secret: str = Field(default="development-only-secret", min_length=16)
    database_url: str = "sqlite:///./data/content_ops.db"
    redis_url: str = ""  # deprecated: Postgres LISTEN/NOTIFY replaces Redis for job wake-up
    admin_email: str = "admin@example.com"
    admin_password: str = "admin"
    cookie_secure: bool = False
    storage_dir: Path = Path("storage")
    job_lease_seconds: int = Field(default=300, gt=0)
    max_job_attempts: int = Field(default=3, ge=1, le=10)
    wechat_app_id: str | None = None
    wechat_app_secret: str | None = None
    wechat_api_base_url: str = "https://api.weixin.qq.com"
    wechat_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    auto_publish_enabled: bool = False


def _resolve_sqlite_url(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        return database_url
    raw_path = database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return f"sqlite:///{path.as_posix()}"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_url = _resolve_sqlite_url(settings.database_url)
    if not settings.storage_dir.is_absolute():
        settings.storage_dir = PROJECT_ROOT / settings.storage_dir
    return settings