"""Quantum risk intelligence through the API, over a real scan of the payments estate."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import WRITE, invite_and_activate

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SYSTEM = {
    "code": "PAY", "name": "Payments Platform", "kind": "service", "exposure": "external", "criticality": "critical",
    "data_classification": "restricted", "data_shelf_life_years": 10, "migration_years": 3,
}


@pytest.fixture
def scanned(owner: TestClient) -> str:
    system = owner.post("/api/v1/systems", json=SYSTEM, headers=WRITE).json()["id"]
    created = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE,
                         json={"kind": "directory", "locator": str(FIXTURES / "estates" / "payments-platform")}).json()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        scan = owner.get(f"/api/v1/scans/{created['scan']['id']}").json()
        if scan["status"] not in ("queued", "running"):
            break
        time.sleep(0.3)
    assert scan["status"] == "succeeded", scan
    return system


def test_summary_classifies_the_whole_inventory(owner: TestClient, scanned: str) -> None:
    summary = owner.get("/api/v1/risk/summary").json()
    inventory = owner.get("/api/v1/inventory/summary").json()
    assert summary["total"] == inventory["total"]
    assert sum(summary["bands"].values()) == summary["total"]
    assert summary["bands"]["critical"] > 0 and summary["bands"]["none"] > 0
    # Internet-facing payments with a 10-year shelf-life: recorded key exchanges outlive any horizon.
    assert summary["hndl"]["exposed"] > 0 and summary["hndl"]["systems"] == 1
    assert sum(c["count"] for c in summary["matrix"]["cells"]) == summary["total"] - summary["bands"]["none"]
    assert {row["kind"] for row in summary["classification"]["rows"]} >= {"algorithm", "certificate", "library"}
    assert summary["plane"] and all(p["count"] >= 1 for p in summary["plane"])
    payments = summary["systems"][0]
    assert payments["code"] == "PAY" and payments["band"] == "critical" and payments["estimated_y"] > 0
    assert set(summary["compliance"]) == {"nist-ir-8547", "nist-sp-800-131a", "cnsa-2.0", "eu-pqc-roadmap"}


def test_register_filters_and_sorts(owner: TestClient, scanned: str) -> None:
    everything = owner.get("/api/v1/risk/register", params={"limit": 2000}).json()
    scores = [r["score"] for r in everything["items"]]
    assert scores == sorted(scores, reverse=True)
    hndl = owner.get("/api/v1/risk/register", params={"hndl": "true"}).json()
    assert hndl["total"] > 0 and all(r["hndl"]["exposed"] and "confidentiality" in r["roles"] for r in hndl["items"])
    critical = owner.get("/api/v1/risk/register", params=[("band", "critical"), ("kind", "algorithm")]).json()
    assert all(r["band"] == "critical" and r["kind"] == "algorithm" for r in critical["items"])
    disallowed = owner.get("/api/v1/risk/register", params=[("framework", "nist-sp-800-131a"), ("policy_status", "disallowed")]).json()
    names = {r["name"] for r in disallowed["items"]}
    assert "MD5" in names and all(r["policy"]["nist-sp-800-131a"] == "disallowed" for r in disallowed["items"])


def test_artefact_risk_is_explained(owner: TestClient, scanned: str) -> None:
    rows = owner.get("/api/v1/risk/register", params={"q": "DH-2048"}).json()["items"]
    detail = owner.get(f"/api/v1/risk/artefacts/{rows[0]['id']}").json()
    assert detail["roles"] == ["confidentiality"] and detail["hndl"]["exposed"] is True
    assert {"value", "classical", "quantum", "policy", "driver"} <= set(detail["likelihood"])
    assert {"value", "criticality", "exposure", "classification"} <= set(detail["impact"])
    assert detail["mosca"]["x"] == 10 and detail["migration"]["label"]
    assert [p["framework"] for p in detail["policies"]] == ["nist-ir-8547", "nist-sp-800-131a", "cnsa-2.0", "eu-pqc-roadmap"]
    assert all(p["source"].startswith("https://") for p in detail["policies"])
    assert detail["drivers"]
    assert owner.get("/api/v1/risk/artefacts/nope").status_code == 404


def test_timeline_and_policies(owner: TestClient, scanned: str) -> None:
    timeline = owner.get("/api/v1/risk/timeline", params={"until": 2040}).json()
    kinds = {e["kind"] for e in timeline["events"]}
    assert {"horizon", "policy"} <= kinds
    assert all(timeline["model"]["now"] <= e["year"] <= 2041 for e in timeline["events"])
    assert timeline["curve"][0]["p"] < timeline["curve"][-1]["p"]
    vulnerable = [a for a in timeline["artefacts"] if a["t"]["broken"] is not None]
    assert vulnerable and all(a["t"]["broken"] >= timeline["model"]["now"] - 1e-6 for a in vulnerable)

    policies = owner.get("/api/v1/risk/policies").json()
    ir = next(f for f in policies["frameworks"] if f["id"] == "nist-ir-8547")
    assert ir["dates"] == [2031.0, 2036.0]
    assert ir["at"]["2036"].get("disallowed", 0) >= ir["now"].get("acceptable", 0)


def test_changing_the_threat_model_changes_the_risk(owner: TestClient, scanned: str) -> None:
    before = owner.get("/api/v1/risk/summary").json()
    owner.put("/api/v1/organisation/threat-model", json={"crqc_scenario": "aggressive", "risk_tolerance": 0.25}, headers=WRITE)
    after = owner.get("/api/v1/risk/summary").json()
    assert after["model"]["planning_years"] < before["model"]["planning_years"]
    assert after["hndl"]["exposed"] >= before["hndl"]["exposed"]


def test_access(owner: TestClient, client: TestClient, scanned: str) -> None:
    viewer = invite_and_activate(owner, "viewer.risk@falcon.test", "viewer")
    assert viewer.get("/api/v1/risk/summary").status_code == 200
    anonymous = TestClient(owner.app)
    assert anonymous.get("/api/v1/risk/summary").status_code == 401
