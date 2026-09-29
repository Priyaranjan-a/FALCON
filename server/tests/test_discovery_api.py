"""Discovery through the API: real scans in the isolated worker process."""
from __future__ import annotations

import io
import json
import shutil
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import WRITE, invite_and_activate

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
SYSTEM = {
    "code": "PAY", "name": "Payments Platform", "kind": "platform", "exposure": "external", "criticality": "critical",
    "data_classification": "restricted", "data_shelf_life_years": 10, "migration_years": 3,
}


def wait_for(client: TestClient, scan_id: str, timeout: float = 90) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        scan = client.get(f"/api/v1/scans/{scan_id}").json()
        if scan["status"] not in ("queued", "running"):
            return scan
        time.sleep(0.4)
    raise AssertionError(f"scan {scan_id} did not finish: {scan}")


@pytest.fixture
def system(owner: TestClient) -> str:
    return owner.post("/api/v1/systems", json=SYSTEM, headers=WRITE).json()["id"]


def add_folder(client: TestClient, system_id: str, folder: Path, **extra) -> dict:
    response = client.post(f"/api/v1/systems/{system_id}/sources", headers=WRITE,
                           json={"kind": "directory", "locator": str(folder), **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_capabilities(owner: TestClient) -> None:
    caps = owner.get("/api/v1/discovery/capabilities").json()
    kinds = {k["kind"]: k for k in caps["source_kinds"]}
    assert kinds["directory"]["available"] is True  # scan roots are configured for the tests
    assert caps["any_folder"] is False and len(caps["scan_roots"]) == 2
    assert kinds["endpoint"]["available"] is False  # probes are opt-in on servers
    assert caps["knowledge"]["algorithms"] == "2026.09"


def test_folder_scan_builds_the_inventory(owner: TestClient, system: str) -> None:
    created = add_folder(owner, system, FIXTURES / "estates" / "payments-platform", name="Payments monorepo")
    assert created["source"]["name"] == "Payments monorepo"
    scan = wait_for(owner, created["scan"]["id"])
    assert scan["status"] == "succeeded", scan["error"]
    assert scan["files_total"] >= 20 and scan["artefacts"] >= 60 and scan["new_artefacts"] == scan["artefacts"]
    assert scan["summary"]["by_kind"]["certificate"] >= 3
    assert sum(leaf["scanned"] for leaf in scan["coverage"].values()) == scan["files_total"]

    listing = owner.get("/api/v1/artefacts", params={"system": system, "kind": "certificate"}).json()
    names = {a["name"] for a in listing["items"]}
    assert {"payments.gov.example", "settlement-legacy.gov.example", "Example Payments Root CA"} <= names

    vulnerable = owner.get("/api/v1/artefacts", params={"system": system, "quantum": "vulnerable", "sort": "risk"}).json()
    assert vulnerable["total"] > 10 and all(a["quantum"] == "vulnerable" for a in vulnerable["items"])

    gateway = next(a for a in listing["items"] if a["name"] == "payments.gov.example")
    detail = owner.get(f"/api/v1/artefacts/{gateway['id']}").json()
    assert detail["evidence"][0]["path"] == "deploy/pki/gateway.pem"
    assert {link["relation"] for link in detail["links"]} == {"certifies-key", "signed-with"}

    systems = owner.get("/api/v1/systems").json()["items"]
    summary = owner.get("/api/v1/inventory/summary", params={"system": system}).json()
    assert systems[0]["inventory"]["artefacts"] == summary["total"] and summary["systems"] == 1
    assert sum(sum(row.values()) for row in summary["matrix"].values()) == summary["total"]
    assert summary["matrix"]["certificate"]["vulnerable"] >= 3
    assert summary["certificates"]["expired"] >= 1  # the legacy settlement certificate
    assert summary["libraries"]["abandoned"] >= 1 and summary["libraries"]["pqc_capable"] >= 1


def test_rescan_is_idempotent_and_tracks_resolution(owner: TestClient, system: str, tmp_path: Path) -> None:
    estate = tmp_path / "estate"
    shutil.copytree(FIXTURES / "estates" / "identity-service", estate)
    created = add_folder(owner, system, estate)
    first = wait_for(owner, created["scan"]["id"])
    assert first["status"] == "succeeded"

    # Retire the Java signer, then scan again.
    shutil.rmtree(estate / "services" / "signer")
    again = owner.post(f"/api/v1/sources/{created['source']['id']}/scans", headers=WRITE)
    assert again.status_code == 202
    second = wait_for(owner, again.json()["id"])
    assert second["new_artefacts"] == 0
    resolved = owner.get("/api/v1/artefacts", params={"system": system, "status": "resolved"}).json()
    assert "ML-DSA-87" in {a["name"] for a in resolved["items"]}
    active = owner.get("/api/v1/artefacts", params={"system": system}).json()
    assert "ML-KEM-1024" in {a["name"] for a in active["items"]}
    # Evidence shows what the latest scan saw, not every historical sighting.
    kem = next(a for a in active["items"] if a["name"] == "ML-KEM-1024")
    evidence = owner.get(f"/api/v1/artefacts/{kem['id']}").json()["evidence"]
    assert evidence and {e["scan_id"] for e in evidence} == {second["id"]}
    # A resolved artefact keeps the evidence of the last scan that found it.
    signer = next(a for a in resolved["items"] if a["name"] == "ML-DSA-87")
    assert {e["scan_id"] for e in owner.get(f"/api/v1/artefacts/{signer['id']}").json()["evidence"]} == {first["id"]}


def test_uploaded_archive_and_image(owner: TestClient, system: str) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path in (FIXTURES / "estates" / "identity-service").rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(FIXTURES / "estates").as_posix())
    upload = owner.post(f"/api/v1/systems/{system}/sources/upload", headers=WRITE, data={"kind": "archive"},
                        files={"file": ("identity.zip", buffer.getvalue(), "application/zip")})
    assert upload.status_code == 201, upload.text
    scan = wait_for(owner, upload.json()["scan"]["id"])
    assert scan["status"] == "succeeded" and scan["artefacts"] > 5

    with (FIXTURES / "images" / "payments-api-3.8.1.tar").open("rb") as fh:
        image = owner.post(f"/api/v1/systems/{system}/sources/upload", headers=WRITE, data={"kind": "image-archive", "name": "payments-api"},
                           files={"file": ("payments-api.tar", fh, "application/x-tar")})
    scan = wait_for(owner, image.json()["scan"]["id"])
    assert scan["status"] == "succeeded"
    libraries = owner.get("/api/v1/artefacts", params={"system": system, "kind": "library", "scan": scan["id"]}).json()
    assert "OpenSSL 1.1.1n" in {a["name"] for a in libraries["items"]}


def test_archive_by_local_path(owner: TestClient, system: str) -> None:
    image = FIXTURES / "images" / "payments-api-3.8.1.tar"
    created = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "image-archive", "locator": str(image)})
    assert created.status_code == 201, created.text
    assert created.json()["source"]["locator"] == str(image.resolve())  # a path source shows its path, not a stored copy
    assert created.json()["source"]["name"] == "payments-api-3.8.1.tar"
    scan = wait_for(owner, created.json()["scan"]["id"])
    assert scan["status"] == "succeeded" and scan["artefacts"] > 0
    assert image.exists()  # the original is only read, never moved or removed
    folder = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "archive", "locator": str(FIXTURES)})
    assert folder.status_code == 422 and folder.json()["errors"][0]["message"] == "Not a file"
    owner.delete(f"/api/v1/sources/{created.json()['source']['id']}", headers=WRITE)
    assert image.exists()


