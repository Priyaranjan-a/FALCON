"""Quantum risk of one cryptographic artefact.

Mosca per artefact
    X  lifetime: how long what the artefact protects must stay protected.
       Confidentiality (key establishment, encryption): the system's data
       shelf-life, because traffic can be harvested today and decrypted later.
       Authenticity (signatures, certificates): how long the signatures must
       stay trustworthy (a certificate's remaining validity; otherwise none,
       because a forgery cannot reach back in time).
    Y  migration effort for this artefact (knowledge/risk.json), from what it
       is and where it was found: a configuration setting, code, a binary, a
       certificate authority, a hardware module.
    Z  the organisation's planning horizon (threat model).
    Exposed when X + Y > Z; the probabilistic form is P(CRQC within X + Y).

Score (0-100) = 100 x impact x likelihood, explained term by term.
    impact      system criticality x exposure (x data classification when the
                artefact protects confidentiality)
    likelihood  the largest of
                - classical: attackable today (broken, weak, legacy)
                - quantum: severity x P(CRQC within X + Y)
                - policy: pressure from the nearest compliance deadline, given
                  the time the migration needs
                - for libraries: end of life, or no post-quantum path

Harvest now, decrypt later (HNDL)
    A quantum-vulnerable artefact that protects confidentiality on a system
    reachable by an adversary is harvestable: recorded traffic becomes readable
    once a CRQC exists. It is exposed when its Mosca exposure is positive.

Time machine
    Each artefact carries the years its state changes (at risk, exposed,
    non-compliant or broken) so the console can replay any year instantly.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..domains.horizon.model import ThreatModel
from . import policies
from .facts import AUTHENTICITY, CONFIDENTIALITY, ENABLING, ArtefactFacts, SystemFacts, knowledge, roles

_CODE_DETECTORS = ("rules:", "python-ast", "java-bytecode")


@dataclass
class Risk:
    artefact_id: str
    system_id: str
    score: int
    band: str
    roles: list[str]
    impact: dict[str, Any]
    likelihood: dict[str, Any]
    mosca: dict[str, Any]
    migration: dict[str, Any]
    lifetime: dict[str, Any]
    hndl: dict[str, Any]
    classification: dict[str, Any]
    timeline: dict[str, Any]
    drivers: list[str] = field(default_factory=list)
    policies: list[policies.PolicyResult] = field(default_factory=list)


# ------------------------------------------------------------- components

def migration_effort(a: ArtefactFacts) -> tuple[str, float]:
    effort = knowledge()["migration"]
    if a.kind == "algorithm":
        if any(d.startswith(_CODE_DETECTORS) for d in a.detectors):
            key = "algorithm.code"
        elif "binaries" in a.detectors:
            key = "algorithm.binary"
        else:
            key = "algorithm.config"
    elif a.kind == "certificate":
        key = "certificate.ca" if a.properties.get("is_ca") else "certificate.leaf"
    elif a.kind == "library":
        pqc = a.properties.get("pqc") or {}
        if pqc.get("capable"):
            key = "algorithm.config"
        elif pqc.get("status") == "none":
            key = "library.replace"
        else:
            key = "library.upgrade"
    else:
        key = {"protocol": "protocol", "key": "key", "hardware": "hardware", "cloud_service": "cloud_service"}.get(a.kind, "algorithm.code")
    return key, float(effort[key]["years"])


def lifetime_years(a: ArtefactFacts, artefact_roles: frozenset[str], system: SystemFacts) -> tuple[float, str]:
    if CONFIDENTIALITY in artefact_roles or ENABLING in artefact_roles:
        return float(system.shelf_life_years), "System data shelf-life"
    if a.kind == "certificate":
        days = a.properties.get("days_remaining")
        # Capped at 50 years: test and self-signed certificates can claim centuries.
        return min(50.0, max(0.0, float(days) / 365.25)) if isinstance(days, (int, float)) else 0.0, "Remaining certificate validity"
    return 0.0, "Signatures: no retroactive exposure"


def band_for(score: int) -> str:
    for band in knowledge()["scoring"]["bands"]:
        if score >= band["min"]:
            return band["key"]
    return "none"


def bucket(value: float, buckets: list[dict[str, Any]]) -> str:
    for b in buckets:
        if value < b["max"]:
            return b["key"]
    return buckets[-1]["key"]


def lifetime_band(years: float) -> str:
    for b in knowledge()["scoring"]["lifetime_bands"]:
        if years < b["max"]:
            return b["key"]
    return "archival"


def policy_pressure(slack_years: float) -> float:
    """1 when the deadline cannot be met; halves 2.5 years before it is out of reach."""
    p = knowledge()["scoring"]["policy_pressure"]
    return 1.0 / (1.0 + math.exp((slack_years - p["midpoint_years"]) / p["spread_years"]))


# ------------------------------------------------------------------ assess

def assess(a: ArtefactFacts, system: SystemFacts, model: ThreatModel) -> Risk:
    s = knowledge()["scoring"]
    now = model.now
    z = model.planning_years
    artefact_roles = roles(a)
    confidentiality = CONFIDENTIALITY in artefact_roles
    quantum = a.quantum or "unknown"
    classical = a.classical or "unknown"

    # Impact: what the system is worth to the organisation.
    crit = s["impact"]["criticality"].get(system.criticality, 0.55)
    expo = s["impact"]["exposure"].get(system.exposure, 0.75)
    cls = s["impact"]["classification"].get(system.classification, 0.75) if confidentiality else 1.0
    impact_value = round(crit * expo * cls, 4)

    # Mosca for this artefact.
    effort_key, y = migration_effort(a)
    x, x_basis = lifetime_years(a, artefact_roles, system)
    exposure_years = x + y - z
    probability = model.probability_by(x + y)
    mosca_status = "exposed" if exposure_years > 0 else ("watch" if exposure_years > -2 else "clear")

    # Likelihood components.
    drivers: list[str] = []
    classical_l = float(s["classical_likelihood"].get(classical, 0.0))
    if a.kind == "library":
        library = s["library"]
        pqc = a.properties.get("pqc") or {}
        classical_l = max(classical_l, library["end_of_life"] if (a.properties.get("eol") or {}).get("reached") else 0.0,
                          library["abandoned"] if a.properties.get("status") == "abandoned" else 0.0)
        severity = library["no_pqc"] if pqc.get("capable") is False else (library["pqc_unknown"] if pqc.get("capable") is None else 0.0)
    elif a.kind == "hardware":
        severity = s["hardware_quantum"]
    else:
        severity = float(s["quantum_severity"].get(quantum, 0.2))
    quantum_l = severity * probability

    results = policies.evaluate(a, system, now)
    nist = [r for r in results if r.framework in ("nist-ir-8547", "nist-sp-800-131a")]
    disallowed = [r.disallowed_from for r in nist if r.disallowed_from is not None]
    upcoming = [d for r in nist for d in (r.deprecated_from, r.disallowed_from) if d is not None and d > now]
    deprecated_now = any(r.deprecated_from is not None and r.deprecated_from <= now for r in nist)
    nearest = min(upcoming) if upcoming else None
    if any(d <= now for d in disallowed):
        policy_l, nearest = 1.0, max(d for d in disallowed if d <= now)
    else:
        policy_l = policy_pressure(nearest - now - y) if nearest is not None else 0.0
        if deprecated_now:
            policy_l = max(policy_l, 0.5)  # still permitted, but on borrowed time

    components = {"classical": classical_l, "quantum": quantum_l, "policy": policy_l}
    driver = max(components, key=components.get)
    likelihood_value = round(max(components.values()), 4)
    score = int(round(100 * impact_value * likelihood_value))

    # Harvest now, decrypt later.
    harvestable = confidentiality and quantum == "vulnerable" and a.kind not in ("library", "hardware")
    reach = {"external": "internet", "partner": "partner", "internal": "insider", "isolated": "isolated"}.get(system.exposure, "insider")
    hndl_exposed = harvestable and reach != "isolated" and exposure_years > 0
    band = band_for(score)
    if hndl_exposed and reach in ("internet", "partner") and band in ("medium", "low", "none"):
        band = "high"  # recorded traffic from an exposed system outlives the horizon: never below high
        drivers.append("Harvest now, decrypt later: traffic recorded today outlives the planning horizon.")

    if classical_l > 0 and driver == "classical" and a.kind != "library":
        drivers.append("Attackable today, without a quantum computer." if classical in ("broken", "weak") else "Legacy strength: plan its replacement.")
    if quantum_l > 0 and (driver == "quantum" or quantum_l >= 0.3):
        drivers.append(f"{probability:.0%} chance a CRQC exists within X + Y = {x + y:.1f} years.")
    if policy_l >= 0.3 and nearest is not None:
        if nearest <= now:
            drivers.append("Already outside NIST rules (SP 800-131A or IR 8547).")
        else:
            drivers.append(f"NIST deadline at the end of {int(nearest) - 1}, {nearest - now:.1f} years away; migrating it takes {y:g} years.")
    if a.kind == "library" and (a.properties.get("eol") or {}).get("reached"):
        drivers.append("End of life: no security fixes.")

    # Time machine: the years this artefact's state changes.
    planning_year = model.planning_year
    vulnerable = quantum == "vulnerable" or (a.kind == "hardware") or (a.kind == "library" and (a.properties.get("pqc") or {}).get("capable") is False)
    at_risk = now if (vulnerable or quantum in ("weakened", "unknown") or classical in ("legacy", "weak", "broken")) else None
    exposed = None
    if vulnerable:
        exposed = max(now, planning_year - (x if confidentiality else y))
    broken_candidates = list(disallowed)
    if vulnerable:
        broken_candidates.append(planning_year)
    if classical in ("broken", "weak"):
        broken_candidates.append(now)
    broken = max(now, min(broken_candidates)) if broken_candidates else None
    if at_risk is None and exposed is None and broken is not None:
        at_risk = broken

    classification = {
        "type": a.kind,
        "role": sorted(artefact_roles)[0] if len(artefact_roles) == 1 else "+".join(sorted(artefact_roles)),
        "lifetime": lifetime_band(x),
        "criticality": system.criticality,
        "mosca": "not-affected" if not vulnerable and quantum not in ("weakened", "unknown") else mosca_status,
    }

    return Risk(
        artefact_id=a.id,
        system_id=system.id,
        score=score,
        band=band,
        roles=sorted(artefact_roles),
        impact={"value": impact_value, "criticality": crit, "exposure": expo, "classification": cls if confidentiality else None,
                "bucket": bucket(impact_value, s["impact_buckets"])},
        likelihood={"value": likelihood_value, "driver": driver, "classical": round(classical_l, 4), "quantum": round(quantum_l, 4),
                    "quantum_severity": severity, "policy": round(policy_l, 4), "policy_deadline": nearest,
                    "bucket": bucket(likelihood_value, s["likelihood_buckets"])},
        mosca={"x": round(x, 2), "y": y, "z": round(z, 3), "exposure_years": round(exposure_years, 3), "status": mosca_status,
               "probability": round(probability, 5), "complete_by": round(now + z - x, 3), "start_by": round(now + z - x - y, 3)},
        migration={"key": effort_key, "years": y, **{k: v for k, v in knowledge()["migration"][effort_key].items() if k != "years"}},
        lifetime={"years": round(x, 2), "basis": x_basis, "band": lifetime_band(x)},
        hndl={"applies": harvestable, "reach": reach if harvestable else None, "exposed": hndl_exposed},
        classification=classification,
        timeline={"at_risk": _round(at_risk), "exposed": _round(exposed), "broken": _round(broken)},
        drivers=drivers,
        policies=results,
    )


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def estimated_system_migration(risks: list[Risk]) -> float | None:
    """Mosca's Y refined from discovery: the longest artefact migration, plus
    coordination time that grows with the number of vulnerable artefacts."""
    efforts = [r.migration["years"] for r in risks if r.classification["mosca"] != "not-affected"]
    if not efforts:
        return None
    return round(max(efforts) + 0.15 * math.log2(1 + len(efforts)), 2)
