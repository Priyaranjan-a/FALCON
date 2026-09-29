"""SARIF 2.1.0 findings for code scanning (GitHub, GitLab, Azure DevOps, IDEs).

One result per rule, artefact and location (up to ``per_artefact``
locations), so every line of code that uses the cryptography is annotated.
Levels follow the artefact's risk band; ``security-severity`` (0-10) is the
risk score over ten, which is how GitHub ranks code-scanning alerts.
Endpoint evidence has no file, so it is reported as a logical location.
"""
from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import quote

from ..domains.horizon.model import format_decimal_year
from .inventory import TOOL_NAME, TOOL_URI, TOOL_VERSION, Item, Report

SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

RULES: list[dict[str, Any]] = [
    {"id": "FALCON001", "name": "BrokenOrWeakCryptography", "level": "error", "tags": ["security", "cryptography", "CWE-327"],
     "short": "Broken or weak cryptography",
     "full": "The algorithm, key size or protocol can be attacked with classical computers today.",
     "help": "Replace it now; this does not wait for a quantum computer. See the recommendation in the result for the replacement."},
    {"id": "FALCON002", "name": "HarvestNowDecryptLater", "level": "error", "tags": ["security", "cryptography", "quantum", "CWE-327"],
     "short": "Harvest now, decrypt later exposure",
     "full": "Quantum-vulnerable key establishment protects data whose confidentiality must outlast the arrival of a cryptographically relevant quantum computer (Mosca: X + Y > Z).",
     "help": "Traffic recorded today becomes readable later. Move key establishment to ML-KEM, or hybrid X25519MLKEM768 during the transition, before the date in the result."},
    {"id": "FALCON003", "name": "QuantumVulnerableKeyEstablishment", "level": "warning", "tags": ["security", "cryptography", "quantum"],
     "short": "Quantum-vulnerable key establishment or encryption",
     "full": "RSA, Diffie-Hellman and elliptic-curve key establishment are broken by Shor's algorithm.",
     "help": "Plan the move to ML-KEM (FIPS 203), with a hybrid key exchange during the transition."},
    {"id": "FALCON004", "name": "QuantumVulnerableSignature", "level": "warning", "tags": ["security", "cryptography", "quantum"],
     "short": "Quantum-vulnerable signature or certificate",
     "full": "RSA, DSA, ECDSA and EdDSA signatures can be forged once a cryptographically relevant quantum computer exists.",
     "help": "Plan the move to ML-DSA (FIPS 204) or SLH-DSA (FIPS 205); long-lived roots and firmware signing first."},
    {"id": "FALCON005", "name": "QuantumWeakenedSymmetric", "level": "note", "tags": ["security", "cryptography", "quantum"],
     "short": "Symmetric strength halved by Grover's algorithm",
     "full": "128-bit symmetric keys and 256-bit hashes keep 64 and 128 bits of security respectively against a quantum adversary.",
     "help": "Prefer AES-256 and SHA-384 or stronger for data that must stay protected for decades."},
    {"id": "FALCON006", "name": "LibraryWithoutPostQuantumPath", "level": "warning", "tags": ["security", "dependency", "quantum"],
     "short": "Cryptographic library at end of life or without a post-quantum path",
     "full": "The library version is past its end of life, or it offers no post-quantum algorithms, so the application cannot migrate without replacing or upgrading it.",
     "help": "Upgrade to a release with ML-KEM and ML-DSA (for example OpenSSL 3.5, Bouncy Castle 1.79, Go 1.24)."},
    {"id": "FALCON007", "name": "PolicyViolation", "level": "error", "tags": ["security", "compliance"],
     "short": "Disallowed by a compliance framework",
     "full": "NIST IR 8547, NIST SP 800-131A, CNSA 2.0 or the EU PQC roadmap disallows this use today.",
     "help": "The result lists the framework and the rule. Replace the cryptography, or record a time-bound exception."},
    {"id": "FALCON008", "name": "CertificateExpired", "level": "warning", "tags": ["security", "pki"],
     "short": "Expired certificate",
     "full": "The certificate is past its validity period.",
     "help": "Renew it; when you do, consider issuing from a post-quantum or composite hierarchy."},
]
_INDEX = {r["id"]: i for i, r in enumerate(RULES)}
_LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note", "none": "note"}


