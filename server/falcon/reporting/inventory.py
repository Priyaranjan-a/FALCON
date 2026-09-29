"""The assessed inventory every report format is written from.

A :class:`Report` is built either from the platform database (the live
inventory with its systems and threat model) or offline from a scan's
findings (the ``falcon scan`` command line). The writers never see where it
came from, so a CBOM from a CI pipeline and one from the console read alike.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..domains.discovery.consolidate import classify
from ..domains.horizon.model import ThreatModel
from ..migration.recommend import recommend
from ..risk.facts import ArtefactFacts, SystemFacts
from ..risk.model import Risk, assess

TOOL_NAME = "FALCON"
TOOL_VERSION = "1.0.0"
TOOL_VENDOR = "FALCON"
TOOL_URI = "https://falcon.local/"


@dataclass
class Occ:
    path: str
    line: int | None
    column: int | None
    detector: str
    rule: str
    function: str | None
    via: str | None = None


@dataclass
class Item:
    facts: ArtefactFacts
    fingerprint: str
    system: SystemFacts
    risk: Risk
    occurrences: list[Occ] = field(default_factory=list)
    occurrence_total: int = 0
    confidence: float = 0.0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    recommendation: dict[str, Any] | None = None

    @property
    def id(self) -> str:
        return self.facts.id

    @property
    def ref(self) -> str:
        """Stable across scans and exports: the system and the artefact's fingerprint."""
        return f"crypto/{self.system.code}/{self.fingerprint}"


@dataclass
class Report:
    organisation: str
    scope: str
    model: ThreatModel
    items: list[Item]
    links: list[tuple[str, str, str]]  # (from artefact id, to artefact id, relation)
    systems: dict[str, SystemFacts]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0))
    origin: dict[str, Any] = field(default_factory=dict)

    def by_id(self) -> dict[str, Item]:
        return {i.id: i for i in self.items}


def _functions(occurrences: list[Occ]) -> frozenset[str]:
    return frozenset(o.function for o in occurrences if o.function)


# ------------------------------------------------------------------- database

def from_database(db, *, system_id: str | None = None, occurrence_limit: int = 25) -> Report:
    from sqlalchemy import func, select

    from ..domains.discovery.consolidate import latest_scan_ids
    from ..domains.discovery.models import ArtefactLink, Occurrence
    from ..domains.organisation.service import require_organisation
    from ..domains.risk.service import assess_inventory
    from ..migration import bench

    org = require_organisation(db)
    model, systems, assessed = assess_inventory(db, system_id=system_id)
    ids = [a.artefact.id for a in assessed]
    scan_ids = {sid for s in {a.system.id for a in assessed} for sid in latest_scan_ids(db, s)} or {""}

    evidence: dict[str, list[Occ]] = defaultdict(list)
    totals: dict[str, int] = {}
    if ids:
        totals = dict(db.execute(
            select(Occurrence.artefact_id, func.count()).where(Occurrence.artefact_id.in_(ids), Occurrence.scan_id.in_(scan_ids))
            .group_by(Occurrence.artefact_id)
        ).all())
        rows = db.execute(
            select(Occurrence.artefact_id, Occurrence.path, Occurrence.line, Occurrence.col, Occurrence.detector,
                   Occurrence.rule, Occurrence.function, Occurrence.via)
            .where(Occurrence.artefact_id.in_(ids), Occurrence.scan_id.in_(scan_ids))
            .order_by(Occurrence.artefact_id, Occurrence.path, Occurrence.line)
        ).all()
        for artefact_id, path, line, col, detector, rule, function, via in rows:
            bucket = evidence[artefact_id]
            if len(bucket) < occurrence_limit:
                bucket.append(Occ(path, line, col, detector, rule, function, via))

    benchmarks = bench.latest()
    items = [
        Item(
            facts=a.facts, fingerprint=a.artefact.fingerprint, system=a.system, risk=a.risk,
            occurrences=evidence.get(a.artefact.id, []), occurrence_total=totals.get(a.artefact.id, 0),
            confidence=a.artefact.confidence, first_seen=a.artefact.first_seen_at, last_seen=a.artefact.last_seen_at,
            recommendation=recommend(a.facts, a.risk, a.system, benchmarks),
        )
        for a in assessed
    ]
    id_set = set(ids)
    links = [
        (f, t, r) for f, t, r in db.execute(
            select(ArtefactLink.from_id, ArtefactLink.to_id, ArtefactLink.relation).where(ArtefactLink.from_id.in_(ids or [""]))
        ).all() if t in id_set
    ]
    scope = systems[system_id].name if system_id and system_id in systems else "All systems"
    return Report(org.name, scope, model, items, links, systems, origin={"mode": "platform", "system_id": system_id})