def test_hostile_archive_is_rejected(owner: TestClient, system: str) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../../escape.txt", "x")
        zf.writestr("ok/app.py", "import hashlib\nhashlib.md5(b'')\n")
    upload = owner.post(f"/api/v1/systems/{system}/sources/upload", headers=WRITE, data={"kind": "archive"},
                        files={"file": ("evil.zip", buffer.getvalue(), "application/zip")})
    scan = wait_for(owner, upload.json()["scan"]["id"])
    assert scan["status"] == "succeeded"
    paths = {e["path"] for a in owner.get("/api/v1/artefacts", params={"system": system}).json()["items"]
             for e in owner.get(f"/api/v1/artefacts/{a['id']}").json()["evidence"]}
    assert paths == {"ok/app.py"}  # the traversal entry was never written


def test_source_validation(owner: TestClient, system: str) -> None:
    missing = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "directory", "locator": "Z:/no/such/folder"})
    assert missing.status_code == 422 and missing.json()["errors"][0]["field"] == "locator"
    bad_git = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "git", "locator": "file:///etc"})
    assert bad_git.status_code in (409, 422)
    endpoint = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "endpoint", "locator": "example.org:443"})
    assert endpoint.status_code == 409 and endpoint.json()["code"] == "source_unavailable"


def test_one_active_scan_per_source_and_cancel(owner: TestClient, system: str) -> None:
    created = add_folder(owner, system, FIXTURES / "estates" / "payments-platform", scan_now=False)
    source_id = created["source"]["id"]
    assert created["scan"] is None
    first = owner.post(f"/api/v1/sources/{source_id}/scans", headers=WRITE).json()
    duplicate = owner.post(f"/api/v1/sources/{source_id}/scans", headers=WRITE)
    assert duplicate.status_code == 409
    owner.post(f"/api/v1/scans/{first['id']}/cancel", headers=WRITE)
    final = wait_for(owner, first["id"])
    assert final["status"] in ("cancelled", "succeeded")  # a tiny estate may finish before the cancel lands


