"""The quantum risk model: roles, Mosca per artefact, HNDL, scores and policy dates."""
from __future__ import annotations

import pytest

from falcon.domains.horizon.model import ThreatModel
from falcon.risk.facts import ArtefactFacts, SystemFacts, roles
from falcon.risk.model import assess, estimated_system_migration, migration_effort, policy_pressure
from falcon.risk.policies import evaluate

NOW = 2026.75
MODERATE = ThreatModel.build("moderate", None, None, 0.05, now=NOW)

PAYMENTS = SystemFacts("s1", "PAY", "Payments", "service", "critical", "external", "restricted", 10.0, 2.5)
INTRANET = SystemFacts("s2", "INTRA", "Intranet", "application", "low", "isolated", "internal", 1.0, 0.5)


def algorithm(name: str, *, family: str, quantum: str, classical: str = "strong", primitive: str, bits: int | None = 128,
              parameter: str | None = None, hash: str | None = None, functions=(), detectors=("rules:java",)) -> ArtefactFacts:
    identity = {"algorithm": family, **({"parameter": parameter} if parameter else {}), **({"hash": hash} if hash else {})}
    props = {"assessment": {"quantum": quantum, "classical": classical, "primitive": primitive, "classical_bits": bits}}
    return ArtefactFacts(name, "s1", "algorithm", name, family, quantum, classical, primitive, identity, props,
                         functions=frozenset(functions), detectors=frozenset(detectors))


def policy(results, framework):
    return next(r for r in results if r.framework == framework)


# ------------------------------------------------------------------- roles

def test_roles_follow_the_primitive_and_how_it_is_used() -> None:
    dh = algorithm("DH-2048", family="DH", quantum="vulnerable", primitive="key-agreement", bits=112)
    dsa = algorithm("DSA", family="DSA", quantum="vulnerable", primitive="signature", functions={"secure-channel"})
    rsa_kex = algorithm("RSA", family="RSA", quantum="vulnerable", primitive="signature", functions={"tls-cipher-suite"})
    rsa_sign = algorithm("RSA", family="RSA", quantum="vulnerable", primitive="signature", functions={"sign"})
    aes = algorithm("AES-256-GCM", family="AES", quantum="resistant", primitive="ae", bits=256)
    sha = algorithm("SHA-256", family="SHA-256", quantum="resistant", primitive="hash")
    assert roles(dh) == {"confidentiality"}
    assert roles(dsa) == {"authenticity"}  # a host key in an SSH config still only authenticates
    assert roles(rsa_kex) == {"confidentiality", "authenticity"}  # RSA key transport in a TLS suite
    assert roles(rsa_sign) == {"authenticity"}
    assert roles(aes) == {"confidentiality"} and roles(sha) == {"integrity"}


def test_migration_effort_depends_on_where_it_was_found() -> None:
    in_code = algorithm("RSA", family="RSA", quantum="vulnerable", primitive="signature")
    in_config = algorithm("RSA", family="RSA", quantum="vulnerable", primitive="signature", detectors=("protocol-config",))
    in_binary = algorithm("RSA", family="RSA", quantum="vulnerable", primitive="signature", detectors=("binaries",))
    assert migration_effort(in_code) == ("algorithm.code", 1.0)
    assert migration_effort(in_config) == ("algorithm.config", 0.25)
    assert migration_effort(in_binary) == ("algorithm.binary", 1.5)
    ca = ArtefactFacts("ca", "s1", "certificate", "Root CA", "RSA", "vulnerable", "strong", "signature", {},
                       {"is_ca": True, "key_algorithm": "RSA-4096", "days_remaining": 3650})
    assert migration_effort(ca) == ("certificate.ca", 3.0)


# -------------------------------------------------------- Mosca and HNDL

def test_key_exchange_on_an_exposed_system_is_harvestable_now() -> None:
    kex = algorithm("ECDH P-256", family="ECDH", quantum="vulnerable", primitive="key-agreement", functions={"key-agree"})
    risk = assess(kex, PAYMENTS, MODERATE)
    assert risk.mosca["x"] == 10.0 and risk.mosca["y"] == 1.0
    assert risk.mosca["exposure_years"] > 0 and risk.mosca["status"] == "exposed"
    assert risk.hndl == {"applies": True, "reach": "internet", "exposed": True}
    assert risk.band in ("critical", "high")
    assert risk.timeline["exposed"] == pytest.approx(NOW)  # X alone outlives the horizon: exposed today
    assert any("Harvest" in d or "CRQC" in d for d in risk.drivers)


