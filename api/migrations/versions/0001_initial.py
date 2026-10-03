"""M3 tables: users, projects, units, unit_versions, runs.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None

JsonDoc = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("clerk_id", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("org_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "units",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(32),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "unit_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(32),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("config", JsonDoc, nullable=False),
        sa.Column("sequence", JsonDoc, nullable=False),
        sa.Column("conditions", JsonDoc, nullable=False),
        sa.Column(
            "created_by", sa.String(32), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("unit_id", "version"),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "unit_version_id",
            sa.String(32),
            sa.ForeignKey("unit_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("sequence_hash", sa.String(64), nullable=False),
        sa.Column("conditions_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("results", JsonDoc, nullable=False),
        sa.Column("failures", JsonDoc, nullable=False),
        sa.Column("valid", sa.Boolean, nullable=False),
    )


def downgrade() -> None:
    for table in ("runs", "unit_versions", "units", "projects", "users"):
        op.drop_table(table)
