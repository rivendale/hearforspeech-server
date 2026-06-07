from functools import lru_cache
from os import getenv


def _csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in getenv(name, default).split(",") if item.strip()]


class Settings:
    allowed_origins: list[str]
    max_upload_mb: int
    max_batch_files: int
    api_key: str | None

    def __init__(self) -> None:
        self.allowed_origins = _csv_env(
            "HFS_ALLOWED_ORIGINS",
            "https://hearforspeech.com,http://localhost:5173,http://127.0.0.1:5173",
        )
        self.max_upload_mb = int(getenv("HFS_MAX_UPLOAD_MB", "50"))
        self.max_batch_files = int(getenv("HFS_MAX_BATCH_FILES", "40"))
        self.api_key = getenv("HFS_API_KEY") or None


@lru_cache
def get_settings() -> Settings:
    return Settings()
