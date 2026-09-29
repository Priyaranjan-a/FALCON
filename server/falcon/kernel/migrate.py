"""Schema migrations, applied automatically at start-up.

    python -m falcon migrate            # upgrade to head
    python -m falcon revision "message" # autogenerate a new revision (development)
"""
from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from ..settings import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    # Percent signs in a URL (encoded passwords) must be escaped for ConfigParser.
    config.set_main_option("sqlalchemy.url", get_settings().resolved_database_url.replace("%", "%%"))
    return config


def upgrade() -> None:
    command.upgrade(alembic_config(), "head")


def revision(message: str) -> None:
    command.revision(alembic_config(), message=message, autogenerate=True)