def test_signatures_have_no_retroactive_exposure() -> None:
    sig = algorithm("ECDSA P-256", family="ECDSA", quantum="vulnerable", primitive="signature", functions={"sign"})
    risk = assess(sig, PAYMENTS, MODERATE)
    assert risk.roles == ["authenticity"] and risk.mosca["x"] == 0.0
    assert risk.hndl["applies"] is False
    # Not HNDL, but the migration must be finished before the horizon.
    assert risk.timeline["exposed"] == pytest.approx(MODERATE.planning_year - risk.mosca["y"], abs=1e-3)


def test_isolated_low_value_system_scores_lower() -> None:
    kex = algorithm("ECDH", family="ECDH", quantum="vulnerable", primitive="key-agreement")
    high = assess(kex, PAYMENTS, MODERATE)
    low = assess(kex, INTRANET, MODERATE)
    assert low.score < high.score and low.hndl["exposed"] is False
    assert low.impact["value"] < high.impact["value"]


def test_threat_model_moves_the_probability() -> None:
    kex = algorithm("ECDH", family="ECDH", quantum="vulnerable", primitive="key-agreement")
    aggressive = assess(kex, INTRANET, ThreatModel.build("aggressive", None, None, 0.05, now=NOW))
    conservative = assess(kex, INTRANET, ThreatModel.build("conservative", None, None, 0.05, now=NOW))
    assert aggressive.mosca["probability"] > conservative.mosca["probability"]
    assert aggressive.mosca["z"] < conservative.mosca["z"]


def test_quantum_safe_cryptography_carries_no_risk() -> None:
    for artefact in (
        algorithm("AES-256-GCM", family="AES", quantum="resistant", primitive="ae", bits=256, parameter="256"),
        algorithm("ML-KEM-1024", family="ML-KEM", quantum="pqc", primitive="kem", parameter="1024"),
        algorithm("X25519MLKEM768", family="X25519MLKEM768", quantum="hybrid", primitive="kem"),
    ):
        risk = assess(artefact, PAYMENTS, MODERATE)
        assert risk.score == 0 and risk.band == "none", artefact.name
        assert risk.classification["mosca"] == "not-affected"
        assert risk.timeline == {"at_risk": None, "exposed": None, "broken": None}


def test_classically_broken_is_critical_today() -> None:
    md5 = algorithm("MD5", family="MD5", quantum="weakened", classical="broken", primitive="hash")
    risk = assess(md5, PAYMENTS, MODERATE)
    assert risk.likelihood["classical"] == 1.0 and risk.band == "critical"
    assert risk.timeline["broken"] == pytest.approx(NOW)


def test_library_end_of_life_and_pqc_path() -> None:
    old = ArtefactFacts("lib", "s1", "library", "OpenSSL 1.1.1n", "openssl", None, None, "library", {"library": "openssl"},
                        {"pqc": {"status": "native", "capable": False}, "eol": {"reached": True, "date": "2023-09-11"}})
    new = ArtefactFacts("lib2", "s1", "library", "OpenSSL 3.5.0", "openssl", None, None, "library", {"library": "openssl"},
                        {"pqc": {"status": "native", "capable": True}})
    old_risk, new_risk = assess(old, PAYMENTS, MODERATE), assess(new, PAYMENTS, MODERATE)
    assert old_risk.likelihood["classical"] == 0.6 and old_risk.score > new_risk.score
    assert "End of life" in " ".join(old_risk.drivers)
    assert new_risk.migration["key"] == "algorithm.config"  # post-quantum support is already there: enable it
    assert new_risk.score == 0


def test_estimated_system_migration_uses_the_longest_path() -> None:
    risks = [assess(algorithm(f"ECDH{i}", family="ECDH", quantum="vulnerable", primitive="key-agreement"), PAYMENTS, MODERATE) for i in range(3)]
    assert estimated_system_migration(risks) == pytest.approx(1.0 + 0.15 * 2, abs=0.01)
    assert estimated_system_migration([]) is None


