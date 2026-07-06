"""Alembic environment: production schema changes for the app tables.
(Dev/test bootstrap uses Base.metadata.create_all; LangGraph manages its own
checkpoint tables.) DATABASE_URL overrides alembic.ini; async URLs are
normalized to their sync drivers for migration runs."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from aura.db.models import Base

config = context.config

url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
url = (url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
          .replace("sqlite+aiosqlite://", "sqlite://"))
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
