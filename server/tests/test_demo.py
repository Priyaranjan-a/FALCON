"""First-run demonstration: a fresh installation started with --demo opens as
a working platform, signed in with the printed admin credentials."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from conftest import SETUP, WRITE


def test_demo_seeds_a_fresh_installation_once(monkeypatch, request, capsys) -> None:
    monkeypatch.setenv("FALCON_DEMO", "true")
    monkeypatch.setenv("FALCON_DEMO_BENCHMARKS", "false")
    client: TestClient = request.getfixturevalue("client")

    printed = capsys.readouterr().out
    assert "admin@falcon.local" in printed and "Quantum-Safe-2026!" in printed

    status = client.get("/api/v1/setup").json()
    assert status["initialised"] is True
    signed_in = client.post("/api/v1/auth/sign-in", json={"email": "admin@falcon.local", "password": "Quantum-Safe-2026!"}, headers=WRITE)
    assert signed_in.status_code == 200, signed_in.text

    systems = client.get("/api/v1/systems").json()
    assert systems["total"] == 10 and {"PAY-GW", "CITIZEN-ID", "PKI-ROOT"} <= {s["code"] for s in systems["items"]}

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        scans = client.get("/api/v1/scans").json()
        if scans and all(s["status"] not in ("queued", "running") for s in scans):
            break
        time.sleep(0.5)
    assert len(scans) == 4 and all(s["status"] == "succeeded" for s in scans), scans

    summary = client.get("/api/v1/risk/summary").json()
    assert summary["total"] > 100 and summary["bands"]["critical"] > 0

    # The first signed snapshot follows the scans.
    while time.monotonic() < deadline:
        snapshots = client.get("/api/v1/reports/snapshots").json()["items"]
        if snapshots:
            break
        time.sleep(0.5)
    assert snapshots and snapshots[0]["label"] == "First inventory"
    assert client.get(f"/api/v1/reports/snapshots/{snapshots[0]['id']}").json()["verification"]["valid"]

    # A second start never re-seeds an installation that exists.
    from falcon import demo

    capsys.readouterr()
    assert demo.seed() is False
    assert client.get("/api/v1/systems").json()["total"] == 10
    assert "admin@falcon.local" in capsys.readouterr().out  # the sign-in is repeated, not lost


def test_an_installation_owned_by_someone_else_says_so(monkeypatch, request, capsys) -> None:
    """Started with --demo over an existing installation: name the owner instead of failing silently."""
    monkeypatch.setenv("FALCON_DEMO", "false")
    client: TestClient = request.getfixturevalue("client")
    assert client.post("/api/v1/setup", json=SETUP).status_code == 201

    from falcon import demo

    monkeypatch.setenv("FALCON_DEMO", "true")
    capsys.readouterr()
    assert demo.seed() is False
    printed = capsys.readouterr().out
    assert SETUP["owner"]["email"] in printed, printed
    assert "already set up" in printed and "start fresh" in printed
    assert "Quantum-Safe-2026!" not in printed  # never suggest a password that does not work here
