from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient


def test_migrations_match_models(client: TestClient) -> None:
    """The migration chain must produce exactly the schema the models declare."""
    from falcon.kernel.database import get_engine
    from falcon.registry import metadata

    with get_engine().connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), metadata)
    assert diff == []