def _rules_for(item: Item, report: Report) -> list[tuple[str, str]]:
    """(rule id, message) pairs that apply to an artefact."""
    a, r = item.facts, item.risk
    out: list[tuple[str, str]] = []
    rec = item.recommendation or {}
    fix = f" Recommended: {rec['title']}." if rec.get("title") and rec.get("action") != "keep" else ""
    where = f" in {item.system.name}"
    if a.classical in ("broken", "weak"):
        out.append(("FALCON001", f"{a.name} is {a.classical} against classical attack today{where}.{fix}"))
    if r.hndl.get("exposed"):
        years = r.mosca.get("exposure_years") or 0
        out.append(("FALCON002", f"{a.name} protects data that must stay confidential {years:.1f} years beyond the planning horizon "
                                 f"(X {r.mosca['x']:g} + Y {r.mosca['y']:g} > Z {r.mosca['z']:g}){where}.{fix}"))
    elif a.quantum == "vulnerable" and "confidentiality" in r.roles:
        out.append(("FALCON003", f"{a.name} establishes keys with quantum-vulnerable cryptography{where}.{fix}"))
    if a.quantum == "vulnerable" and "authenticity" in r.roles and a.kind != "protocol":
        broken = r.timeline.get("broken")
        when = f" Disallowed from {format_decimal_year(broken)}." if broken else ""
        out.append(("FALCON004", f"{a.name} signs with quantum-vulnerable cryptography{where}.{when}{fix}"))
    if a.quantum == "weakened":
        out.append(("FALCON005", f"{a.name} has its security halved by Grover's algorithm{where}.{fix}"))
    if a.kind == "library":
        pqc = a.properties.get("pqc") or {}
        eol = a.properties.get("eol") or {}
        if eol.get("reached"):
            out.append(("FALCON006", f"{a.name} reached end of life on {eol.get('date')}{where}.{fix}"))
        elif pqc.get("status") == "none" or pqc.get("capable") is False:
            since = f" Post-quantum support arrives in {pqc['since']}." if pqc.get("since") else ""
            out.append(("FALCON006", f"{a.name} cannot use post-quantum algorithms at this version{where}.{since}{fix}"))
    disallowed = [p for p in r.policies if p.status_at(report.model.now) == "disallowed"]
    if disallowed:
        p = disallowed[0]
        out.append(("FALCON007", f"{a.name} is disallowed by {p.framework.upper()}: {p.rule}{where}."))
    if a.kind == "certificate" and a.properties.get("expired"):
        out.append(("FALCON008", f"Certificate {a.name} expired on {str(a.properties.get('not_after', ''))[:10]}{where}."))
    return out


def _level(rule_id: str, item: Item) -> str:
    if rule_id in ("FALCON001", "FALCON007"):
        return "error"
    if rule_id == "FALCON008":
        return "warning"
    return _LEVEL.get(item.risk.band, "note")


def _location(path: str, line: int | None, column: int | None, detector: str) -> dict[str, Any]:
    if detector == "tls-endpoint" or "://" in path:
        return {"logicalLocations": [{"name": path, "kind": "resource"}]}
    region: dict[str, Any] = {}
    if line:
        region["startLine"] = int(line)
        if column:
            region["startColumn"] = int(column)
    physical: dict[str, Any] = {"artifactLocation": {"uri": quote(path.replace("\\", "/"), safe="/:@!$&'()*+,;="), "uriBaseId": "SRCROOT"}}
    if region:
        physical["region"] = region
    return {"physicalLocation": physical}


def build(report: Report, *, per_artefact: int = 10, minimum: str | None = None) -> dict[str, Any]:
    order = ["none", "low", "medium", "high", "critical"]
    floor = order.index(minimum) if minimum in order else 0
    results: list[dict[str, Any]] = []
    for item in sorted(report.items, key=lambda i: (-i.risk.score, i.facts.name)):
        if order.index(item.risk.band) < floor and item.facts.classical not in ("broken", "weak"):
            continue
        # An artefact seen twice on one line (directly and through a relation) is one annotation.
        unique = list({(o.path, o.line): o for o in item.occurrences}.values())[:per_artefact]
        for rule_id, message in _rules_for(item, report):
            locations = unique or [None]
            for occ in locations:
                result: dict[str, Any] = {
                    "ruleId": rule_id, "ruleIndex": _INDEX[rule_id], "level": _level(rule_id, item),
                    "message": {"text": message},
                    "partialFingerprints": {"falconArtefact/v1": hashlib.sha256(
                        f"{rule_id}|{item.ref}|{occ.path if occ else ''}|{occ.line if occ else ''}".encode()).hexdigest()},
                    "properties": {
                        "security-severity": f"{max(item.risk.score, 10 if rule_id in ('FALCON001', 'FALCON007') else 0) / 10:.1f}",
                        "falcon/artefact": item.facts.name, "falcon/kind": item.facts.kind, "falcon/system": item.system.code,
                        "falcon/quantum": item.facts.quantum, "falcon/risk": item.risk.score, "falcon/band": item.risk.band,
                        "falcon/bom-ref": item.ref,
                    },
                }
                if occ:
                    result["locations"] = [_location(occ.path, occ.line, occ.column, occ.detector)]
                rec = item.recommendation or {}
                if rec.get("primary"):
                    result["properties"]["falcon/replace-with"] = rec["primary"]["name"]
                results.append(result)

    driver_rules = [{
        "id": r["id"], "name": r["name"], "shortDescription": {"text": r["short"]}, "fullDescription": {"text": r["full"]},
        "help": {"text": r["help"], "markdown": f"**{r['short']}**\n\n{r['full']}\n\n{r['help']}"},
        "defaultConfiguration": {"level": r["level"]},
        "helpUri": f"{TOOL_URI}docs/rules#{r['id'].lower()}",
        "properties": {"tags": r["tags"], "precision": "high"},
    } for r in RULES]
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": TOOL_NAME, "version": TOOL_VERSION, "semanticVersion": TOOL_VERSION,
                                "informationUri": TOOL_URI, "rules": driver_rules}},
            "automationDetails": {"id": f"falcon/{report.scope}/"},
            "originalUriBaseIds": {"SRCROOT": {"description": {"text": "The root of the scanned source."}}},
            "invocations": [{"executionSuccessful": True, "endTimeUtc": report.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")}],
            "results": results,
            "properties": {"organisation": report.organisation, "threatModel": report.model.scenario,
                           "planningHorizon": format_decimal_year(report.model.planning_year)},
        }],
    }
