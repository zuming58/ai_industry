from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_prefix="KONGPU_",
        extra="ignore",
    )

    data_dir: Path = REPOSITORY_ROOT / ".local-data"
    database_url: str | None = None
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    max_upload_bytes: int = 20 * 1024 * 1024
    max_xlsx_uncompressed_bytes: int = 100 * 1024 * 1024
    max_xlsx_entries: int = 2_000

    @property
    def project_root(self) -> Path:
        return REPOSITORY_ROOT

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        path = (self.data_dir / "kongpu.sqlite3").resolve()
        return f"sqlite:///{path.as_posix()}"

    @property
    def artifact_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def repository_dir(self) -> Path:
        return self.data_dir / "repositories"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.repository_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