# -------------------------------------------------------------------- offline

class OfflineInventory:
    """Consolidates finding messages in memory, the way the platform does in its database."""

    def __init__(self) -> None:
        self.artefacts: dict[str, dict[str, Any]] = {}
        self.evidence: dict[str, list[Occ]] = defaultdict(list)
        self.seen: set[tuple[str, str, int | None, str | None]] = set()
        self.links: set[tuple[str, str, str]] = set()

    def _upsert(self, fp: str, kind: str, identity: dict, name: str, properties: dict, confidence: float,
                related_assessment: dict | None = None) -> str:
        family, quantum, classical, primitive = classify(kind, identity, properties)
        if kind == "cloud_service" and related_assessment:
            quantum, classical = related_assessment.get("quantum"), related_assessment.get("classical")
        current = self.artefacts.get(fp)
        if current:
            current["properties"] = {**current["properties"], **properties}
            current["quantum"] = quantum or current["quantum"]
            current["classical"] = classical or current["classical"]
            current["confidence"] = max(current["confidence"], confidence)
        else:
            self.artefacts[fp] = {"kind": kind, "identity": identity, "name": name[:300], "properties": properties, "family": family,
                                  "quantum": quantum, "classical": classical, "primitive": primitive, "confidence": confidence}
        return fp

    def _occurrence(self, fp: str, message: dict, via: str | None) -> None:
        ev = message["evidence"]
        key = (fp, ev["path"], ev.get("line"), via)
        if key in self.seen:
            return
        self.seen.add(key)
        self.evidence[fp].append(Occ(ev["path"], ev.get("line"), ev.get("column"), message["detector"], message["rule"],
                                     message.get("function") or None, via))

    def ingest(self, messages: list[dict[str, Any]]) -> None:
        for m in messages:
            related_assessment = next((r["properties"].get("assessment") for r in m.get("related", [])
                                       if r["kind"] == "algorithm" and r["properties"].get("assessment")), None)
            fp = self._upsert(m["fingerprint"], m["kind"], m["identity"], m["name"], m.get("properties") or {}, m["confidence"], related_assessment)
            self._occurrence(fp, m, None)
            for r in m.get("related", []):
                rid = self._upsert(r["fingerprint"], r["kind"], r["identity"], r["name"], r.get("properties") or {}, m["confidence"])
                self._occurrence(rid, m, r["relation"])
                self.links.add((fp, rid, r["relation"]))

    def report(self, system: SystemFacts, model: ThreatModel, *, organisation: str, scope: str,
               origin: dict[str, Any] | None = None, occurrence_limit: int = 25) -> Report:
        items: list[Item] = []
        for fp, a in self.artefacts.items():
            occ = sorted(self.evidence.get(fp, []), key=lambda o: (o.path, o.line or 0))
            facts = ArtefactFacts(
                id=fp, system_id=system.id, kind=a["kind"], name=a["name"], family=a["family"], quantum=a["quantum"],
                classical=a["classical"], primitive=a["primitive"], identity=a["identity"], properties=a["properties"],
                functions=_functions(occ), detectors=frozenset(o.detector for o in occ),
            )
            risk = assess(facts, system, model)
            items.append(Item(facts, fp, system, risk, occ[:occurrence_limit], len(occ), a["confidence"],
                              recommendation=recommend(facts, risk, system, None)))
        items.sort(key=lambda i: (-i.risk.score, i.facts.kind, i.facts.name))
        return Report(organisation, scope, model, items, sorted(self.links), {system.id: system}, origin=origin or {"mode": "offline"})
