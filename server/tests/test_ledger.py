from __future__ import annotations

import threading

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from conftest import WRITE, db_session
from falcon.kernel import audit
from falcon.kernel.audit import AuditEvent


def test_every_change_is_recorded_and_chained(owner: TestClient) -> None:
    owner.post("/api/v1/systems", json={
        "code": "HSM-01", "name": "Root HSM", "kind": "infrastructure", "exposure": "isolated",
        "criticality": "critical", "data_classification": "secret", "data_shelf_life_years": 25,
        "migration_years": 4,
    }, headers=WRITE)
    events = owner.get("/api/v1/audit").json()["events"]
    actions = [e["action"] for e in events]
    assert actions[:2] == ["system.registered", "organisation.created"]
    newest, previous = events[0], events[1]
    assert newest["prev_hash"] == previous["hash"]

    result = owner.post("/api/v1/audit/verify", headers=WRITE).json()
    assert result["valid"] is True and result["checked"] == 2


def test_tampering_is_detected(owner: TestClient) -> None:
    owner.patch("/api/v1/organisation", json={"name": "Renamed Agency"}, headers=WRITE)
    with db_session() as db:
        db.execute(update(AuditEvent).where(AuditEvent.seq == 1).values(summary="nothing happened here"))
        db.commit()
    result = owner.post("/api/v1/audit/verify", headers=WRITE).json()
    assert result["valid"] is False
    assert result["broken_at"] == 1


def test_truncation_is_detected(owner: TestClient) -> None:
    owner.patch("/api/v1/organisation", json={"name": "Renamed Agency"}, headers=WRITE)
    with db_session() as db:
        last = db.scalar(select(AuditEvent.seq).order_by(AuditEvent.seq.desc()))
        db.execute(delete(AuditEvent).where(AuditEvent.seq == last))
        db.commit()
    with db_session() as db:
        result = audit.verify_chain(db)
    assert result["valid"] is False
    assert "head" in result["reason"]


def test_concurrent_writers_never_fork_the_chain(owner: TestClient) -> None:
    errors: list[BaseException] = []

    def writer(n: int) -> None:
        try:
            for i in range(10):
                with db_session() as db:
                    audit.append(db, action="test.concurrent", summary=f"writer {n} event {i}")
                    db.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    with db_session() as db:
        result = audit.verify_chain(db)
    assert result["valid"] is True
    assert result["checked"] == 41  # setup + 40 concurrent events


def test_audit_filters_and_paging(owner: TestClient) -> None:
    for i in range(3):
        owner.patch("/api/v1/organisation", json={"name": f"Agency {i}"}, headers=WRITE)
    page = owner.get("/api/v1/audit", params={"limit": 2}).json()
    assert len(page["events"]) == 2 and page["next_before"] is not None
    rest = owner.get("/api/v1/audit", params={"limit": 2, "before": page["next_before"]}).json()
    assert rest["events"][0]["seq"] < page["events"][-1]["seq"]
    only_org = owner.get("/api/v1/audit", params={"category": "organisation"}).json()["events"]
    assert all(e["action"].startswith(("organisation.", "threat_model.")) for e in only_org)


def test_problem_documents(owner: TestClient) -> None:
    response = owner.get("/api/v1/systems/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith("/not-found") and body["status"] == 404
    assert owner.get("/api/v1/nowhere").status_code == 404


def test_security_headers(client: TestClient) -> None:
    response = client.get("/api/v1/platform/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"
    assert "x-request-id" in response.headers


def test_audit_target_filter(owner: TestClient) -> None:
    system_id = owner.post("/api/v1/systems", json={
        "code": "VPN", "name": "Remote access VPN", "kind": "infrastructure", "exposure": "external",
        "criticality": "high", "data_classification": "confidential", "data_shelf_life_years": 5,
        "migration_years": 3,
    }, headers=WRITE).json()["id"]
    owner.patch(f"/api/v1/systems/{system_id}", json={"team": "Network"}, headers=WRITE)
    events = owner.get("/api/v1/audit", params={"target": system_id}).json()["events"]
    assert [e["action"] for e in events] == ["system.updated", "system.registered"]
