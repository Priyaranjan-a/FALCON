"""Reporting: CycloneDX CBOM, SARIF, SPDX, CSV, ML-DSA-65 attestations, drift,
the reports API and the offline command line."""
from __future__ import annotations

import base64
import copy
import csv
import io
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from conftest import WRITE, invite_and_activate
from falcon.__main__ import main
from falcon.discovery import engine
from falcon.domains.horizon.model import ThreatModel
from falcon.reporting import attest, cbom, drift, sarif, spdx, tabular
from falcon.reporting.inventory import OfflineInventory
from falcon.risk.facts import SystemFacts

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
ESTATE = FIXTURES / "estates" / "payments-platform"
MODEL = ThreatModel.build("moderate", None, None, 0.05, now=2026.75)
SYSTEM = SystemFacts("s1", "PAY", "Payments Platform", "service", "critical", "external", "restricted", 10.0, 3.0)
SYSTEM_IN = {
    "code": "PAY", "name": "Payments Platform", "kind": "service", "exposure": "external", "criticality": "critical",
    "data_classification": "restricted", "data_shelf_life_years": 10, "migration_years": 3,
}


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    findings: list[dict] = []
    job = engine.Job(scan_id="t", kind="directory", locator=str(ESTATE), workdir=str(tmp_path_factory.mktemp("job")))
    engine.run(job, lambda kind, payload: findings.extend(payload) if kind == "findings" else None)
    inventory = OfflineInventory()
    inventory.ingest(findings)
    return inventory.report(SYSTEM, MODEL, organisation="Example Authority", scope="Payments Platform")


@pytest.fixture(scope="module")
def doc(report):
    return cbom.build(report)


# ------------------------------------------------------------------ CycloneDX

def test_cbom_is_cyclonedx_1_6_with_crypto_assets(doc) -> None:
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.6" and doc["serialNumber"].startswith("urn:uuid:")
    refs = [c["bom-ref"] for c in doc["components"]]
    assert len(refs) == len(set(refs)), "bom-refs must be unique"
    assets = [c for c in doc["components"] if c["type"] == "cryptographic-asset"]
    kinds = {c["cryptoProperties"]["assetType"] for c in assets}
    assert kinds >= {"algorithm", "certificate", "related-crypto-material", "protocol"}
    assert any(c["type"] == "library" and c.get("purl", "").startswith("pkg:") for c in doc["components"])
    assert doc["components"][0]["type"] == "application" and doc["components"][0]["bom-ref"] == "system/PAY"


def test_cbom_algorithm_properties_follow_the_spec(doc) -> None:
    algos = {c["name"]: c["cryptoProperties"] for c in doc["components"]
             if c.get("cryptoProperties", {}).get("assetType") == "algorithm"}
    primitives = {"drbg", "mac", "block-cipher", "stream-cipher", "signature", "hash", "pke", "xof", "kdf", "key-agree", "kem", "ae",
                  "combiner", "other", "unknown"}
    assert all(p["algorithmProperties"]["primitive"] in primitives for p in algos.values())
    gcm = next(p for n, p in algos.items() if n.startswith("AES-256-GCM"))
    assert gcm["algorithmProperties"]["mode"] == "gcm" and gcm["oid"] == "2.16.840.1.101.3.4.1.46"
    assert gcm["algorithmProperties"]["nistQuantumSecurityLevel"] == 5
    rsa = next(p for n, p in algos.items() if n.startswith("RSA"))
    assert rsa["algorithmProperties"]["nistQuantumSecurityLevel"] == 0


def test_cbom_links_certificates_keys_and_protocols(doc) -> None:
    refs = {c["bom-ref"] for c in doc["components"]}
    certs = [c["cryptoProperties"]["certificateProperties"] for c in doc["components"]
             if c.get("cryptoProperties", {}).get("assetType") == "certificate"]
    assert certs and all(c["certificateFormat"] == "X.509" and c["notValidAfter"].endswith("Z") for c in certs)
    assert any(c.get("subjectPublicKeyRef") in refs and c.get("signatureAlgorithmRef") in refs for c in certs)
    for dep in doc["dependencies"]:
        assert dep["ref"] in refs or dep["ref"].startswith("scope/")
        assert set(dep["dependsOn"]) <= refs


def test_cbom_carries_evidence_and_the_assessment(doc) -> None:
    asset = next(c for c in doc["components"] if c["name"] == "DSA")
    props = {p["name"]: p["value"] for p in asset["properties"]}
    assert props["falcon:quantum-status"] == "vulnerable" and props["falcon:risk:band"] in ("critical", "high")
    assert props["falcon:recommendation:primary"].startswith("ML-DSA")
    assert {"falcon:mosca:x", "falcon:mosca:y", "falcon:mosca:z", "falcon:policy:nist-ir-8547"} <= set(props)
    occ = asset["evidence"]["occurrences"][0]
    assert occ["location"] == "deploy/nginx/payments.conf" and occ["line"] == 8


