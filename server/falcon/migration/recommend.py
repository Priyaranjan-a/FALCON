"""What to replace each artefact with, and what the change costs.

A recommendation names a primary replacement, a hybrid option where one fits
the transition, alternatives, the size overhead against what is deployed
today, the work involved and the steps. Parameters follow the system's
sensitivity: category 5 (ML-KEM-1024, ML-DSA-87, P-384 hybrids) for secret or
restricted data and mission-critical systems, category 3 otherwise.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..risk.facts import AUTHENTICITY, CONFIDENTIALITY, ArtefactFacts, SystemFacts, policy_family
from ..risk.model import Risk

_KB = Path(__file__).resolve().parents[1] / "knowledge" / "pqc.json"

_SYMMETRIC_REPLACEMENTS = {
    "3DES": "AES-256-GCM", "DES": "AES-256-GCM", "RC4": "AES-256-GCM", "RC2": "AES-256-GCM", "Blowfish": "AES-256-GCM",
    "IDEA": "AES-256-GCM", "CAST5": "AES-256-GCM", "AES": "AES-256-GCM", "Camellia": "AES-256-GCM", "SEED": "AES-256-GCM",
    "MD4": "SHA-384", "MD5": "SHA-384", "SHA-1": "SHA-384", "RIPEMD-160": "SHA-384", "SHA-224": "SHA-384",
    "HMAC": "HMAC-SHA-384", "PBKDF1": "Argon2id", "PBKDF2": "Argon2id", "Insecure PRNG": "CSPRNG", "Dual_EC_DRBG": "CSPRNG",
}
_LANGUAGE = {"rules:java": "java", "java-bytecode": "java", "rules:go": "go", "rules:python": "python", "python-ast": "python",
             "rules:javascript": "javascript", "rules:rust": "rust", "rules:c": "c", "rules:csharp": "csharp"}


@lru_cache
def knowledge() -> dict[str, Any]:
    return json.loads(_KB.read_text(encoding="utf-8"))


def _alg(name: str, why: str) -> dict[str, Any]:
    spec = knowledge()["algorithms"][name]
    return {"name": name, "standard": spec["standard"], "category": spec.get("category"), "summary": spec["summary"], "why": why,
            "sizes": {k: spec[k] for k in ("public_key", "ciphertext", "signature") if k in spec}}


def _high_assurance(system: SystemFacts) -> bool:
    return system.classification in ("secret", "restricted") or system.criticality == "critical"


def _context(a: ArtefactFacts) -> str:
    setting = str(a.properties.get("setting") or "").lower()
    rules = " ".join(a.detectors)
    if "kex" in setting or "hostkey" in setting or "ssh" in setting or a.identity.get("protocol") == "SSH":
        return "ssh"
    if "ike" in setting or "esp" in setting or "ipsec" in a.functions or a.identity.get("protocol") == "IPsec":
        return "ipsec"
    if a.functions & {"tls", "tls-cipher-suite", "secure-channel"} or "tls-endpoint" in rules or a.identity.get("protocol") == "TLS":
        return "tls"
    if a.detectors & {"protocol-config", "infrastructure-as-code"}:
        return "config"
    return "code"


def _language(a: ArtefactFacts) -> str:
    for detector in a.detectors:
        if detector in _LANGUAGE:
            return _LANGUAGE[detector]
    return "default"


def _overhead(before_family: str | None, after: dict[str, Any], field: str) -> dict[str, Any] | None:
    classical = knowledge()["classical_sizes"].get(before_family or "", {})
    sizes = after.get("sizes", {})
    if field == "kem":
        was = classical.get("public_key")
        now = sizes.get("public_key", 0) + sizes.get("ciphertext", 0)
        if was:
            return {"before": was * 2, "after": now, "delta": now - was * 2, "unit": "bytes per key exchange"}
        return {"before": None, "after": now, "delta": None, "unit": "bytes per key exchange"}
    was = (classical.get("public_key") or 0) + (classical.get("signature") or 0)
    now = sizes.get("public_key", 0) + sizes.get("signature", 0)
    return {"before": was or None, "after": now, "delta": (now - was) if was else None, "unit": "bytes per public key and signature"}


def recommend(a: ArtefactFacts, risk: Risk, system: SystemFacts, benchmarks: dict[str, Any] | None = None) -> dict[str, Any]:
    strong = _high_assurance(system)
    family, parameter = policy_family(a)
    quantum = a.quantum or "unknown"
    classical = a.classical or "unknown"
    effort = {"years": risk.migration["years"], "label": risk.migration["label"]}
    base = {"effort": effort, "grade": "Category 5 (CNSA-aligned)" if strong else "Category 3", "hybrid": None, "alternatives": [], "overhead": None, "latency": None}

    def result(action: str, title: str, summary: str, primary: dict[str, Any] | None, steps: list[str], **extra: Any) -> dict[str, Any]:
        out = {**base, "action": action, "title": title, "summary": summary, "primary": primary, "steps": steps, **extra}
        if benchmarks and primary:
            out["latency"] = _latency(primary["name"], family, benchmarks)
        return out

    # ------------------------------------------------------------ enabling
    if a.kind == "library":
        pqc = a.properties.get("pqc") or {}
        eol = (a.properties.get("eol") or {}).get("reached")
        lang = {"maven": "java", "gradle": "java", "go": "go", "pypi": "python", "npm": "javascript", "cargo": "rust", "nuget": "csharp"}.get(
            str(a.properties.get("ecosystem") or ""), "c")
        target = knowledge()["libraries"].get(lang, knowledge()["libraries"]["default"])
        if pqc.get("capable"):
            return result("enable", "Turn on post-quantum algorithms", "This version already implements the NIST standards: enable hybrid key exchange and plan ML-DSA.",
                          None, ["Enable X25519MLKEM768 in TLS configuration.", "Expose ML-KEM and ML-DSA to the applications that need them."])
        if pqc.get("status") == "native" and pqc.get("since"):
            return result("upgrade", f"Upgrade to {a.properties.get('library')} {pqc['since']} or later",
                          f"Post-quantum support arrived in {pqc['since']}." + (" This branch is also past its end of life." if eol else ""), None,
                          [f"Upgrade {a.properties.get('package') or a.name} to {pqc['since']} or later.", "Rebuild and run regression tests.", "Enable hybrid key exchange."])
        return result("replace", f"Move to {target['name']}", target["summary"] + (" The current library is past its end of life." if eol else ""), None,
                      ["Choose the replacement and wrap it behind the existing crypto interface.", "Migrate call sites, then remove the old dependency."])

    if a.kind == "hardware":
        return result("refresh", "Plan a post-quantum hardware refresh", "Confirm the vendor's firmware roadmap for ML-KEM and ML-DSA, and budget for modules validated under FIPS 140-3 with them.",
                      None, ["Ask the vendor for its PQC firmware schedule.", "Test ML-DSA key generation and signing in the module.", "Schedule replacement where no firmware path exists."])

    if a.kind == "cloud_service" and quantum == "vulnerable":
        primary = _alg("ML-DSA-87" if strong else "ML-DSA-65", "Signing keys: the provider's KMS offers ML-DSA key specs.") if AUTHENTICITY in risk.roles and CONFIDENTIALITY not in risk.roles else None
        return result("replace", "Create post-quantum keys in the KMS", "Create ML-DSA keys where the provider supports them (AWS KMS and Google Cloud KMS offer ML-DSA), move workloads to them and retire the RSA or ECC keys.",
                      primary, ["Create the new key and grant the same permissions.", "Switch signers or wrapping to the new key.", "Enable automatic rotation; schedule deletion of the old key."])

    # -------------------------------------------------- symmetric and hash
    if quantum in ("resistant", "weakened", "unknown") and a.kind == "algorithm" and a.primitive not in ("key-agreement", "kem", "signature", "pke"):
        replacement = _SYMMETRIC_REPLACEMENTS.get(family or "")
        weak_aes = family == "AES" and (str(parameter or a.identity.get("parameter") or "256") != "256" or a.identity.get("mode") == "ECB")
        if replacement and (classical in ("broken", "weak", "legacy") or quantum == "weakened" or weak_aes or (family == "HMAC" and a.identity.get("hash") == "SHA-1") or (family == "PBKDF2" and a.identity.get("hash") == "SHA-1")):
            primary = _alg(replacement, "Restores a 128-bit post-quantum security margin and meets SP 800-131A and CNSA 2.0.")
            return result("replace", f"Replace with {replacement}", knowledge()["algorithms"][replacement]["summary"], primary,
                          [f"Replace {a.name} with {replacement} in {('configuration' if _context(a) != 'code' else 'code')}.",
                           "Re-encrypt or re-hash stored data on next write, keeping a read path for old records."])
        return result("keep", "No change needed", "Symmetric and hash algorithms at this strength stay safe against quantum attack.", None, [])

    if quantum in ("pqc", "hybrid", "resistant") and classical not in ("broken", "weak"):
        if strong and family == "ML-KEM" and str(parameter) != "1024":
            return result("strengthen", "Move to ML-KEM-1024", "CNSA 2.0 requires ML-KEM-1024 for national security systems.", _alg("ML-KEM-1024", "CNSA 2.0 parameter set."), ["Switch the parameter set; sizes grow by about a third."])
        if strong and family == "ML-DSA" and str(parameter) != "87":
            return result("strengthen", "Move to ML-DSA-87", "CNSA 2.0 requires ML-DSA-87 for national security systems.", _alg("ML-DSA-87", "CNSA 2.0 parameter set."), ["Switch the parameter set when keys are next rotated."])
        return result("keep", "Already quantum-safe", "Keep it, and keep its implementation current.", None, [])

    # --------------------------------------------------------- protocols
    if a.kind == "protocol":
        proto = a.identity.get("protocol")
        version = str(a.identity.get("version") or "")
        if proto == "SSH":
            primary = _alg("mlkem768x25519-sha256", "OpenSSH 10 negotiates it by default; OpenSSH 9.0+ offers sntrup761x25519.")
            return result("upgrade", "Enable hybrid ML-KEM key exchange in SSH", primary["summary"], primary,
                          ["Upgrade OpenSSH to 10.0 or later on servers and clients.", "Put mlkem768x25519-sha256 first in KexAlgorithms.", "Remove diffie-hellman-group*-sha1."],
                          alternatives=[_alg("X25519MLKEM768", "Same construction as TLS.")])
        if proto == "IPsec":
            primary = _alg("IKEv2 + ML-KEM-768 (RFC 9370)", "Adds a post-quantum exchange without losing the classical one.")
            return result("upgrade", "Add an ML-KEM exchange to IKEv2", primary["summary"], primary,
                          ["Confirm RFC 9370 support in both gateways.", "Add ADDKE1 = ML-KEM-768 to the proposals.", "Retire IKEv1 and DH groups below 3072 bits."])
        hybrid = "SecP384r1MLKEM1024" if strong else "X25519MLKEM768"
        primary = _alg(hybrid, "Protects recorded traffic now; every current browser and OpenSSL 3.5 negotiate it.")
        steps = ["Move to TLS 1.3 everywhere; remove TLS 1.0 and 1.1." if version in ("1.0", "1.1") or "SSL" in a.name else "Keep TLS 1.3 as the preferred version.",
                 f"Offer {hybrid} first in the key-exchange groups.", "Watch handshake sizes on middleboxes that cap ClientHello length."]
        return result("upgrade", f"TLS 1.3 with {hybrid}", primary["summary"], primary, steps,
                      overhead=_overhead("X25519", primary, "kem"), alternatives=[_alg("ML-KEM-1024", "Pure post-quantum once every peer supports it.")])

    # ---------------------------------------------------- key establishment
    if CONFIDENTIALITY in risk.roles and (a.primitive in ("key-agreement", "kem", "pke") or family in ("RSA", "DH", "ECDH", "X25519", "X448")):
        context = _context(a)
        if context == "ssh":
            primary = _alg("mlkem768x25519-sha256", "The SSH key exchange that protects recorded sessions.")
            return result("replace", "Hybrid ML-KEM key exchange for SSH", primary["summary"], primary,
                          ["Upgrade OpenSSH to 10.0+.", f"Replace {a.name} in KexAlgorithms with mlkem768x25519-sha256."], overhead=_overhead(family, primary, "kem"))
        if context in ("tls", "config"):
            name = "SecP384r1MLKEM1024" if strong else "X25519MLKEM768"
            primary = _alg(name, "Hybrid: stops harvest-now-decrypt-later today while keeping classical security.")
            return result("replace", f"Hybrid key exchange: {name}", primary["summary"], primary,
                          [f"Offer {name} first in the TLS groups or cipher configuration.", f"Keep {a.name} as a fallback only until every peer supports the hybrid.", "Remove the fallback before the NIST 2030 deprecation."],
                          overhead=_overhead(family, primary, "kem"), alternatives=[_alg("ML-KEM-1024" if strong else "ML-KEM-768", "Pure ML-KEM once peers support it.")])
        name = "ML-KEM-1024" if strong else "ML-KEM-768"
        lib = knowledge()["libraries"].get(_language(a), knowledge()["libraries"]["default"])
        return result("replace", f"Replace with {name}", knowledge()["algorithms"][name]["summary"], _alg(name, "NIST's standard key encapsulation (FIPS 203)."),
                      [f"Use {lib['name']}.", f"Replace {a.name} key agreement or key transport with {name} encapsulation.", "Derive session keys from the shared secret with HKDF-SHA-384."],
                      hybrid=_alg("X-Wing", "Keeps X25519 alongside ML-KEM during the transition."), overhead=_overhead(family, _alg(name, ""), "kem"))

    # ----------------------------------------------------------- signatures
    ca = a.kind == "certificate" and a.properties.get("is_ca")
    long_lived = ca or "firmware" in a.name.lower() or "code" in str(a.properties.get("setting") or "").lower()
    if ca:
        primary = _alg("ML-DSA-87", "A new root and intermediates signed with ML-DSA-87.")
        return result("reissue", "Build a post-quantum CA hierarchy", "Stand up an ML-DSA hierarchy beside the current one, cross-certify during the transition and distribute the new roots to every relying party.",
                      primary, ["Generate the new root in an HSM that supports ML-DSA or SLH-DSA.", "Issue new intermediates; cross-sign from the current root.", "Distribute trust anchors, then re-issue leaf certificates.", "Retire the classical hierarchy."],
                      alternatives=[_alg("SLH-DSA-SHA2-192s", "Hash-based: the most conservative choice for a root that must last decades.")],
                      hybrid=_alg("Composite ML-DSA-65 + ECDSA P-256", "One certificate for both old and new relying parties."))
    name = "ML-DSA-87" if strong else "ML-DSA-65"
    primary = _alg(name, "NIST's standard digital signature (FIPS 204).")
    if a.kind == "certificate":
        expired = a.properties.get("expired")
        return result("reissue", f"Re-issue with {name}", ("It has expired: replace it now. " if expired else "") + "Request a certificate with an ML-DSA key from a post-quantum-capable CA; use a composite certificate where relying parties still validate classically.",
                      primary, ["Generate an ML-DSA key pair.", "Request issuance from the post-quantum hierarchy.", "Deploy and confirm clients validate the chain."],
                      hybrid=_alg("Composite ML-DSA-65 + ECDSA P-256", "Transition option for mixed relying parties."), overhead=_overhead(family, primary, "signature"))
    alternatives = [_alg("FN-DSA-512", "Smaller signatures for bandwidth-constrained protocols.")]
    if long_lived:
        alternatives.insert(0, _alg("LMS", "Stateful hash-based signing for software and firmware (CNSA 2.0)."))
    lib = knowledge()["libraries"].get(_language(a), knowledge()["libraries"]["default"])
    steps = [f"Generate {name} keys{' in the key store' if a.kind == 'key' else ''}.", f"Replace {a.name} signing and verification with {name}" + (f" using {lib['name']}." if a.kind == "algorithm" else "."),
             "Support both signatures during the transition, then remove the classical one."]
    if a.kind == "key" and a.properties.get("private") and not a.properties.get("encrypted"):
        steps.insert(0, "Move the private key into an HSM or an encrypted keystore now.")
    return result("replace", f"Replace with {name}", knowledge()["algorithms"][name]["summary"], primary, steps,
                  hybrid=_alg("Composite ML-DSA-65 + ECDSA P-256", "Both signatures during the transition."), alternatives=alternatives,
                  overhead=_overhead(family, primary, "signature"))


def _latency(name: str, family: str | None, benchmarks: dict[str, Any]) -> dict[str, Any] | None:
    """Measured cost of the recommendation against what it replaces, from the benchmark lab."""
    results = {r["algorithm"]: r for r in benchmarks.get("results", [])}
    mapping = {"X25519MLKEM768": "X25519MLKEM768", "SecP384r1MLKEM1024": "ML-KEM-1024", "ML-KEM-768": "ML-KEM-768", "ML-KEM-1024": "ML-KEM-1024",
               "ML-DSA-65": "ML-DSA-65", "ML-DSA-87": "ML-DSA-87", "ML-DSA-44": "ML-DSA-44", "X-Wing": "X25519MLKEM768", "mlkem768x25519-sha256": "X25519MLKEM768"}
    before = {"RSA": "RSA-2048", "ECDSA": "ECDSA P-256", "EdDSA": "Ed25519", "ECDH": "ECDH P-256", "X25519": "X25519", "DH": "ECDH P-256", "DSA": "ECDSA P-256"}
    after = results.get(mapping.get(name, ""))
    was = results.get(before.get(family or "", ""))
    if not after:
        return None
    return {"after": after, "before": was}
