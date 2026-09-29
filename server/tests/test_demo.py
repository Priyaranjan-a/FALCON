"""First-run demonstration: a fresh installation started with --demo opens as
a working platform, signed in with the printed admin credentials."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from conftest import WRITE


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

    assert demo.seed() is False
    assert client.get("/api/v1/systems").json()["total"] == 10
