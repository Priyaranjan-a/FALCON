from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import WRITE, invite_and_activate

PAYMENTS = {
    "code": "pay-gw",
    "name": "Payments  Gateway",
    "kind": "service",
    "exposure": "external",
    "criticality": "critical",
    "data_classification": "restricted",
    "data_shelf_life_years": 10,
    "migration_years": 2,
    "owner": "Treasury Platform",
    "tags": ["Payments", "pci"],
}

INTRANET = {
    "code": "INTRA",
    "name": "Staff intranet",
    "kind": "application",
    "exposure": "internal",
    "criticality": "low",
    "data_classification": "public",
    "data_shelf_life_years": 0,
    "migration_years": 0.5,
}


def test_register_normalises_and_scores(owner: TestClient) -> None:
    response = owner.post("/api/v1/systems", json=PAYMENTS, headers=WRITE)
    assert response.status_code == 201, response.text
    system = response.json()
    assert system["code"] == "PAY-GW"
    assert system["name"] == "Payments Gateway"
    assert system["tags"] == ["payments", "pci"]
    mosca = system["mosca"]
    assert mosca["x"] == 10 and mosca["y"] == 2
    assert mosca["exposure_years"] > 0
    assert mosca["status"] == "exposed"
    assert 0 < mosca["probability"] < 1
    assert mosca["overdue_years"] > 0


def test_validation_messages(owner: TestClient) -> None:
    bad = {**PAYMENTS, "code": "no spaces allowed here!", "data_shelf_life_years": -1}
    response = owner.post("/api/v1/systems", json=bad, headers=WRITE)
    assert response.status_code == 422
    fields = {e["field"] for e in response.json()["errors"]}
    assert {"code", "data_shelf_life_years"} <= fields


def test_duplicate_code_conflicts(owner: TestClient) -> None:
    owner.post("/api/v1/systems", json=PAYMENTS, headers=WRITE)
    again = owner.post("/api/v1/systems", json={**PAYMENTS, "name": "Other"}, headers=WRITE)
    assert again.status_code == 409
    assert again.json()["code"] == "system_code_taken"


def test_update_and_delete(owner: TestClient) -> None:
    system_id = owner.post("/api/v1/systems", json=PAYMENTS, headers=WRITE).json()["id"]
    updated = owner.patch(f"/api/v1/systems/{system_id}", json={"data_shelf_life_years": 1, "migration_years": 0.5, "owner": None}, headers=WRITE)
    assert updated.status_code == 200
    body = updated.json()
    assert body["owner"] is None
    assert body["mosca"]["status"] in ("clear", "watch")
    assert owner.delete(f"/api/v1/systems/{system_id}", headers=WRITE).status_code == 204
    assert owner.get(f"/api/v1/systems/{system_id}").status_code == 404


def test_filters_sorting_and_summary(owner: TestClient) -> None:
    owner.post("/api/v1/systems", json=PAYMENTS, headers=WRITE)
    owner.post("/api/v1/systems", json=INTRANET, headers=WRITE)

    listing = owner.get("/api/v1/systems").json()
    assert [s["code"] for s in listing["items"]] == ["PAY-GW", "INTRA"]  # most exposed first
    assert owner.get("/api/v1/systems", params={"criticality": "low"}).json()["total"] == 1
    assert owner.get("/api/v1/systems", params={"q": "pci"}).json()["items"][0]["code"] == "PAY-GW"
    assert owner.get("/api/v1/systems", params={"status": "exposed"}).json()["total"] == 1

    summary = owner.get("/api/v1/systems/summary").json()
    assert summary["active"] == 2
    assert summary["mosca"]["exposed"] == 1
    assert {c["key"]: c["count"] for c in summary["by_criticality"]}["critical"] == 1
    assert summary["plane"][0]["code"] == "PAY-GW"


def test_threat_model_changes_flow_into_mosca(owner: TestClient) -> None:
    system_id = owner.post("/api/v1/systems", json={**PAYMENTS, "data_shelf_life_years": 5}, headers=WRITE).json()["id"]
    before = owner.get(f"/api/v1/systems/{system_id}").json()["mosca"]["z"]
    response = owner.put("/api/v1/organisation/threat-model", json={"crqc_scenario": "conservative", "risk_tolerance": 0.25}, headers=WRITE)
    assert response.status_code == 200
    after = owner.get(f"/api/v1/systems/{system_id}").json()["mosca"]["z"]
    assert after > before


def test_analyst_cannot_delete(owner: TestClient) -> None:
    system_id = owner.post("/api/v1/systems", json=PAYMENTS, headers=WRITE).json()["id"]
    analyst = invite_and_activate(owner, "an@falcon.test", "analyst")
    assert analyst.patch(f"/api/v1/systems/{system_id}", json={"team": "Core"}, headers=WRITE).status_code == 200
    assert analyst.delete(f"/api/v1/systems/{system_id}", headers=WRITE).status_code == 403


def test_overview(owner: TestClient) -> None:
    owner.post("/api/v1/systems", json=PAYMENTS, headers=WRITE)
    overview = owner.get("/api/v1/overview").json()
    assert overview["organisation"]["name"] == "National Test Agency"
    assert overview["systems"]["active"] == 1
    checklist = {item["key"]: item["done"] for item in overview["checklist"]}
    assert checklist == {"threat_model": True, "systems": True, "owners": True, "team": False, "discovery": False}
    assert all(m["date"] >= "2026" for m in overview["milestones"])
