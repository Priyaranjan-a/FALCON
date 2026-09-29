"""Test fixtures: every test gets a fresh database built by the real
migrations, so the migration chain is exercised on every run."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["FALCON_ENVIRONMENT"] = "test"

OWNER = {"email": "owner@falcon.test", "name": "Asha Raman", "password": "Quantum-Ready-2035"}
SETUP = {
    "organisation": {"name": "National Test Agency", "sector": "government", "country": "IN"},
    "threat_model": {"crqc_scenario": "moderate", "risk_tolerance": 0.05},
    "owner": OWNER,
}
WRITE = {"X-Falcon-Request": "1"}


def _reset_caches() -> None:
    from falcon.kernel import database
    from falcon import settings

    settings.get_settings.cache_clear()
    database.get_engine.cache_clear()
    database.get_sessionmaker.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("FALCON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FALCON_CONSOLE_DIST", str(tmp_path / "no-console"))
    # Tests run as a server install: folders are scannable only under explicit roots.
    fixtures = Path(__file__).resolve().parents[2] / "fixtures"
    monkeypatch.setenv("FALCON_SCAN_ROOTS", json.dumps([str(fixtures), str(tmp_path)]))
    _reset_caches()
    from falcon.app import create_app
    from falcon.domains.identity import api as identity_api

    identity_api._sign_in_limiter.reset()
    with TestClient(create_app()) as test_client:
        yield test_client
    from falcon.kernel.database import get_engine

    get_engine().dispose()
    _reset_caches()


@pytest.fixture
def owner(client: TestClient) -> TestClient:
    """A client signed in as the organisation owner."""
    response = client.post("/api/v1/setup", json=SETUP)
    assert response.status_code == 201, response.text
    return client


def db_session():
    from falcon.kernel.database import get_sessionmaker

    return get_sessionmaker()()


def invite_and_activate(owner: TestClient, email: str, role: str) -> TestClient:
    """Invite a member as the owner and return a separate client signed in as them."""
    response = owner.post("/api/v1/members", json={"email": email, "name": "Dev Kapoor", "role": role}, headers=WRITE)
    assert response.status_code == 201, response.text
    secret = response.json()["activation_link"].split("#", 1)[1]
    member = TestClient(owner.app)
    activated = member.post("/api/v1/auth/activate", json={"token": secret, "name": "Dev Kapoor", "password": "Lattice-Based-9876"})
    assert activated.status_code == 200, activated.text
    return member
