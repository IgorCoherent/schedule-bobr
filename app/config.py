import os
from functools import lru_cache


@lru_cache
def get_settings() -> "Settings":
    return Settings()


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings:
    def __init__(self) -> None:
        self.database_url: str = _normalize_database_url(os.environ["DATABASE_URL"])
        self.secret_key: str = os.environ["SECRET_KEY"]
        self.env: str = os.environ.get("ENV", "development")
        self.seed_on_start: bool = os.environ.get("SEED_ON_START", "true").lower() == "true"
        self.bootstrap_on_start: bool = (
            os.environ.get("BOOTSTRAP_ON_START", "false").lower() == "true"
        )
        self.admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
        self.admin_password: str = os.environ.get("ADMIN_PASSWORD", "admin")
        self.timezone: str = "Europe/Minsk"

    @property
    def session_https_only(self) -> bool:
        return self.env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return 5 * 1024 * 1024

    @property
    def max_text_length(self) -> int:
        return 2000
