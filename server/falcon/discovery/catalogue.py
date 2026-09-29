"""The algorithm catalogue and its assessment rules.

``assess(ref)`` answers three questions for any algorithm reference:

* how strong is it today (classical security bits, NIST SP 800-57),
* what does a quantum adversary do to it (Shor breaks it, Grover weakens it,
  or it was designed to resist both), and
* what classical status follows (strong, acceptable, weak, legacy, broken).

The data lives in ``knowledge/algorithms.json`` so it can be reviewed and
updated independently of code (important for air-gapped deployments).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_KB = Path(__file__).resolve().parents[1] / "knowledge" / "algorithms.json"

QUANTUM_STATES = ("vulnerable", "weakened", "resistant", "pqc", "hybrid", "unknown")
CLASSICAL_STATES = ("strong", "acceptable", "weak", "legacy", "broken", "unknown")


@lru_cache
def knowledge() -> dict[str, Any]:
    with _KB.open(encoding="utf-8") as fh:
        data = json.load(fh)
    # Curve alias lookup, built once.
    aliases: dict[str, str] = {}
    for name, curve in data["curves"].items():
        aliases[name.lower()] = name
        for alias in curve["aliases"]:
            aliases[alias.lower()] = name
    data["_curve_aliases"] = aliases
    return data


def version() -> str:
    return knowledge()["version"]


def algorithm(name: str) -> dict[str, Any] | None:
    return knowledge()["algorithms"].get(name)


def canonical_curve(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().strip("\"'").lower().replace(" ", "")
    return knowledge()["_curve_aliases"].get(key)


def curve_bits(curve: str) -> int | None:
    entry = knowledge()["curves"].get(curve)
    return entry["bits"] if entry else None


@dataclass(frozen=True)
class AlgorithmRef:
    """A normalised reference to an algorithm and its parameters."""

    algorithm: str
    parameter: str | None = None  # key size, curve, or parameter set
    mode: str | None = None  # block-cipher mode
    padding: str | None = None
    hash: str | None = None  # hash used by a signature, HMAC or padding scheme

    def identity(self) -> dict[str, str]:
        return {k: v for k, v in (("algorithm", self.algorithm), ("parameter", self.parameter),
                                  ("mode", self.mode), ("padding", self.padding), ("hash", self.hash)) if v}

    @property
    def display(self) -> str:
        return display_name(self)


@dataclass
class Assessment:
    classical_bits: int | None
    quantum_bits: int | None
    quantum: str
    classical: str
    primitive: str | None
    reasons: list[str] = field(default_factory=list)
    nist_category: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "classical_bits": self.classical_bits, "quantum_bits": self.quantum_bits,
            "quantum": self.quantum, "classical": self.classical, "primitive": self.primitive,
            "reasons": self.reasons, "nist_category": self.nist_category,
        }


def _table_strength(table: str, bits: int) -> int:
    strength = 0
    for size, security in knowledge()["strength_tables"][table]:
        if bits >= size:
            strength = security
    return strength


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


def _classical_from_bits(bits: int | None) -> str:
    if bits is None:
        return "unknown"
    if bits >= 128:
        return "strong"
    if bits >= 112:
        return "acceptable"
    if bits >= 80:
        return "weak"
    return "broken"


_WORST = {"broken": 4, "weak": 3, "legacy": 2, "acceptable": 1, "strong": 0, "unknown": -1}


def _worse(a: str, b: str) -> str:
    return a if _WORST.get(a, -1) >= _WORST.get(b, -1) else b


def assess(ref: AlgorithmRef) -> Assessment:
    entry = algorithm(ref.algorithm)
    if entry is None:
        return Assessment(None, None, "unknown", "unknown", None, ["Not in the FALCON catalogue"])
    cls = entry["class"]
    primitive = entry["primitives"][0]
    reasons: list[str] = []
    classical_bits: int | None = entry.get("bits")
    quantum_bits: int | None = None
    quantum = entry.get("quantum")
    category: int | None = None

    if cls == "asymmetric":
        size = _int(ref.parameter)
        if entry.get("strength") == "ifc":
            size = size or 2048
            classical_bits = _table_strength("ifc", size)
            if ref.parameter is None:
                reasons.append("Key size not visible at this location; assumed 2048 bits")
        elif entry.get("strength") == "ecc":
            curve = canonical_curve(ref.parameter) if ref.parameter else None
            bits = curve_bits(curve) if curve else (size or 256)
            classical_bits = _table_strength("ecc", bits)
            if ref.parameter is None:
                reasons.append("Curve not visible at this location; assumed a 256-bit curve")
        quantum_bits = 0
        quantum = "vulnerable"
        reasons.append("Shor's algorithm recovers the private key on a cryptographically relevant quantum computer")
    elif cls == "symmetric":
        key_bits = _int(ref.parameter) or entry.get("default_bits")
        if entry.get("key_bits"):
            classical_bits = key_bits
        quantum_bits = (classical_bits or 0) // 2
        if quantum is None:
            quantum = "resistant" if (key_bits or 0) >= 192 else "weakened"
        if quantum == "weakened":
            reasons.append(f"Grover's algorithm halves the effective key strength to about {quantum_bits} bits")
        if ref.mode == "ECB":
            reasons.append("ECB mode leaks plaintext patterns")
    elif cls in ("hash", "mac", "kdf", "random"):
        if cls == "mac" and ref.algorithm == "HMAC" and ref.hash:
            inner = algorithm(ref.hash)
            output = inner.get("output_bits", 256) if inner else 256
            classical_bits = min(output, 256)
            if ref.hash in ("MD5", "SHA-1"):
                reasons.append(f"HMAC-{ref.hash} remains usable but is deprecated for new designs")
        output = entry.get("output_bits")
        quantum_bits = (output // 2) if output else (classical_bits or 0)
        if quantum is None:
            quantum = "resistant" if (quantum_bits or 0) >= 128 else "weakened"
    elif cls in ("pqc", "hybrid"):
        categories = entry.get("parameters", {})
        param = ref.parameter or entry.get("default_parameter")
        category = categories.get(str(param)) if param else None
        classical_bits = classical_bits or {1: 128, 2: 128, 3: 192, 4: 192, 5: 256}.get(category or 1)
        quantum_bits = classical_bits
        quantum = entry["quantum"]
        if cls == "hybrid":
            reasons.append("Secure while either the classical or the post-quantum component holds")
        else:
            reasons.append(f"Designed to resist quantum attacks ({entry.get('standard', 'post-quantum')})")

    classical = entry.get("classical") or _classical_from_bits(classical_bits)
    if cls == "asymmetric":
        classical = _worse(classical, _classical_from_bits(classical_bits))
        minimum = entry.get("min_acceptable_bits")
        size = _int(ref.parameter)
        if minimum and size and size < minimum and entry.get("strength") == "ifc":
            reasons.append(f"{size}-bit keys are below the {minimum}-bit minimum of SP 800-131A")
    if ref.mode == "ECB":
        classical = _worse(classical, "weak")
    if ref.hash in ("MD5", "SHA-1") and cls == "asymmetric":
        if "key-agreement" in entry.get("primitives", []) and "signature" not in entry.get("primitives", []):
            # In a key exchange the hash binds the transcript; collisions do not forge it, but it is withdrawn.
            classical = _worse(classical, "legacy")
            reasons.append(f"{ref.hash} in the key-exchange hash is deprecated (RFC 9142 for SSH)")
        else:
            classical = _worse(classical, "broken")
            reasons.append(f"Signatures over {ref.hash} are forgeable through collisions")
    if ref.padding == "PKCS1v15" and "pke" in entry.get("primitives", []) and ref.algorithm == "RSA":
        reasons.append("PKCS #1 v1.5 encryption padding is exposed to padding-oracle attacks")
    if entry.get("classical") == "broken":
        reasons.insert(0, entry["description"])

    return Assessment(classical_bits, quantum_bits, quantum or "unknown", classical, primitive, reasons, category)


def protocol_assessment(name: str, *, hybrid_key_exchange: bool = False) -> Assessment:
    entry = knowledge()["protocols"].get(name)
    classical = entry["classical"] if entry else "unknown"
    reasons = [entry["description"]] if entry else []
    if name.startswith(("SSL", "TLS", "DTLS", "SSH", "IKE", "WireGuard")):
        quantum = "hybrid" if hybrid_key_exchange else "vulnerable"
        reasons.append(
            "Negotiates a hybrid post-quantum key exchange" if hybrid_key_exchange
            else "Classical key exchange can be recorded now and decrypted later (harvest now, decrypt later)"
        )
    else:
        quantum = "unknown"
    return Assessment(None, None, quantum, classical, "protocol", reasons)


def display_name(ref: AlgorithmRef) -> str:
    a, p = ref.algorithm, ref.parameter
    entry = algorithm(a) or {}
    cls = entry.get("class")
    if cls == "asymmetric":
        if entry.get("strength") == "ifc":
            name = f"{a}-{p}" if p else a
        elif a == "EdDSA":
            name = p or "EdDSA"
        else:
            name = f"{a} {p}" if p else a
        if ref.padding in ("OAEP", "PSS"):
            name += f"-{ref.padding}"
        if ref.hash and a in ("RSA", "ECDSA", "DSA") and ref.padding != "OAEP":
            name += f" with {ref.hash}"
        return name
    if cls == "symmetric":
        name = a
        if p and entry.get("key_bits") and len(entry["key_bits"]) > 1:
            name = f"{a}-{p}"
        if ref.mode:
            name += f"-{ref.mode}"
        return name
    if a == "HMAC" and ref.hash:
        return f"HMAC-{ref.hash.replace('-', '')}"
    if a in ("PBKDF2", "HKDF") and ref.hash:
        return f"{a}-{ref.hash.replace('-', '')}"
    if cls == "pqc" and p:
        return f"{a}-{p}"
    return a
