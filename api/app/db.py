"""Database engine, sessions and migrations (SQLAlchemy 2 + Alembic).

Postgres (Neon) in production; SQLite works for local development and tests.
"""

from collections.abc import Iterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_API_DIR = Path(__file__).parents[1]


def make_engine(url: str) -> Engine:
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return create_engine(url, pool_pre_ping=True)


def migrate(url: str, *, fresh: bool = False) -> None:
    """Bring the database to the latest migration (fresh=True drops everything first)."""
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "migrations"))
    cfg.attributes["url"] = url
    if fresh:
        command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> Iterator[Session]:
        with self.sessions() as s:
            yield s