def test_cbom_xml_mirrors_json(doc) -> None:
    root = ET.fromstring(cbom.to_xml(doc).encode("utf-8"))
    ns = {"c": cbom.XML_NS}
    assert root.tag == f"{{{cbom.XML_NS}}}bom" and root.get("version") == "1"
    assert len(root.findall("c:components/c:component", ns)) == len(doc["components"])
    assert root.find("c:components/c:component/c:cryptoProperties/c:assetType", ns) is not None


def test_cbom_digest_ignores_serial_and_time(report, doc) -> None:
    again = cbom.build(report)
    assert again["serialNumber"] != doc["serialNumber"]
    assert cbom.digest(again) == cbom.digest(doc)
    changed = copy.deepcopy(doc)
    changed["components"].pop()
    assert cbom.digest(changed) != cbom.digest(doc)


# ---------------------------------------------------------------- SARIF, SPDX

def test_sarif_annotates_code_by_rule(report) -> None:
    log = sarif.build(report)
    run = log["runs"][0]
    assert log["version"] == "2.1.0" and run["tool"]["driver"]["name"] == "FALCON"
    rule_ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
    results = run["results"]
    assert {r["ruleId"] for r in results} >= {"FALCON001", "FALCON002", "FALCON004"}
    assert all(rule_ids[r["ruleIndex"]] == r["ruleId"] for r in results)
    assert all(r["level"] in ("error", "warning", "note") for r in results)
    hndl = next(r for r in results if r["ruleId"] == "FALCON002")
    assert "X " in hndl["message"]["text"] and float(hndl["properties"]["security-severity"]) > 0
    located = [r for r in results if "locations" in r and "physicalLocation" in r["locations"][0]]
    assert all(not r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].startswith("/") for r in located)
    fingerprints = [r["partialFingerprints"]["falconArtefact/v1"] for r in results]
    assert len(fingerprints) == len(set(fingerprints))
    only_critical = sarif.build(report, minimum="critical")["runs"][0]["results"]
    assert 0 < len(only_critical) < len(results)


def test_spdx_relationships_resolve(report) -> None:
    doc = spdx.build(report)
    assert doc["spdxVersion"] == "SPDX-2.3" and doc["dataLicense"] == "CC0-1.0"
    ids = {p["SPDXID"] for p in doc["packages"]} | {"SPDXRef-DOCUMENT"}
    assert len(ids) == len(doc["packages"]) + 1
    assert all(r["spdxElementId"] in ids and r["relatedSpdxElement"] in ids for r in doc["relationships"])
    libs = [p for p in doc["packages"] if p["primaryPackagePurpose"] == "LIBRARY"]
    assert libs and any(ref["referenceType"] == "purl" for p in libs for ref in p.get("externalRefs", []))


def test_csv_register_and_formula_injection(report) -> None:
    text = tabular.to_csv(report)
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    assert len(rows) == len(report.items)
    assert rows[0]["risk_score"] >= rows[-1]["risk_score"] or int(rows[0]["risk_score"]) >= int(rows[-1]["risk_score"])
    assert {"policy_nist-ir-8547", "policy_cnsa-2.0", "replace_with", "mosca_x_years"} <= set(rows[0])
    assert tabular._cell("=HYPERLINK(1)") == "'=HYPERLINK(1)" and tabular._cell("@SUM") == "'@SUM" and tabular._cell("ok") == "ok"


# --------------------------------------------------------------- attestation

def test_ml_dsa_attestation_round_trip(tmp_path, doc) -> None:
    store = attest.KeyStore(tmp_path / "keys")
    key = store.signing_key()
    digest = cbom.digest(doc)
    envelope = attest.sign(key, attest.statement(doc, name="cbom.json", digest=digest))
    assert len(base64.b64decode(envelope["signatures"][0]["sig"])) == 3309  # FIPS 204 ML-DSA-65 signature size
    verdict = attest.verify(envelope, store.public_keys())
    assert verdict["valid"] and verdict["subject"]["sha256"] == digest and verdict["cbom"]["specVersion"] == "1.6"
    assert attest.verify(json.dumps(envelope), [key.describe()["public_key_pem"]])["valid"]

    # One flipped component: the signature no longer holds.
    body = json.loads(base64.b64decode(envelope["payload"]))
    body["predicate"]["components"][0]["name"] = "tampered"
    forged = {**envelope, "payload": base64.b64encode(attest.canonical(body)).decode()}
    failed = attest.verify(forged, store.public_keys())
    assert not failed["valid"] and next(c for c in failed["checks"] if c["check"] == "signature")["ok"] is False

    # Signed by someone else.
    stranger = attest.KeyStore(tmp_path / "other").signing_key()
    assert not attest.verify(attest.sign(stranger, body), store.public_keys())["valid"]
    assert not attest.verify({"payload": "?"}, store.public_keys())["valid"]


