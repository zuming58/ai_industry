from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> Engine:
    url = settings.resolved_database_url
    runtime_engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        future=True,
    )
    if url.startswith("sqlite"):
        @event.listens_for(runtime_engine, "connect")
        def configure_sqlite(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return runtime_engine


@dataclass
class DatabaseRuntime:
    settings: Settings

    def __post_init__(self) -> None:
        self.engine = build_engine(self.settings)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )

    def sessions(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session

    def create_schema(self) -> None:
        from . import models  # noqa: F401

        Base.metadata.create_all(bind=self.engine)

    def upgrade_schema(self) -> None:
        from alembic import command
        from alembic.config import Config

        config_path = self.settings.project_root / "services" / "api" / "alembic.ini"
        config = Config(str(config_path))
        config.set_main_option("sqlalchemy.url", self.settings.resolved_database_url.replace("%", "%%"))
        command.upgrade(config, "head")

    def dispose(self) -> None:
        self.engine.dispose()


default_database = DatabaseRuntime(get_settings())
engine = default_database.engine
SessionLocal = default_database.session_factory


def get_session() -> Generator[Session, None, None]:
    yield from default_database.sessions()


def create_schema() -> None:
    default_database.create_schema()
