"""What the risk model needs to know about an artefact and its system."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_KB = Path(__file__).resolve().parents[1] / "knowledge" / "risk.json"


@lru_cache
def knowledge() -> dict[str, Any]:
    return json.loads(_KB.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class SystemFacts:
    id: str
    code: str
    name: str
    kind: str
    criticality: str
    exposure: str
    classification: str
    shelf_life_years: float
    migration_years: float


@dataclass(frozen=True)
class ArtefactFacts:
    id: str
    system_id: str
    kind: str
    name: str
    family: str | None
    quantum: str | None
    classical: str | None
    primitive: str | None
    identity: dict[str, Any]
    properties: dict[str, Any]
    status: str = "active"
    functions: frozenset[str] = field(default_factory=frozenset)
    detectors: frozenset[str] = field(default_factory=frozenset)

    @property
    def assessment(self) -> dict[str, Any]:
        return self.properties.get("assessment") or {}

    @property
    def classical_bits(self) -> int | None:
        bits = self.assessment.get("classical_bits")
        return bits if isinstance(bits, int) else None


# ------------------------------------------------------------------ roles

CONFIDENTIALITY = "confidentiality"
AUTHENTICITY = "authenticity"
INTEGRITY = "integrity"
ENABLING = "enabling"

_CONFIDENTIALITY_FUNCTIONS = {"key-agree", "encrypt", "kem", "tls-cipher-suite", "secure-channel", "tls", "ipsec", "key-transport"}
_AUTHENTICITY_FUNCTIONS = {"sign", "certificate", "certificate-issuance"}
_CONFIDENTIALITY_PRIMITIVES = {"key-agreement", "kem", "pke"}
_SYMMETRIC_PRIMITIVES = {"block-cipher", "stream-cipher", "ae", "hash", "xof", "mac", "kdf", "drbg", "prng"}


def roles(a: ArtefactFacts) -> frozenset[str]:
    """The security properties an artefact provides, from how and where it was found."""
    if a.kind in ("library", "hardware"):
        return frozenset({ENABLING})
    if a.kind == "protocol":
        return frozenset({CONFIDENTIALITY, AUTHENTICITY})
    if a.kind == "certificate":
        return frozenset({AUTHENTICITY})
    if a.kind == "cloud_service":
        usage = str(a.properties.get("key_usage") or "").upper()
        if "ENCRYPT" in usage or "WRAP" in usage:
            return frozenset({CONFIDENTIALITY})
        if "SIGN" in usage or "MAC" in usage:
            return frozenset({AUTHENTICITY})
        return frozenset({CONFIDENTIALITY, AUTHENTICITY})
    if a.primitive in _SYMMETRIC_PRIMITIVES:
        return frozenset({INTEGRITY if a.primitive in ("hash", "xof", "mac", "kdf", "drbg", "prng") else CONFIDENTIALITY})
    found: set[str] = set()
    if a.primitive == "signature":
        # Signature algorithms only authenticate, except RSA, which also transports keys
        # (RSA key exchange in TLS cipher suites, RSA-OAEP and PKCS #1 v1.5 encryption).
        if a.family == "RSA" and a.functions & {"encrypt", "key-transport", "tls-cipher-suite"}:
            found.add(CONFIDENTIALITY)
    elif a.primitive in _CONFIDENTIALITY_PRIMITIVES or a.functions & _CONFIDENTIALITY_FUNCTIONS:
        found.add(CONFIDENTIALITY)
    if a.primitive == "signature" or a.functions & _AUTHENTICITY_FUNCTIONS:
        found.add(AUTHENTICITY)
    if a.kind == "key" and not found:
        found.add(AUTHENTICITY)
    return frozenset(found or {AUTHENTICITY})


# ----------------------------------------------------------- key families

_KEY_FAMILY = {"EC": "ECDSA", "ECDSA": "ECDSA", "Ed25519": "EdDSA", "Ed448": "EdDSA", "EdDSA": "EdDSA", "RSA": "RSA", "DSA": "DSA",
               "DH": "DH", "X25519": "X25519", "X448": "X448", "ML-DSA": "ML-DSA", "ML-KEM": "ML-KEM", "SLH-DSA": "SLH-DSA"}


def policy_family(a: ArtefactFacts) -> tuple[str | None, str | None]:
    """(algorithm family, parameter) the policy rules key on."""
    if a.kind == "algorithm":
        return a.identity.get("algorithm"), a.identity.get("parameter")
    if a.kind in ("key", "certificate"):
        text = str(a.properties.get("key_algorithm") or "")
        token = re.split(r"[-\s]", text, maxsplit=1)[0] if text else ""
        parameter = re.search(r"(\d{2,5}|P-\d{3})", text)
        return _KEY_FAMILY.get(token, token or None), parameter.group(1) if parameter else None
    if a.kind == "cloud_service":
        spec = str(a.properties.get("key_spec") or "").upper()
        if spec.startswith("RSA"):
            return "RSA", spec.split("_")[-1]
        if spec.startswith(("ECC", "EC_")):
            return "ECDSA", None
        if spec.startswith("ML_DSA"):
            return "ML-DSA", spec.split("_")[-1]
        if spec.startswith(("SYMMETRIC", "AES")):
            return "AES", "256"
        if spec.startswith("HMAC"):
            return "HMAC", None
    return None, None
