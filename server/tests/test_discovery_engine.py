"""The discovery engine against the fixture estates.

These are the regression gate for detection quality: each expectation is an
artefact a competent reviewer would find by reading the fixture.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from falcon.discovery.engine import Job, run

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def scan(kind: str, locator: Path, tmp_path: Path) -> tuple[list[dict], dict, list[tuple[str, object]]]:
    findings: list[dict] = []
    events: list[tuple[str, object]] = []

    def emit(event: str, payload: object) -> None:
        events.append((event, payload))
        if event == "findings":
            findings.extend(payload)  # type: ignore[arg-type]

    stats = run(Job(scan_id="test", kind=kind, locator=str(locator), workdir=str(tmp_path / "work")), emit)
    return findings, stats, events


def names(findings: list[dict], kind: str | None = None) -> set[str]:
    return {f["name"] for f in findings if kind is None or f["kind"] == kind}


def by_name(findings: list[dict], name: str) -> dict:
    return next(f for f in findings if f["name"] == name)


@pytest.fixture(scope="module")
def payments(tmp_path_factory):
    return scan("directory", FIXTURES / "estates" / "payments-platform", tmp_path_factory.mktemp("pay"))


def test_every_artefact_class_is_found(payments):
    findings, _, _ = payments
    assert {f["kind"] for f in findings} == {"algorithm", "key", "certificate", "protocol", "library", "hardware", "cloud_service"}


@pytest.mark.parametrize("expected", [
    "AES-ECB", "RSA-OAEP", "RSA-2048", "RSA with SHA-1", "MD5", "PBKDF2-SHA1", "CSPRNG",  # Java
    "RSA-3072", "ECDSA P-256", "SHA-1", "X25519MLKEM768",  # Go
    "PBKDF2-SHA256", "AES-GCM", "RSA-PSS", "Insecure PRNG", "AES-128-CBC", "HMAC-SHA256",  # Python
    "AES-256-CBC", "RSA with SHA-256",  # TypeScript
    "3DES-CBC", "ML-KEM-768",  # C
    "DH-2048", "Ed25519",  # sshd
])
def test_source_and_config_algorithms(payments, expected):
    assert expected in names(payments[0], "algorithm")


def test_protocols(payments):
    protocols = names(payments[0], "protocol")
    assert {"TLS 1.0", "TLS 1.1", "TLS 1.2", "SSH 2", "IKEv2", "IKEv2 (hybrid PQC)"} <= protocols


def test_go_min_version_is_a_floor(payments):
    ledger = [f for f in payments[0] if f["kind"] == "protocol" and f["evidence"]["path"].endswith("ledger.go")]
    assert {f["name"] for f in ledger} >= {"TLS 1.2", "TLS 1.3 (hybrid PQC)"}


def test_libraries_with_versions_and_pqc_capability(payments):
    findings = payments[0]
    assert by_name(findings, "Bouncy Castle 1.68")["properties"]["pqc"]["capable"] is False
    assert by_name(findings, "Go standard library crypto 1.22")["properties"]["pqc"]["capable"] is False
    assert by_name(findings, "@noble/post-quantum 0.2.1")["properties"]["pqc"]["capable"] is True
    assert by_name(findings, "PyCrypto 2.6.1")["properties"]["status"] == "abandoned"
    assert "Bouncy Castle 1.78" in names(findings, "library")  # bundled inside the fat JAR


def test_keys_certificates_and_exposure(payments):
    findings = payments[0]
    private = by_name(findings, "ECDSA P-256 private key")
    assert private["properties"]["exposure"] == "Unencrypted private key stored at rest"
    legacy = by_name(findings, "settlement-legacy.gov.example")
    assert legacy["properties"]["expired"] is True and legacy["properties"]["self_signed"] is True
    assert legacy["properties"]["key_algorithm"] == "RSA-1024"
    gateway = by_name(findings, "payments.gov.example")
    assert gateway["properties"]["dns_names"] == ["payments.gov.example", "api.payments.gov.example"]
    assert {r["relation"] for r in gateway["related"]} == {"certifies-key", "signed-with"}


def test_secrets_never_leave_the_worker(payments):
    for finding in payments[0]:
        for _, text in finding["evidence"]["snippet"] or []:
            assert "BEGIN PRIVATE KEY" not in text or "REDACTED" in text or len(text) < 60


def test_cloud_and_hardware(payments):
    findings = payments[0]
    pq = by_name(findings, "AWS KMS key · receipts_pq")
    assert pq["related"][0]["name"] == "ML-DSA-65"
    card = by_name(findings, "AWS KMS key · card_data")
    assert card["related"][0]["name"] == "AES-256-GCM"
    hardware = names(findings, "hardware")
    assert {"AWS CloudHSM", "Google Cloud HSM"} <= hardware
    assert any(h.startswith("Thales Luna") for h in hardware)


def test_binary_and_bytecode(payments):
    findings = payments[0]
    binary = [f for f in findings if f["evidence"]["path"].endswith("libsettle.so")]
    assert "OpenSSL 1.1.1k" in {f["name"] for f in binary}
    assert {"AES", "SHA-256"} <= {f["name"] for f in binary if f["kind"] == "algorithm"}
    openssl = by_name(findings, "OpenSSL 1.1.1k")
    assert openssl["properties"]["eol"]["reached"] is True
    bytecode = {f["name"] for f in findings if "BatchSigner.class" in f["evidence"]["path"]}
    assert {"3DES-CBC", "ECDSA with SHA-256", "TLS 1.0"} <= bytecode


def test_progress_events_and_coverage(payments):
    _, stats, events = payments
    stages = [p["stage"] for e, p in events if e == "stage"]
    assert stages[:3] == ["acquire", "enumerate", "analyse"]
    tree = next(p for e, p in events if e == "tree")
    assert sum(leaf["files"] for leaf in tree["leaves"]) == stats["files"]
    last = [p for e, p in events if e == "progress"][-1]
    assert last["files_done"] == stats["files"]


def test_container_image(tmp_path):
    findings, stats, _ = scan("image-archive", FIXTURES / "images" / "payments-api-3.8.1.tar", tmp_path)
    libraries = names(findings, "library")
    assert {"OpenSSL 1.1.1n", "OpenSSH 8.4p1", "GnuTLS 3.7.1"} <= libraries
    assert "TLS 1.0" in names(findings, "protocol")  # MinProtocol = TLSv1 in openssl.cnf
    assert stats["source"]["tags"] == ["registry.pay.gov.example/payments-api:3.8.1"]
    assert not (tmp_path / "work").exists()  # workspace cleaned up


def test_post_quantum_ready_estate(tmp_path):
    findings, _, _ = scan("directory", FIXTURES / "estates" / "identity-service", tmp_path)
    algorithms = names(findings, "algorithm")
    assert {"ML-KEM-1024", "ML-DSA-87", "X25519MLKEM768", "SHA-384"} <= algorithms
    assert "TLS 1.3 (hybrid PQC)" in names(findings, "protocol")
    assert by_name(findings, "Go standard library crypto 1.24")["properties"]["pqc"]["capable"] is True
    assert by_name(findings, "Bouncy Castle 1.80")["properties"]["pqc"]["capable"] is True
