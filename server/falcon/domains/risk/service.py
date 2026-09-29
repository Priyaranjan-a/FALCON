"""Quantum risk intelligence over the live inventory.

Risk is computed on read from the current artefacts, the systems register and
the organisation's threat model, so it always reflects the latest scan and any
change to the threat model or to a system's shelf-life, migration time or
criticality. Nothing here is stored.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...kernel.problems import not_found
from ...risk import policies as policy_rules
from ...risk.facts import ArtefactFacts, SystemFacts, knowledge
from ...risk.model import Risk, assess, estimated_system_migration
from ..discovery.consolidate import latest_scan_ids
from ..discovery.models import Artefact, Occurrence
from ..horizon.model import ThreatModel, format_decimal_year
from ..organisation.service import require_organisation, threat_model
from ..systems.models import System

BAND_ORDER = ["critical", "high", "medium", "low", "none"]
BAND_RANK = {b: i for i, b in enumerate(BAND_ORDER)}
KIND_ORDER = ["algorithm", "key", "certificate", "protocol", "library", "hardware", "cloud_service"]


@dataclass
class Assessed:
    artefact: Artefact
    facts: ArtefactFacts
    system: SystemFacts
    risk: Risk


def _system_facts(system: System) -> SystemFacts:
    return SystemFacts(system.id, system.code, system.name, system.kind, system.criticality, system.exposure,
                       system.data_classification, float(system.data_shelf_life_years), float(system.migration_years))


def assess_inventory(db: Session, *, system_id: str | None = None, artefact_id: str | None = None) -> tuple[ThreatModel, dict[str, SystemFacts], list[Assessed]]:
    model = threat_model(require_organisation(db))
    stmt = select(System).where(System.lifecycle != "retired")
    if system_id:
        stmt = stmt.where(System.id == system_id)
    systems = {s.id: _system_facts(s) for s in db.scalars(stmt).all()}

    query = select(Artefact).where(Artefact.status == "active", Artefact.system_id.in_(list(systems)))
    if artefact_id:
        query = select(Artefact).where(Artefact.id == artefact_id)
    artefacts = db.scalars(query).all()
    if not artefacts:
        return model, systems, []

    # How and where each artefact was found, from the latest scan of every source.
    scan_ids = {sid for s in {a.system_id for a in artefacts} for sid in latest_scan_ids(db, s)}
    functions: dict[str, set[str]] = defaultdict(set)
    detectors: dict[str, set[str]] = defaultdict(set)
    rows = db.execute(
        select(Occurrence.artefact_id, Occurrence.function, Occurrence.detector)
        .where(Occurrence.artefact_id.in_([a.id for a in artefacts]), Occurrence.scan_id.in_(scan_ids or {""}))
        .group_by(Occurrence.artefact_id, Occurrence.function, Occurrence.detector)
    ).all()
    for artefact_ref, function, detector in rows:
        if function:
            functions[artefact_ref].add(function)
        detectors[artefact_ref].add(detector)

    out: list[Assessed] = []
    for a in artefacts:
        system = systems.get(a.system_id)
        if system is None:
            owner = db.get(System, a.system_id)
            if owner is None:
                continue
            system = systems[a.system_id] = _system_facts(owner)
        facts = ArtefactFacts(
            id=a.id, system_id=a.system_id, kind=a.kind, name=a.name, family=a.family, quantum=a.quantum, classical=a.classical,
            primitive=a.primitive, identity=a.identity or {}, properties=a.properties or {}, status=a.status,
            functions=frozenset(functions.get(a.id, ())), detectors=frozenset(detectors.get(a.id, ())),
        )
        out.append(Assessed(a, facts, system, assess(facts, system, model)))
    return model, systems, out


# ------------------------------------------------------------------ payloads

def _model_payload(model: ThreatModel) -> dict[str, Any]:
    return {"now": round(model.now, 4), "planning_years": round(model.planning_years, 3), "planning_year": round(model.planning_year, 3),
            "planning_label": format_decimal_year(model.planning_year), "tolerance": model.tolerance, "scenario": model.scenario}


def row_payload(item: Assessed, model: ThreatModel) -> dict[str, Any]:
    a, r, s = item.artefact, item.risk, item.system
    return {
        "id": a.id, "name": a.name, "kind": a.kind, "family": a.family, "quantum": a.quantum, "classical": a.classical,
        "system": {"id": s.id, "code": s.code, "name": s.name, "criticality": s.criticality},
        "score": r.score, "band": r.band, "roles": r.roles,
        "lifetime": r.lifetime, "migration": {"key": r.migration["key"], "label": r.migration["label"], "years": r.migration["years"]},
        "mosca": r.mosca, "hndl": r.hndl, "classification": r.classification,
        "likelihood": {"value": r.likelihood["value"], "driver": r.likelihood["driver"], "bucket": r.likelihood["bucket"]},
        "impact": {"value": r.impact["value"], "bucket": r.impact["bucket"]},
        "driver": r.drivers[0] if r.drivers else None,
        "policy": {p.framework: p.status_at(model.now) for p in r.policies},
        "timeline": r.timeline,
    }


def detail(db: Session, artefact_id: str) -> dict[str, Any]:
    if db.get(Artefact, artefact_id) is None:
        raise not_found("Artefact")
    model, _, items = assess_inventory(db, artefact_id=artefact_id)
    if not items:
        raise not_found("Artefact")
    item = items[0]
    r = item.risk
    frameworks = policy_rules.frameworks()
    return {
        **row_payload(item, model),
        "model": _model_payload(model),
        "impact": r.impact,
        "likelihood": r.likelihood,
        "migration": r.migration,
        "drivers": r.drivers,
        "policies": [{**p.as_dict(model.now), **frameworks[p.framework]} for p in r.policies],
    }


def _sort_key(sort: str):
    return {
        "score": lambda i: (-i.risk.score, BAND_RANK[i.risk.band], i.artefact.name),
        "exposure": lambda i: (-i.risk.mosca["exposure_years"], -i.risk.score),
        "probability": lambda i: (-i.risk.mosca["probability"], -i.risk.score),
        "name": lambda i: (i.artefact.name.lower(),),
    }.get(sort, lambda i: (-i.risk.score, i.artefact.name))


def register(db: Session, *, system_id: str | None, band: list[str] | None, kind: list[str] | None, role: str | None,
             hndl: bool | None, lifetime: str | None, framework: str | None, policy_status: list[str] | None,
             likelihood: str | None, impact: str | None, q: str | None, sort: str, limit: int, offset: int) -> dict[str, Any]:
    model, _, items = assess_inventory(db, system_id=system_id)
    def keep(i: Assessed) -> bool:
        r = i.risk
        if band and r.band not in band:
            return False
        if kind and i.artefact.kind not in kind:
            return False
        if role and role not in r.roles:
            return False
        if hndl is not None and r.hndl["exposed"] != hndl:
            return False
        if lifetime and r.lifetime["band"] != lifetime:
            return False
        if likelihood and r.likelihood["bucket"] != likelihood:
            return False
        if impact and r.impact["bucket"] != impact:
            return False
        if framework:
            status = next((p.status_at(model.now) for p in r.policies if p.framework == framework), None)
            if policy_status and status not in policy_status:
                return False
        if q and q.lower() not in i.artefact.name.lower():
            return False
        return True
    rows = sorted((i for i in items if keep(i)), key=_sort_key(sort))
    return {"items": [row_payload(i, model) for i in rows[offset: offset + limit]], "total": len(rows), "model": _model_payload(model)}


def summary(db: Session, *, system_id: str | None = None) -> dict[str, Any]:
    model, systems, items = assess_inventory(db, system_id=system_id)
    s = knowledge()["scoring"]
    bands = Counter(i.risk.band for i in items)

    matrix: dict[tuple[str, str], list[Assessed]] = defaultdict(list)
    for i in items:
        if i.risk.score > 0:
            matrix[(i.risk.likelihood["bucket"], i.risk.impact["bucket"])].append(i)

    classification: dict[str, Counter] = defaultdict(Counter)
    classification_risk: dict[tuple[str, str], int] = defaultdict(int)
    for i in items:
        classification[i.artefact.kind][i.risk.lifetime["band"]] += 1
        key = (i.artefact.kind, i.risk.lifetime["band"])
        classification_risk[key] = max(classification_risk[key], i.risk.score)

    # Mosca plane: artefacts at (X, Y), grouped where they coincide.
    plane: dict[tuple[float, float], list[Assessed]] = defaultdict(list)
    for i in items:
        if i.risk.classification["mosca"] != "not-affected":
            plane[(round(i.risk.mosca["x"] * 2) / 2, i.risk.mosca["y"])].append(i)

    by_system: dict[str, list[Assessed]] = defaultdict(list)
    for i in items:
        by_system[i.system.id].append(i)
    system_rows = []
    for sid, facts in systems.items():
        group = by_system.get(sid, [])
        worst = min((i.risk.band for i in group), key=lambda b: BAND_RANK[b], default="none")
        system_rows.append({
            "id": sid, "code": facts.code, "name": facts.name, "criticality": facts.criticality, "exposure": facts.exposure,
            "artefacts": len(group), "score": max((i.risk.score for i in group), default=0), "band": worst,
            "bands": dict(Counter(i.risk.band for i in group)),
            "hndl_exposed": sum(1 for i in group if i.risk.hndl["exposed"]),
            "x": facts.shelf_life_years, "register_y": facts.migration_years,
            "estimated_y": estimated_system_migration([i.risk for i in group]),
        })
    system_rows.sort(key=lambda r: (BAND_RANK[r["band"]], -r["score"], r["code"]))

    compliance: dict[str, Counter] = defaultdict(Counter)
    for i in items:
        for p in i.risk.policies:
            compliance[p.framework][p.status_at(model.now)] += 1

    top = sorted((i for i in items if i.risk.score > 0), key=_sort_key("score"))[:8]
    return {
        "model": _model_payload(model),
        "total": len(items),
        "assessed": sum(1 for i in items if i.risk.classification["mosca"] != "not-affected"),
        "bands": {b: bands.get(b, 0) for b in BAND_ORDER},
        "hndl": {
            "applies": sum(1 for i in items if i.risk.hndl["applies"]),
            "exposed": sum(1 for i in items if i.risk.hndl["exposed"]),
            "systems": len({i.system.id for i in items if i.risk.hndl["exposed"]}),
            "internet": sum(1 for i in items if i.risk.hndl["exposed"] and i.risk.hndl["reach"] == "internet"),
        },
        "matrix": {
            "likelihood": [{"key": b["key"], "label": b["label"]} for b in s["likelihood_buckets"]],
            "impact": [{"key": b["key"], "label": b["label"]} for b in s["impact_buckets"]],
            "cells": [{"likelihood": lk, "impact": ik, "count": len(group), "score": max(i.risk.score for i in group),
                       "band": min((i.risk.band for i in group), key=lambda b: BAND_RANK[b])}
                      for (lk, ik), group in matrix.items()],
        },
        "classification": {
            "lifetimes": [{"key": b["key"], "label": b["label"]} for b in s["lifetime_bands"]],
            "rows": [{"kind": k, "cells": {lb: {"count": n, "score": classification_risk[(k, lb)]} for lb, n in classification[k].items()}}
                     for k in KIND_ORDER if k in classification],
            "roles": dict(Counter(role for i in items for role in i.risk.roles)),
            "mosca": dict(Counter(i.risk.classification["mosca"] for i in items)),
        },
        "plane": [{"x": x, "y": y, "count": len(group),
                   "band": min((i.risk.band for i in group), key=lambda b: BAND_RANK[b]),
                   "exposure": round(x + y - model.planning_years, 2),
                   "kinds": dict(Counter(i.artefact.kind for i in group)),
                   "sample": [i.artefact.name for i in sorted(group, key=_sort_key("score"))[:4]]}
                  for (x, y), group in plane.items()],
        "systems": system_rows,
        "compliance": {fw: dict(c) for fw, c in compliance.items()},
        "top": [row_payload(i, model) for i in top],
    }


def timeline(db: Session, *, system_id: str | None, until: int) -> dict[str, Any]:
    model, systems, items = assess_inventory(db, system_id=system_id)
    now = model.now
    frameworks = policy_rules.frameworks()
    events: list[dict[str, Any]] = []

    def add(year: float, kind: str, title: str, detail: str, count: int | None = None, framework: str | None = None) -> None:
        if now <= year <= until + 1:
            events.append({"year": round(year, 3), "kind": kind, "title": title, "detail": detail, "count": count, "framework": framework})

    add(model.planning_year, "horizon", "Planning horizon (Z)",
        f"A {model.tolerance:.0%} chance a cryptographically relevant quantum computer exists.")
    for q, label in ((0.1, "10%"), (0.5, "50%"), (0.9, "90%")):
        add(now + model.quantile_years(q), "probability", f"{label} chance of a CRQC", "Under the organisation's threat model.")

    # Policy dates, with how many artefacts each one catches.
    by_date: dict[tuple[str, float, str], int] = Counter()
    for i in items:
        for p in i.risk.policies:
            if p.deprecated_from and p.deprecated_from > now:
                by_date[(p.framework, p.deprecated_from, "deprecated")] += 1
            if p.disallowed_from and p.disallowed_from > now:
                by_date[(p.framework, p.disallowed_from, "disallowed")] += 1
    for (fw, year, what), count in sorted(by_date.items(), key=lambda kv: kv[0][1]):
        noun = f"{count} artefact{'s' if count != 1 else ''}"
        if what == "deprecated":
            title = f"{frameworks[fw]['name']}: {noun} deprecated"
        elif fw == "cnsa-2.0":
            title = f"{frameworks[fw]['name']}: {noun} must be replaced"
        elif fw == "eu-pqc-roadmap":
            title = f"{frameworks[fw]['name']}: {noun} due for migration"
        else:
            title = f"{frameworks[fw]['name']}: {noun} disallowed"
        add(year, "policy", title, frameworks[fw]["summary"], count, fw)

    expiries: Counter[int] = Counter()
    for i in items:
        if i.artefact.kind == "certificate":
            not_after = (i.artefact.properties or {}).get("not_after")
            if isinstance(not_after, str) and not_after[:4].isdigit():
                expiries[int(not_after[:4])] += 1
        if i.artefact.kind == "library":
            eol = (i.artefact.properties or {}).get("eol") or {}
            if eol.get("date") and not eol.get("reached"):
                add(int(eol["date"][:4]) + (int(eol["date"][5:7]) - 1) / 12, "library", f"{i.artefact.name} reaches end of life",
                    "No further security fixes from the maintainers.")
    for year, count in sorted(expiries.items()):
        if year >= int(now):
            add(year + 0.5, "certificate", f"{count} certificate{'s expire' if count != 1 else ' expires'}", "Re-issue with post-quantum or hybrid keys when possible.", count)
    events.sort(key=lambda e: e["year"])

    return {
        "model": _model_payload(model),
        "until": until,
        "curve": [p for p in model.curve(until_year=until + 1, points_per_year=4) if p["year"] >= now - 0.25],
        "systems": [{"id": s.id, "code": s.code, "name": s.name, "criticality": s.criticality} for s in systems.values()],
        "artefacts": [{
            "id": i.artefact.id, "name": i.artefact.name, "kind": i.artefact.kind, "system_id": i.system.id, "band": i.risk.band,
            "score": i.risk.score, "t": i.risk.timeline,
            "policy": {p.framework: p.disallowed_from for p in i.risk.policies if p.disallowed_from is not None},
        } for i in sorted(items, key=lambda i: (i.system.code, BAND_RANK[i.risk.band], -i.risk.score))],
        "events": events,
    }


def policy_overview(db: Session) -> dict[str, Any]:
    model, _, items = assess_inventory(db)
    frameworks = policy_rules.frameworks()
    checkpoints = [int(model.now), 2030, 2031, 2033, 2034, 2036]
    out = []
    for fw, meta in frameworks.items():
        results = [p for i in items for p in i.risk.policies if p.framework == fw]
        at = {str(year): dict(Counter(p.status_at(year + 0.5 if year == int(model.now) else float(year)) for p in results))
              for year in sorted(set(checkpoints))}
        dates = sorted({d for p in results for d in (p.deprecated_from, p.disallowed_from) if d and d > model.now})
        out.append({"id": fw, **meta, "now": dict(Counter(p.status_at(model.now) for p in results)), "at": at,
                    "dates": [round(d, 3) for d in dates]})
    return {"model": _model_payload(model), "frameworks": out, "statuses": policy_rules.ORDER}
