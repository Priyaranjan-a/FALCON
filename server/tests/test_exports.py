"""The export library: files written to FALCON's library on a server, or to the
user's chosen folder in the desktop app, with history, re-download and reveal."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import SETUP, WRITE

ESTATE = Path(__file__).resolve().parents[2] / "fixtures" / "estates" / "payments-platform"
SYSTEM = {"code": "PAY", "name": "Payments Platform", "kind": "service", "exposure": "external", "criticality": "critical",
          "data_classification": "restricted", "data_shelf_life_years": 10, "migration_years": 3}


def _scan(client: TestClient) -> str:
    system = client.post("/api/v1/systems", json=SYSTEM, headers=WRITE).json()["id"]
    created = client.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "directory", "locator": str(ESTATE)}).json()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        scan = client.get(f"/api/v1/scans/{created['scan']['id']}").json()
        if scan["status"] not in ("queued", "running"):
            break
        time.sleep(0.3)
    assert scan["status"] == "succeeded", scan
    return system


@pytest.fixture
def desktop(monkeypatch, request) -> TestClient:
    """A desktop-mode engine, signed in as its owner."""
    monkeypatch.setenv("FALCON_DESKTOP", "1")
    client = request.getfixturevalue("client")
    assert client.post("/api/v1/setup", json=SETUP).status_code == 201
    return client


def test_server_exports_go_to_the_library_and_download_again(owner: TestClient, tmp_path: Path) -> None:
    system = _scan(owner)
    created = owner.post("/api/v1/reports/exports", json={"format": "cyclonedx-json", "system_id": system}, headers=WRITE)
    assert created.status_code == 201, created.text
    e = created.json()
    assert e["label"] == "CycloneDX 1.6 CBOM" and e["filename"].endswith(".cdx.json") and e["available"]
    assert e["path"] is None  # a server never tells browsers where it keeps files
    stored = tmp_path / "exports" / e["filename"]
    assert stored.exists() and hashlib.sha256(stored.read_bytes()).hexdigest() == e["sha256"]

    file = owner.get(f"/api/v1/reports/exports/{e['id']}/file")
    assert file.status_code == 200 and file.content == stored.read_bytes()
    assert f'filename="{e["filename"]}"' in file.headers["content-disposition"]
    assert json.loads(file.content)["specVersion"] == "1.6"

    listing = owner.get("/api/v1/reports/exports").json()
    assert [x["id"] for x in listing["items"]] == [e["id"]]
    assert listing["location"]["desktop"] is False

    # Same minute, same name: the second file does not overwrite the first.
    again = owner.post("/api/v1/reports/exports", json={"format": "cyclonedx-json", "system_id": system}, headers=WRITE).json()
    assert again["filename"] != e["filename"] and " (2)" in again["filename"]

    # A file changed behind FALCON's back is not served as if it were the original.
    stored.write_bytes(b"tampered")
    assert owner.get(f"/api/v1/reports/exports/{e['id']}/file").status_code == 409

    assert owner.delete(f"/api/v1/reports/exports/{e['id']}", headers=WRITE).status_code == 204
    assert not stored.exists()
    assert [x["id"] for x in owner.get("/api/v1/reports/exports").json()["items"]] == [again["id"]]
    actions = [ev["action"] for ev in owner.get("/api/v1/audit", params={"category": "reports"}).json()["events"]]
    assert actions.count("report.exported") == 2


def test_snapshot_and_key_exports(owner: TestClient) -> None:
    _scan(owner)
    snap = owner.post("/api/v1/reports/snapshots", json={"label": "Baseline"}, headers=WRITE).json()
    envelope = owner.post("/api/v1/reports/exports", json={"kind": "snapshot", "snapshot_id": snap["id"], "part": "envelope"}, headers=WRITE).json()
    assert envelope["format"] == "snapshot-envelope" and envelope["filename"].endswith(".dsse.json")
    body = owner.get(f"/api/v1/reports/exports/{envelope['id']}/file").json()
    assert owner.post("/api/v1/reports/verify", json={"envelope": body}, headers=WRITE).json()["valid"]
    key = owner.post("/api/v1/reports/exports", json={"kind": "key"}, headers=WRITE).json()
    assert key["filename"] == "falcon-attestation.pub.pem"
    assert b"BEGIN PUBLIC KEY" in owner.get(f"/api/v1/reports/exports/{key['id']}/file").content
    assert owner.post("/api/v1/reports/exports", json={"kind": "snapshot", "snapshot_id": snap["id"]}, headers=WRITE).status_code == 422


def test_folders_and_reveal_are_desktop_only(owner: TestClient, tmp_path: Path) -> None:
    assert owner.put("/api/v1/reports/exports/location", json={"path": str(tmp_path / "x")}, headers=WRITE).json()["code"] == "desktop_only"
    assert owner.post("/api/v1/reports/exports/location/open", headers=WRITE).status_code == 409
    _scan(owner)
    e = owner.post("/api/v1/reports/exports", json={"format": "csv"}, headers=WRITE).json()
    assert owner.post(f"/api/v1/reports/exports/{e['id']}/reveal", headers=WRITE).status_code == 409


def test_desktop_writes_to_the_chosen_folder_and_reveals(desktop: TestClient, tmp_path: Path, monkeypatch) -> None:
    from falcon.domains.reports import library

    launched: list[list[str]] = []
    monkeypatch.setattr(library, "_launch", lambda args: launched.append(args))
    location = desktop.get("/api/v1/reports/exports/location").json()
    assert location["desktop"] and location["path"].endswith("FALCON Exports") and not location["custom"]

    assert desktop.put("/api/v1/reports/exports/location", json={"path": "relative/folder"}, headers=WRITE).status_code == 422
    chosen = tmp_path / "My exports" / "FALCON"
    moved = desktop.put("/api/v1/reports/exports/location", json={"path": str(chosen)}, headers=WRITE).json()
    assert moved["path"] == str(chosen) and moved["custom"] and chosen.is_dir()

    _scan(desktop)
    e = desktop.post("/api/v1/reports/exports", json={"format": "sarif"}, headers=WRITE).json()
    assert e["path"] == str(chosen / e["filename"]) and Path(e["path"]).exists()
    assert json.loads(Path(e["path"]).read_text(encoding="utf-8"))["version"] == "2.1.0"

    assert desktop.post(f"/api/v1/reports/exports/{e['id']}/reveal", headers=WRITE).status_code == 204
    # Explorer and Finder select the file; on Linux the file manager selects it, or its folder opens.
    revealed = " ".join(launched[-1])
    assert e["filename"].replace(" ", "%20") in revealed or e["filename"] in revealed or revealed.endswith(str(chosen))
    assert desktop.post("/api/v1/reports/exports/location/open", headers=WRITE).status_code == 200
    assert str(chosen) in launched[-1][-1]

    # Removing from the list never deletes the user's own file.
    assert desktop.delete(f"/api/v1/reports/exports/{e['id']}", headers=WRITE).status_code == 204
    assert Path(e["path"]).exists()
    Path(e["path"]).unlink()

    reset = desktop.delete("/api/v1/reports/exports/location", headers=WRITE).json()
    assert not reset["custom"] and reset["path"].endswith("FALCON Exports")


def test_revealing_a_moved_file_explains(desktop: TestClient, tmp_path: Path, monkeypatch) -> None:
    from falcon.domains.reports import library

    monkeypatch.setattr(library, "_launch", lambda args: None)
    desktop.put("/api/v1/reports/exports/location", json={"path": str(tmp_path / "out")}, headers=WRITE)
    _scan(desktop)
    e = desktop.post("/api/v1/reports/exports", json={"format": "json"}, headers=WRITE).json()
    Path(e["path"]).unlink()
    missing = desktop.post(f"/api/v1/reports/exports/{e['id']}/reveal", headers=WRITE)
    assert missing.status_code == 404 and missing.json()["code"] == "export_missing"
    assert desktop.get("/api/v1/reports/exports").json()["items"][0]["available"] is False
