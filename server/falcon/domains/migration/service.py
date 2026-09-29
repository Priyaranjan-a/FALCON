"""PQC migration planning over the live inventory: recommendations, the
roadmap, the blast-radius graph and the benchmark lab."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from sqlalchemy.orm import Session

from ...kernel.problems import not_found
from ...migration import bench
from ...migration.plan import Item, schedule, wave_for
from ...migration.recommend import recommend
from ..discovery.models import Artefact
from ..risk.service import BAND_RANK, Assessed, _model_payload, assess_inventory, row_payload
from ..systems.models import System

VULNERABLE_FAMILIES = {"RSA", "DSA", "DH", "ECDH", "ECDSA", "EdDSA", "X25519", "X448", "ElGamal", "SM2", "3DES", "DES", "RC4", "MD5", "SHA-1"}


def _recommend(item: Assessed, benchmarks: dict[str, Any] | None) -> dict[str, Any]:
    return recommend(item.facts, item.risk, item.system, benchmarks)


def artefact_recommendation(db: Session, artefact_id: str) -> dict[str, Any]:
    if db.get(Artefact, artefact_id) is None:
        raise not_found("Artefact")
    model, _, items = assess_inventory(db, artefact_id=artefact_id)
    if not items:
        raise not_found("Artefact")
    return _recommend(items[0], bench.latest())


def plan(db: Session, *, system_id: str | None = None) -> dict[str, Any]:
    model, systems, items = assess_inventory(db, system_id=system_id)
    benchmarks = bench.latest()
    harvest_systems = {i.system.id for i in items if i.risk.hndl["exposed"]}
    work: list[Item] = []
    for i in items:
        row = row_payload(i, model)
        row["recommendation"] = _recommend(i, benchmarks)
        row["likelihood"] = i.risk.likelihood
        row["ca"] = bool((i.artefact.properties or {}).get("is_ca"))
        wave = wave_for(row, i.system.id in harvest_systems)
        if wave is None:
            continue
        rec = row["recommendation"]
        payload = {
            "id": i.artefact.id, "name": i.artefact.name, "kind": i.artefact.kind, "band": i.risk.band, "score": i.risk.score,
            "system": row["system"], "years": i.risk.migration["years"], "effort": i.risk.migration["label"],
            "action": rec["action"], "recommendation": rec["title"], "primary": rec["primary"]["name"] if rec.get("primary") else None,
        }
        work.append(Item(i.artefact.id, i.system.id, i.risk.band, i.risk.score, i.risk.migration["years"], wave, payload))

    system_rows = {sid: {"id": s.id, "code": s.code, "name": s.name, "criticality": s.criticality} for sid, s in systems.items()}
    roadmap = schedule(work, system_rows, model)
    actions = Counter(w.payload["action"] for w in work)
    primaries = Counter(w.payload["primary"] for w in work if w.payload["primary"])
    return {
        "model": _model_payload(model),
        **roadmap,
        "totals": {"artefacts": len(work), "effort_years": round(sum(w.years for w in work), 2), "systems": len({w.system_id for w in work}),
                   "actions": dict(actions), "targets": [{"name": n, "count": c} for n, c in primaries.most_common(8)]},
        "benchmarked": benchmarks is not None,
    }


def graph(db: Session) -> dict[str, Any]:
    """Blast radius: the algorithm families, libraries, certificates and keys each
    system depends on, and how many systems each one would take down with it."""
    model, systems, items = assess_inventory(db)
    nodes: dict[str, dict[str, Any]] = {}
    links: dict[tuple[str, str], dict[str, Any]] = {}

    def node_for(i: Assessed) -> tuple[str, str, str] | None:
        a = i.artefact
        if a.kind == "algorithm" and a.family in VULNERABLE_FAMILIES:
            return f"alg:{a.family}", a.family, "algorithm"
        if a.kind == "library":
            name = (a.properties or {}).get("library") or a.family or a.name
            return f"lib:{(a.identity or {}).get('library')}", name, "library"
        if a.kind in ("certificate", "key"):
            ident = next(iter((a.identity or {}).values()), None)
            return (f"{a.kind}:{ident}", a.name, a.kind) if ident else None
        if a.kind == "protocol" and i.risk.band != "none":
            return f"proto:{a.name}", a.name, "protocol"
        if a.kind in ("hardware", "cloud_service"):
            return f"{a.kind}:{a.name}", a.name, a.kind
        return None

    for i in items:
        key = node_for(i)
        if key is None:
            continue
        nid, label, kind = key
        node = nodes.setdefault(nid, {"id": nid, "label": label, "kind": kind, "systems": set(), "artefacts": 0, "band": "none", "score": 0, "hndl": 0, "sample": i.artefact.id})
        node["systems"].add(i.system.id)
        node["artefacts"] += 1
        node["hndl"] += int(i.risk.hndl["exposed"])
        if BAND_RANK[i.risk.band] < BAND_RANK[node["band"]]:
            node["band"] = i.risk.band
        node["score"] = max(node["score"], i.risk.score)
        link = links.setdefault((i.system.id, nid), {"system": i.system.id, "node": nid, "artefacts": 0, "band": "none"})
        link["artefacts"] += 1
        if BAND_RANK[i.risk.band] < BAND_RANK[link["band"]]:
            link["band"] = i.risk.band

    # Keep what matters: anything shared, or anything that carries risk.
    kept = {nid: n for nid, n in nodes.items() if len(n["systems"]) > 1 or n["band"] in ("critical", "high")}
    impact = {"critical": 1.0, "high": 0.8, "moderate": 0.55, "low": 0.3}
    out_nodes = []
    for n in kept.values():
        crit = [systems[s].criticality for s in n["systems"] if s in systems]
        out_nodes.append({**{k: v for k, v in n.items() if k != "systems"}, "systems": sorted(n["systems"]),
                          "radius": round(sum(impact.get(c, 0.5) for c in crit), 2), "mission_critical": sum(1 for c in crit if c == "critical")})
    out_nodes.sort(key=lambda n: (-n["radius"], BAND_RANK[n["band"]], n["label"]))
    used = {s for n in out_nodes for s in n["systems"]}
    return {
        "model": _model_payload(model),
        "systems": [{"id": s.id, "code": s.code, "name": s.name, "criticality": s.criticality, "exposure": s.exposure} for s in systems.values() if s.id in used],
        "nodes": out_nodes,
        "links": [l for (sid, nid), l in links.items() if nid in kept],
    }


def benchmarks() -> dict[str, Any] | None:
    return bench.latest()


def run_benchmarks() -> dict[str, Any]:
    return bench.run()


def system_names(db: Session) -> dict[str, str]:
    return {s.id: s.name for s in db.query(System).all()}
