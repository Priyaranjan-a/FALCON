"""Alembic environment bound to FALCON's engine and metadata."""
from __future__ import annotations

from alembic import context

from falcon.kernel.database import build_engine
from falcon.registry import metadata

config = context.config


def run_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = build_engine(config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=metadata,
            render_as_batch=True,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
