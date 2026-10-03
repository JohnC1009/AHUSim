"""Tables for M3 (spec §7.1): users, projects, units, unit_versions, runs.

A unit version stores the config in three parts (config, sequence,
conditions) as the spec's table lists them; `unit_config()` puts it back.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JsonDoc = JSON().with_variant(postgresql.JSONB(), "postgresql")


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # M5
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    units: Mapped[list["Unit"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Unit(Base):
    __tablename__ = "units"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    project: Mapped[Project] = relationship(back_populates="units")
    versions: Mapped[list["UnitVersion"]] = relationship(
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="UnitVersion.version.desc()",
    )


class UnitVersion(Base):
    __tablename__ = "unit_versions"
    __table_args__ = (UniqueConstraint("unit_id", "version"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict] = mapped_column(JsonDoc)
    sequence: Mapped[dict] = mapped_column(JsonDoc)
    conditions: Mapped[dict] = mapped_column(JsonDoc)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    unit: Mapped[Unit] = relationship(back_populates="versions")

    def unit_config(self) -> dict:
        return {**self.config, "sequence": self.sequence, "conditions": self.conditions}


class Run(Base):
    """A stored run (spec §6.2). Written from M5 (reproducibility); table exists now."""

    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    unit_version_id: Mapped[str] = mapped_column(
        ForeignKey("unit_versions.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20))  # solve | scenario | sweep | annual
    config_hash: Mapped[str] = mapped_column(String(64))
    sequence_hash: Mapped[str] = mapped_column(String(64))
    conditions_hash: Mapped[str] = mapped_column(String(64))
    engine_version: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    results: Mapped[dict] = mapped_column(JsonDoc)
    failures: Mapped[list] = mapped_column(JsonDoc)
    valid: Mapped[bool] = mapped_column(Boolean)
