"""Policy mapping: where each artefact stands against published transition rules.

Every result carries the dates it changes status, so the same rule answers
"is this compliant today?" and "is it compliant in 2033?" (the time machine).
Statuses, from best to worst:

    approved       named by the framework as acceptable
    acceptable     permitted today, with a known end date
    transition     outside the framework's target set; must be replaced by a date
    not-approved   outside an approved set with no scheduled date (use is non-compliant)
    deprecated     permitted for now, with risk accepted by the owner
    disallowed     must not be used
    not-applicable the framework does not speak to this artefact
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .facts import ArtefactFacts, SystemFacts, knowledge, policy_family

ORDER = ["approved", "acceptable", "not-applicable", "transition", "not-approved", "deprecated", "disallowed"]

_SAFE_QUANTUM = {"pqc", "hybrid"}
_SIGNATURE_FAMILIES = {"RSA", "DSA", "ECDSA", "EdDSA", "SM2"}
_BROKEN_FAMILIES = {"DES", "RC4", "RC2", "MD4", "MD5", "PBKDF1", "Insecure PRNG", "Dual_EC_DRBG"}


@dataclass(frozen=True)
class PolicyResult:
    framework: str
    status: str
    rule: str
    deprecated_from: float | None = None
    disallowed_from: float | None = None

    def status_at(self, year: float) -> str:
        if self.disallowed_from is not None and year >= self.disallowed_from:
            return "disallowed"
        if self.deprecated_from is not None and year >= self.deprecated_from:
            return "deprecated"
        return self.status

    def as_dict(self, now: float) -> dict[str, Any]:
        data = asdict(self)
        data["status_now"] = self.status_at(now)
        return data


def _after(year: int) -> float:
    """"After 2030" takes effect at the start of 2031."""
    return float(year + 1)


def nist_ir_8547(a: ArtefactFacts) -> PolicyResult:
    rules = knowledge()["frameworks"]["nist-ir-8547"]
    if a.kind in ("library", "hardware"):
        return PolicyResult("nist-ir-8547", "not-applicable", "Covers algorithms, not software or hardware.")
    if a.quantum in _SAFE_QUANTUM:
        return PolicyResult("nist-ir-8547", "approved", "Post-quantum or hybrid key establishment and signatures are the transition's target.")
    if a.quantum != "vulnerable":
        return PolicyResult("nist-ir-8547", "not-applicable", "Symmetric and hash algorithms are addressed by SP 800-131A.")
    bits = a.classical_bits
    disallowed = _after(rules["disallowed_after"])
    if bits is not None and bits <= 112:
        return PolicyResult("nist-ir-8547", "acceptable",
                            f"Quantum-vulnerable at {bits}-bit security: deprecated after {rules['deprecated_112_after']}, disallowed after {rules['disallowed_after']}.",
                            deprecated_from=_after(rules["deprecated_112_after"]), disallowed_from=disallowed)
    return PolicyResult("nist-ir-8547", "acceptable",
                        f"Quantum-vulnerable public-key cryptography: disallowed after {rules['disallowed_after']}.", disallowed_from=disallowed)


def nist_sp_800_131a(a: ArtefactFacts, now: float) -> PolicyResult:
    rules = knowledge()["frameworks"]["nist-sp-800-131a"]
    if a.kind in ("library", "hardware", "protocol"):
        return PolicyResult("nist-sp-800-131a", "not-applicable", "Covers algorithms and key lengths.")
    family, _ = policy_family(a)
    hashed = a.identity.get("hash")
    if family in _BROKEN_FAMILIES:
        return PolicyResult("nist-sp-800-131a", "disallowed", f"{family} is not an approved algorithm.", disallowed_from=now)
    if family == "3DES":
        return PolicyResult("nist-sp-800-131a", "disallowed", f"TDEA encryption is disallowed after {rules['tdea_disallowed_after']}.",
                            disallowed_from=_after(rules["tdea_disallowed_after"]))
    if family == "DSA":
        return PolicyResult("nist-sp-800-131a", "disallowed", "DSA signature generation is no longer approved (FIPS 186-5); verification only.",
                            disallowed_from=now)
    if hashed == "SHA-1" and family in _SIGNATURE_FAMILIES:
        return PolicyResult("nist-sp-800-131a", "disallowed", "SHA-1 is disallowed for digital signature generation.", disallowed_from=now)
    bits = a.classical_bits
    if a.quantum == "vulnerable" and bits is not None and bits < 112:
        return PolicyResult("nist-sp-800-131a", "disallowed", f"{bits}-bit security is below the 112-bit minimum.", disallowed_from=now)
    if family == "SHA-1" or hashed == "SHA-1":
        return PolicyResult("nist-sp-800-131a", "deprecated", f"SHA-1 is being retired: disallowed after {rules['sha1_retired_after']}.",
                            deprecated_from=now, disallowed_from=_after(rules["sha1_retired_after"]))
    if family in rules["approved"]:
        return PolicyResult("nist-sp-800-131a", "approved", f"{family} is NIST-approved at this strength.")
    if family is None:
        return PolicyResult("nist-sp-800-131a", "not-applicable", "No algorithm could be identified.")
    return PolicyResult("nist-sp-800-131a", "not-approved", f"{family} is not in the NIST-approved set.")


def cnsa_2(a: ArtefactFacts, system: SystemFacts) -> PolicyResult:
    rules = knowledge()["frameworks"]["cnsa-2.0"]
    if a.kind in ("library", "hardware"):
        return PolicyResult("cnsa-2.0", "not-applicable", "Covers algorithms, not software or hardware.")
    category = rules["categories"].get(system.kind, rules["categories"]["application"])
    family, parameter = policy_family(a)
    approved = rules["approved"]
    if family in approved:
        allowed = approved[family]
        size = parameter or a.identity.get("parameter")
        if allowed is None or (size and str(size) in allowed):
            if family != "HMAC" or a.identity.get("hash") in ("SHA-384", "SHA-512"):
                return PolicyResult("cnsa-2.0", "approved", f"{a.name} is a CNSA 2.0 algorithm.")
    deadline = _after(category["exclusive_after"])
    return PolicyResult("cnsa-2.0", "transition",
                        f"Not in CNSA 2.0. {category['category']}: CNSA 2.0 exclusively after {category['exclusive_after']}.",
                        disallowed_from=deadline)


def eu_roadmap(a: ArtefactFacts, system: SystemFacts) -> PolicyResult:
    rules = knowledge()["frameworks"]["eu-pqc-roadmap"]
    if a.quantum != "vulnerable":
        return PolicyResult("eu-pqc-roadmap", "not-applicable", "The roadmap targets quantum-vulnerable public-key cryptography.")
    high_risk = system.criticality in ("critical", "high") or system.classification in ("secret", "restricted")
    if high_risk:
        return PolicyResult("eu-pqc-roadmap", "transition", f"High-risk use case: migrate by the end of {rules['high_risk_after']}.",
                            disallowed_from=_after(rules["high_risk_after"]))
    return PolicyResult("eu-pqc-roadmap", "transition", f"Migrate by the end of {rules['all_after']}.", disallowed_from=_after(rules["all_after"]))


def evaluate(a: ArtefactFacts, system: SystemFacts, now: float) -> list[PolicyResult]:
    return [nist_ir_8547(a), nist_sp_800_131a(a, now), cnsa_2(a, system), eu_roadmap(a, system)]


def frameworks() -> dict[str, dict[str, Any]]:
    """Publication details; ``publication`` is the document's own status (draft, revision)."""
    return {key: {"name": v["name"], "authority": v["authority"], "title": v["title"], "publication": v["status"],
                  "source": v["source"], "summary": v["summary"]}
            for key, v in knowledge()["frameworks"].items()}
