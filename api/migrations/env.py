"""Alembic environment: the URL comes from app.db.migrate() or DATABASE_URL."""

import os

from alembic import context

from app.db import make_engine
from app.models import Base

config = context.config
url = config.attributes.get("url") or os.environ.get(
    "DATABASE_URL", "sqlite:///./ahuverify-dev.db"
)

with make_engine(url).connect() as connection:
    context.configure(
        connection=connection, target_metadata=Base.metadata, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()
