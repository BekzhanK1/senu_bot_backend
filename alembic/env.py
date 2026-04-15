"""Alembic environment (sync URL; strip +asyncpg from DB_URL)."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database.models import Base

import database.models_v2  # noqa: F401 — register metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_sync_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("DB_URL") or ""
    if not url:
        raise RuntimeError(
            "Set DATABASE_URL or DB_URL for Alembic (e.g. postgresql://user:pass@host:5432/dbname)."
        )
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")
    # Bare postgresql:// defaults to psycopg2 in SQLAlchemy; we ship psycopg3 (psycopg package).
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_sync_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
