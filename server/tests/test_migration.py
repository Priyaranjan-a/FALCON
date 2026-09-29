"""PQC migration planning: recommendations, the roadmap, the blast-radius
graph, the benchmark lab and before/after verification."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import WRITE
from falcon.domains.horizon.model import ThreatModel
from falcon.migration import bench
from falcon.migration.recommend import recommend
from falcon.risk.facts import ArtefactFacts, SystemFacts
from falcon.risk.model import assess

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
MODEL = ThreatModel.build("moderate", None, None, 0.05, now=2026.75)
SECRET = SystemFacts("s1", "PAY", "Payments", "service", "critical", "external", "secret", 25.0, 3.0)
PLAIN = SystemFacts("s2", "WEB", "Website", "application", "moderate", "external", "internal", 2.0, 1.0)


def algo(name, family, quantum, primitive, *, classical="strong", bits=128, functions=(), detectors=("rules:java",), **identity) -> ArtefactFacts:
    return ArtefactFacts(name, "s1", "algorithm", name, family, quantum, classical, primitive, {"algorithm": family, **identity},
                         {"assessment": {"quantum": quantum, "classical": classical, "primitive": primitive, "classical_bits": bits}},
                         functions=frozenset(functions), detectors=frozenset(detectors))


def rec(a: ArtefactFacts, system=PLAIN):
    return recommend(a, assess(a, system, MODEL), system)


# ---------------------------------------------------------- recommendations

def test_tls_key_exchange_gets_a_hybrid_sized_to_the_system() -> None:
    kex = algo("ECDH", "ECDH", "vulnerable", "key-agreement", functions={"tls-cipher-suite"}, detectors=("protocol-config",))
    plain, secret = rec(kex), rec(kex, SECRET)
    assert plain["primary"]["name"] == "X25519MLKEM768" and secret["primary"]["name"] == "SecP384r1MLKEM1024"
    assert plain["overhead"]["delta"] > 1000  # the hybrid key shares cost about a kilobyte each way


def test_key_agreement_in_code_gets_ml_kem_with_a_hybrid_option() -> None:
    r = rec(algo("X25519", "X25519", "vulnerable", "key-agreement", functions={"key-agree"}, detectors=("rules:go",)))
    assert r["primary"]["name"] == "ML-KEM-768" and r["hybrid"]["name"] == "X-Wing"
    assert any("Go 1.24" in s for s in r["steps"])


def test_ssh_and_ipsec_have_their_own_answers() -> None:
    ssh = algo("DH-2048", "DH", "vulnerable", "key-agreement", bits=112, functions={"key-agree"}, detectors=("protocol-config",))
    ssh = ArtefactFacts(**{**ssh.__dict__, "properties": {**ssh.properties, "setting": "KexAlgorithms"}})
    assert rec(ssh)["primary"]["name"] == "mlkem768x25519-sha256"
    ike = ArtefactFacts("ike", "s1", "protocol", "IKEv2", "IPsec", "vulnerable", "acceptable", "protocol", {"protocol": "IPsec", "version": "2"}, {})
    assert "RFC 9370" in rec(ike)["primary"]["name"]


def test_signatures_certificates_and_roots() -> None:
    sig = rec(algo("ECDSA", "ECDSA", "vulnerable", "signature", functions={"sign"}))
    assert sig["primary"]["name"] == "ML-DSA-65" and sig["hybrid"]["name"].startswith("Composite")
    assert rec(algo("ECDSA", "ECDSA", "vulnerable", "signature", functions={"sign"}), SECRET)["primary"]["name"] == "ML-DSA-87"
    root = ArtefactFacts("root", "s1", "certificate", "Root CA", "RSA", "vulnerable", "strong", "signature", {"sha256": "x"},
                         {"is_ca": True, "key_algorithm": "RSA-4096", "days_remaining": 5000})
    r = rec(root)
    assert r["action"] == "reissue" and "hierarchy" in r["title"] and r["alternatives"][0]["name"].startswith("SLH-DSA")


def test_symmetric_and_hash_fixes() -> None:
    assert rec(algo("3DES", "3DES", "weakened", "block-cipher", classical="weak", bits=112))["primary"]["name"] == "AES-256-GCM"
    assert rec(algo("MD5", "MD5", "weakened", "hash", classical="broken"))["primary"]["name"] == "SHA-384"
    assert rec(algo("AES-256-GCM", "AES", "resistant", "ae", bits=256, parameter="256"))["action"] == "keep"
    assert rec(algo("SHA-256", "SHA-256", "resistant", "hash"))["action"] == "keep"


def test_pqc_parameters_are_raised_for_cnsa_systems() -> None:
    kem = algo("ML-KEM-768", "ML-KEM", "pqc", "kem", parameter="768")
    assert rec(kem)["action"] == "keep"
    assert rec(kem, SECRET)["primary"]["name"] == "ML-KEM-1024"


def test_libraries() -> None:
    old = ArtefactFacts("lib", "s1", "library", "OpenSSL 1.1.1n", "openssl", None, None, "library", {"library": "openssl"},
                        {"library": "OpenSSL", "pqc": {"status": "native", "since": "3.5.0", "capable": False}, "eol": {"reached": True}})
    r = rec(old)
    assert r["action"] == "upgrade" and "3.5.0" in r["title"] and "end of life" in r["summary"]
    none = ArtefactFacts("lib2", "s1", "library", "jsrsasign 10", "jsrsasign", None, None, "library", {"library": "jsrsasign"},
                         {"library": "jsrsasign", "ecosystem": "npm", "pqc": {"status": "none", "capable": False}})
    assert "@noble/post-quantum" in rec(none)["title"]


def test_latency_comes_from_the_benchmark_lab() -> None:
    kex = algo("ECDH", "ECDH", "vulnerable", "key-agreement", functions={"tls"}, detectors=("protocol-config",))
    fake = {"results": [{"algorithm": "X25519MLKEM768", "operations": {"encapsulate": 190}}, {"algorithm": "ECDH P-256", "operations": {"encapsulate": 160}}]}
    r = recommend(kex, assess(kex, PLAIN, MODEL), PLAIN, fake)
    assert r["latency"]["after"]["operations"]["encapsulate"] == 190 and r["latency"]["before"]["algorithm"] == "ECDH P-256"


def test_benchmark_lab_measures_real_primitives(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FALCON_DATA_DIR", str(tmp_path))
    from falcon import settings
    settings.get_settings.cache_clear()
    monkeypatch.setattr(bench, "BUDGET", 0.002)
    monkeypatch.setattr(bench, "BATCHES", 1)
    report = bench.run()
    results = {r["algorithm"]: r for r in report["results"]}
    assert {"ML-KEM-768", "ML-KEM-1024", "X25519MLKEM768", "ML-DSA-65", "ML-DSA-87", "RSA-2048", "ECDSA P-256"} <= set(results)
    assert results["ML-KEM-768"]["sizes"] == {"public_key": 1184, "ciphertext": 1088}  # FIPS 203
    assert results["ML-DSA-65"]["sizes"] == {"public_key": 1952, "signature": 3309}  # FIPS 204
    assert all(v > 0 for r in report["results"] for v in r["operations"].values())
    assert bench.latest()["measured_at"] == report["measured_at"]
    settings.get_settings.cache_clear()


# ---------------------------------------------------------------------- API

def _wait(client: TestClient, scan_id: str) -> dict:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        scan = client.get(f"/api/v1/scans/{scan_id}").json()
        if scan["status"] not in ("queued", "running"):
            return scan
        time.sleep(0.3)
    raise AssertionError("scan did not finish")


@pytest.fixture
def estate(owner: TestClient, tmp_path: Path) -> tuple[str, str, Path]:
    system = owner.post("/api/v1/systems", headers=WRITE, json={
        "code": "PAY", "name": "Payments", "kind": "service", "exposure": "external", "criticality": "critical",
        "data_classification": "restricted", "data_shelf_life_years": 10, "migration_years": 3}).json()["id"]
    folder = tmp_path / "estate"
    shutil.copytree(FIXTURES / "estates" / "payments-platform", folder)
    created = owner.post(f"/api/v1/systems/{system}/sources", headers=WRITE, json={"kind": "directory", "locator": str(folder)}).json()
    assert _wait(owner, created["scan"]["id"])["status"] == "succeeded"
    return system, created["source"]["id"], folder


def test_plan_graph_and_recommendation(owner: TestClient, estate) -> None:
    system, _, _ = estate
    plan = owner.get("/api/v1/migration/plan").json()
    waves = {w["key"]: w for w in plan["waves"]}
    assert list(waves) == ["fix-now", "stop-harvest", "long-lead", "before-2030", "complete"]
    assert waves["fix-now"]["artefacts"] > 0 and waves["stop-harvest"]["artefacts"] > 0
    assert waves["before-2030"]["start"] >= waves["stop-harvest"]["finish"] - 1e-6
    assert plan["totals"]["artefacts"] == sum(w["artefacts"] for w in plan["waves"])
    assert plan["lanes"][0]["system"]["code"] == "PAY"
    assert any(t["name"].startswith(("ML-DSA", "SecP384r1MLKEM1024", "X25519MLKEM768")) for t in plan["totals"]["targets"])

    graph = owner.get("/api/v1/migration/graph").json()
    assert graph["nodes"] and all(set(n["systems"]) <= {system} for n in graph["nodes"])
    assert any(n["kind"] == "algorithm" and n["label"] == "RSA" for n in graph["nodes"])

    rows = owner.get("/api/v1/risk/register", params={"q": "TLS 1.0"}).json()["items"]
    r = owner.get(f"/api/v1/migration/recommendations/{rows[0]['id']}").json()
    assert r["action"] == "upgrade" and "TLS 1.3" in r["title"] and r["steps"]


def test_migration_is_verified_by_rescanning(owner: TestClient, estate) -> None:
    _, source, folder = estate
    first = owner.get("/api/v1/scans").json()[0]["id"]
    # The team migrates: nginx moves to TLS 1.3 with the hybrid group, and the legacy settlement PKI goes.
    (folder / "deploy" / "nginx" / "payments.conf").write_text(
        "server {\n    listen 443 ssl;\n    ssl_protocols TLSv1.3;\n    ssl_ecdh_curve X25519MLKEM768:X25519;\n}\n", encoding="utf-8")
    (folder / "deploy" / "pki" / "legacy-settlement.crt").unlink()
    again = owner.post(f"/api/v1/sources/{source}/scans", headers=WRITE).json()["id"]
    assert _wait(owner, again)["status"] == "succeeded"
    diff = owner.get(f"/api/v1/scans/{again}/diff").json()
    assert diff["base"]["id"] == first
    removed = {r["name"] for r in diff["removed"]}
    added = {r["name"] for r in diff["added"]}
    # TLS 1.0 is still configured elsewhere (the load balancer policy, the Java client), so it rightly stays;
    # nginx's legacy cipher suites and the retired certificate are gone.
    assert "settlement-legacy.gov.example" in removed and "Camellia-128-CBC" in removed
    assert "TLS 1.0" not in removed
    # The hybrid group already existed in Go code; what is new is where it is used.
    spread = {r["name"]: r["new_locations"] for r in diff["spread"]}
    assert "deploy/nginx/payments.conf" in spread.get("X25519MLKEM768", [])
    assert diff["verified"]["retired"] > 0 and diff["verified"]["introduced"] > 0 and diff["verdict"] in ("improved", "mixed")


def test_benchmarks_endpoint_requires_scan_rights(owner: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(bench, "BUDGET", 0.002)
    monkeypatch.setattr(bench, "BATCHES", 1)
    assert owner.get("/api/v1/migration/benchmarks").json() == {"report": None}
    report = owner.post("/api/v1/migration/benchmarks", headers=WRITE).json()["report"]
    assert report["results"] and owner.get("/api/v1/migration/benchmarks").json()["report"]["measured_at"] == report["measured_at"]