def test_a_statement_that_lies_about_its_digest_fails(tmp_path, doc) -> None:
    key = attest.KeyStore(tmp_path / "keys").signing_key()
    envelope = attest.sign(key, attest.statement(doc, name="cbom.json", digest="0" * 64))
    verdict = attest.verify(envelope, [key.describe()["public_key_pem"]])
    assert not verdict["valid"] and [c["check"] for c in verdict["checks"] if not c["ok"]] == ["digest"]


def test_rotation_keeps_old_attestations_verifiable(tmp_path, doc) -> None:
    store = attest.KeyStore(tmp_path / "keys")
    old = store.signing_key()
    envelope = attest.sign(old, attest.statement(doc, name="cbom.json", digest=cbom.digest(doc)))
    new = store.rotate()
    assert new.id != old.id and store.signing_key().id == new.id
    assert attest.verify(envelope, store.public_keys())["valid"]


# ---------------------------------------------------------------------- drift

def test_drift_reports_retired_introduced_and_changed(doc) -> None:
    head = copy.deepcopy(doc)
    head["components"] = [c for c in head["components"] if c["name"] != "DSA"]
    pqc = copy.deepcopy(next(c for c in doc["components"] if c.get("cryptoProperties", {}).get("assetType") == "algorithm"))
    pqc["bom-ref"], pqc["name"] = "crypto/PAY/new-ml-kem", "ML-KEM-768"
    pqc["properties"] = [p if p["name"] != "falcon:quantum-status" else {**p, "value": "pqc"} for p in pqc["properties"]]
    head["components"].append(pqc)
    result = drift.compare(doc, head)
    assert [r["name"] for r in result["removed"]] == ["DSA"] and [r["name"] for r in result["added"]] == ["ML-KEM-768"]
    assert result["verified"] == {"retired": 1, "introduced": 1, "regressions": 0} and result["verdict"] == "improved"
    assert drift.compare(doc, doc)["verdict"] == "unchanged"


# ------------------------------------------------------------------------ API

@pytest.fixture
def scanned(owner: TestClient) -> str:
    system = owner.post("/api/v1/systems", json=SYSTEM_IN, headers=WRITE).json()["id"]
    created = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE,
                         json={"kind": "directory", "locator": str(ESTATE)}).json()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        scan = owner.get(f"/api/v1/scans/{created['scan']['id']}").json()
        if scan["status"] not in ("queued", "running"):
            break
        time.sleep(0.3)
    assert scan["status"] == "succeeded", scan
    return system


def test_exports_every_format(owner: TestClient, scanned: str) -> None:
    formats = [f["id"] for f in owner.get("/api/v1/reports/formats").json()["formats"]]
    assert formats == ["cyclonedx-json", "cyclonedx-xml", "sarif", "spdx", "csv", "json"]
    for fmt in formats:
        response = owner.get("/api/v1/reports/export", params={"format": fmt, "system": scanned})
        assert response.status_code == 200, (fmt, response.text)
        assert response.headers["content-disposition"].startswith('attachment; filename="falcon-pay-')
    body = owner.get("/api/v1/reports/export", params={"format": "cyclonedx-json"}).json()
    assert body["specVersion"] == "1.6" and body["metadata"]["manufacturer"]["name"]
    assert owner.get("/api/v1/reports/export", params={"format": "pdf"}).status_code == 422
    events = owner.get("/api/v1/audit", params={"category": "reports"}).json()["events"]
    assert len(events) == len(formats) + 1 and events[0]["action"] == "report.exported"