def test_live_event_stream(owner: TestClient, system: str) -> None:
    created = add_folder(owner, system, FIXTURES / "estates" / "payments-platform")
    events: list[tuple[str, dict]] = []
    with owner.stream("GET", f"/api/v1/scans/{created['scan']['id']}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line.removeprefix("event: ")
            elif line.startswith("data: ") and name:
                events.append((name, json.loads(line.removeprefix("data: "))))
    names = [n for n, _ in events]
    assert names[0] == "snapshot"
    assert names[-1] in ("finished", "snapshot")  # a scan that finished before we connected sends only its snapshot
    if len(names) > 1:
        assert "progress" in names and "discovered" in names
        # Progress carries absolute values per directory, so replays cannot double-count.
        for _, data in (e for e in events if e[0] == "progress"):
            assert all({"files", "scanned", "findings"} <= set(leaf) and leaf["scanned"] <= leaf["files"] for leaf in data["coverage"].values())
    final = events[0][1] if names == ["snapshot"] else wait_for(owner, created["scan"]["id"])
    assert sum(leaf["scanned"] for leaf in final["coverage"].values()) == final["files_total"]


def test_removing_a_source_removes_its_evidence(owner: TestClient, system: str) -> None:
    created = add_folder(owner, system, FIXTURES / "estates" / "identity-service")
    wait_for(owner, created["scan"]["id"])
    assert owner.get("/api/v1/inventory/summary", params={"system": system}).json()["total"] > 0
    assert owner.delete(f"/api/v1/sources/{created['source']['id']}", headers=WRITE).status_code == 204
    assert owner.get("/api/v1/inventory/summary", params={"system": system}).json()["total"] == 0


def test_roles_and_audit(owner: TestClient, system: str) -> None:
    created = add_folder(owner, system, FIXTURES / "estates" / "identity-service")
    wait_for(owner, created["scan"]["id"])
    viewer = invite_and_activate(owner, "viewer.disc@falcon.test", "viewer")
    assert viewer.get("/api/v1/artefacts").status_code == 200
    assert viewer.post(f"/api/v1/systems/{system}/sources", headers=WRITE,
                       json={"kind": "directory", "locator": str(FIXTURES)}).status_code == 403
    actions = [e["action"] for e in owner.get("/api/v1/audit", params={"limit": 200}).json()["events"]]
    assert {"source.added", "scan.queued", "scan.succeeded"} <= set(actions)
    # A system's activity includes its sources and scans; the discovery category holds just those.
    history = {e["action"] for e in owner.get("/api/v1/audit", params={"target": system}).json()["events"]}
    assert {"system.registered", "source.added", "scan.succeeded"} <= history
    discovery = {e["action"].split(".")[0] for e in owner.get("/api/v1/audit", params={"category": "discovery"}).json()["events"]}
    assert discovery == {"source", "scan"}
    overview = owner.get("/api/v1/overview").json()
    assert overview["discovery"]["inventory"]["total"] > 0
    assert {c["key"]: c["done"] for c in overview["checklist"]}["discovery"] is True
    assert json.dumps(overview)  # serialisable end to end