def test_policy_pressure_grows_as_slack_shrinks() -> None:
    assert policy_pressure(-1) > 0.9
    assert policy_pressure(2.5) == pytest.approx(0.5)
    assert policy_pressure(8) < 0.01


# -------------------------------------------------------------- policies

def test_nist_ir_8547_dates() -> None:
    rsa2048 = algorithm("RSA-2048", family="RSA", quantum="vulnerable", primitive="signature", bits=112, parameter="2048")
    p256 = algorithm("ECDSA P-256", family="ECDSA", quantum="vulnerable", primitive="signature", bits=128)
    r = policy(evaluate(rsa2048, PAYMENTS, NOW), "nist-ir-8547")
    assert (r.deprecated_from, r.disallowed_from) == (2031.0, 2036.0)
    assert [r.status_at(y) for y in (2030.5, 2031.5, 2036.0)] == ["acceptable", "deprecated", "disallowed"]
    p = policy(evaluate(p256, PAYMENTS, NOW), "nist-ir-8547")
    assert p.deprecated_from is None and p.disallowed_from == 2036.0
    mlkem = algorithm("ML-KEM-768", family="ML-KEM", quantum="pqc", primitive="kem", parameter="768")
    assert policy(evaluate(mlkem, PAYMENTS, NOW), "nist-ir-8547").status == "approved"


def test_sp_800_131a_rules() -> None:
    def status(artefact, year=NOW):
        return policy(evaluate(artefact, PAYMENTS, NOW), "nist-sp-800-131a").status_at(year)

    assert status(algorithm("RSA-1024", family="RSA", quantum="vulnerable", primitive="signature", bits=80)) == "disallowed"
    assert status(algorithm("RSA with SHA-1", family="RSA", quantum="vulnerable", primitive="signature", bits=112, hash="SHA-1")) == "disallowed"
    hmac_sha1 = algorithm("HMAC-SHA1", family="HMAC", quantum="resistant", primitive="mac", hash="SHA-1")
    assert status(hmac_sha1) == "deprecated" and status(hmac_sha1, 2031.2) == "disallowed"  # SHA-1 retired after 2030
    assert status(algorithm("3DES", family="3DES", quantum="weakened", classical="weak", primitive="block-cipher", bits=112)) == "disallowed"
    assert status(algorithm("MD5", family="MD5", quantum="weakened", classical="broken", primitive="hash")) == "disallowed"
    assert status(algorithm("AES-128", family="AES", quantum="resistant", primitive="block-cipher", parameter="128")) == "approved"
    assert status(algorithm("ChaCha20-Poly1305", family="ChaCha20-Poly1305", quantum="resistant", primitive="ae")) == "not-approved"


def test_cnsa_2_is_strict_about_parameters_and_dates() -> None:
    def cnsa(artefact, system=PAYMENTS):
        return policy(evaluate(artefact, system, NOW), "cnsa-2.0")

    assert cnsa(algorithm("AES-256", family="AES", quantum="resistant", primitive="block-cipher", parameter="256")).status == "approved"
    aes128 = cnsa(algorithm("AES-128", family="AES", quantum="resistant", primitive="block-cipher", parameter="128"))
    assert aes128.status == "transition" and aes128.disallowed_from == 2034.0  # a service: exclusively after 2033
    assert cnsa(algorithm("ML-KEM-1024", family="ML-KEM", quantum="pqc", primitive="kem", parameter="1024")).status == "approved"
    assert cnsa(algorithm("ML-KEM-768", family="ML-KEM", quantum="pqc", primitive="kem", parameter="768")).status == "transition"
    network = SystemFacts("s3", "VPN", "VPN", "infrastructure", "high", "external", "confidential", 3.0, 2.0)
    assert cnsa(algorithm("ECDH", family="ECDH", quantum="vulnerable", primitive="key-agreement"), network).disallowed_from == 2031.0


def test_eu_roadmap_distinguishes_high_risk_systems() -> None:
    kex = algorithm("ECDH", family="ECDH", quantum="vulnerable", primitive="key-agreement")
    assert policy(evaluate(kex, PAYMENTS, NOW), "eu-pqc-roadmap").disallowed_from == 2031.0
    assert policy(evaluate(kex, INTRANET, NOW), "eu-pqc-roadmap").disallowed_from == 2036.0