def test_signed_snapshots_verify_and_drift(owner: TestClient, scanned: str) -> None:
    created = owner.post("/api/v1/reports/snapshots", json={"label": "Baseline"}, headers=WRITE)
    assert created.status_code == 201, created.text
    snap = created.json()
    assert snap["label"] == "Baseline" and len(snap["digest"]) == 64 and snap["summary"]["artefacts"] > 50
    detail = owner.get(f"/api/v1/reports/snapshots/{snap['id']}").json()
    assert detail["verification"]["valid"] and detail["verification"]["stored_matches"]
    assert [s["id"] for s in owner.get("/api/v1/reports/snapshots").json()["items"]] == [snap["id"]]

    envelope = owner.get(f"/api/v1/reports/snapshots/{snap['id']}/envelope")
    assert envelope.status_code == 200 and "dsse" in envelope.headers["content-disposition"]
    verdict = owner.post("/api/v1/reports/verify", json={"envelope": envelope.json()}, headers=WRITE).json()
    assert verdict["valid"] and verdict["artefacts"] == snap["summary"]["artefacts"] and verdict["organisation"]
    pem = owner.get("/api/v1/reports/key.pem").text
    assert owner.post("/api/v1/reports/verify", json={"envelope": envelope.json(), "public_key": pem}, headers=WRITE).json()["valid"]

    live = owner.get("/api/v1/reports/drift", params={"base": snap["id"]}).json()
    assert live["verdict"] == "unchanged" and live["head"]["label"] == "Current inventory"
    second = owner.post("/api/v1/reports/snapshots", json={}, headers=WRITE).json()
    between = owner.get("/api/v1/reports/drift", params={"base": snap["id"], "head": second["id"]}).json()
    assert between["verdict"] == "unchanged" and between["unchanged"] > 0

    key = owner.get("/api/v1/reports/key").json()
    assert key["algorithm"] == "ML-DSA-65" and key["key_id"] == snap["key_id"] and "BEGIN PUBLIC KEY" in key["public_key_pem"]
    rotated = owner.post("/api/v1/reports/key/rotate", headers=WRITE).json()
    assert rotated["key_id"] != key["key_id"] and len(rotated["known_keys"]) == 2
    assert owner.get(f"/api/v1/reports/snapshots/{snap['id']}").json()["verification"]["valid"]
    actions = [e["action"] for e in owner.get("/api/v1/audit", params={"category": "reports"}).json()["events"]]
    assert actions.count("report.snapshot_signed") == 2 and "report.key_rotated" in actions


def test_empty_inventory_cannot_be_attested(owner: TestClient) -> None:
    response = owner.post("/api/v1/reports/snapshots", json={}, headers=WRITE)
    assert response.status_code == 409 and response.json()["code"] == "empty_inventory"


def test_report_access(owner: TestClient, scanned: str) -> None:
    viewer = invite_and_activate(owner, "viewer@example.gov", "viewer")
    assert viewer.get("/api/v1/reports/export", params={"format": "csv"}).status_code == 200
    assert viewer.post("/api/v1/reports/snapshots", json={}, headers=WRITE).status_code == 403
    assert viewer.post("/api/v1/reports/key/rotate", headers=WRITE).status_code == 403
    lead = invite_and_activate(owner, "lead@example.gov", "security_lead")
    assert lead.post("/api/v1/reports/snapshots", json={}, headers=WRITE).status_code == 201
    assert lead.post("/api/v1/reports/key/rotate", headers=WRITE).status_code == 403
    anonymous = TestClient(owner.app)
    assert anonymous.get("/api/v1/reports/key").status_code == 401


# ------------------------------------------------------------------------ CLI

def test_cli_scan_gate_sign_and_verify(tmp_path, capsys) -> None:
    sarif_out = tmp_path / "falcon.sarif"
    assert main(["scan", str(ESTATE), "-q", "-f", "sarif", "-o", str(sarif_out), "--fail-on", "never"]) == 0
    assert json.loads(sarif_out.read_text(encoding="utf-8"))["runs"][0]["results"]
    assert main(["scan", str(ESTATE), "-q", "-f", "json", "-o", str(tmp_path / "r.json"), "--fail-on", "critical"]) == 1
    assert "gate failed" in capsys.readouterr().err

    assert main(["keygen", "--out", str(tmp_path / "keys")]) == 0
    assert main(["keygen", "--out", str(tmp_path / "keys")]) == 2  # never silently replaces a key
    cdx = tmp_path / "cbom.cdx.json"
    assert main(["scan", str(ESTATE), "-q", "-f", "cyclonedx", "-o", str(cdx),
                 "--sign-key", str(tmp_path / "keys" / "attestation-mldsa65.pem")]) == 0
    envelope = Path(f"{cdx}.dsse.json")
    public = str(tmp_path / "keys" / "falcon-attestation.pub.pem")
    extracted = tmp_path / "verified.json"
    assert main(["verify", str(envelope), "--key", public, "--extract", str(extracted)]) == 0
    assert json.loads(extracted.read_text(encoding="utf-8"))["components"] == json.loads(cdx.read_text(encoding="utf-8"))["components"]

    tampered = json.loads(envelope.read_text(encoding="utf-8"))
    tampered["payload"] = base64.b64encode(b'{"_type":"x"}').decode()
    envelope.write_text(json.dumps(tampered), encoding="utf-8")
    assert main(["verify", str(envelope), "--key", public]) == 3


def test_cli_table_and_archive(tmp_path, capsys) -> None:
    import shutil

    archive = shutil.make_archive(str(tmp_path / "estate"), "zip", ESTATE)
    assert main(["scan", archive, "--name", "Payments", "--code", "PAY"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("FALCON · Payments") and "critical" in out and "→ ML-DSA" in out
