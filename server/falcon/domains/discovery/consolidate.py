"""Turns a stream of findings from the scan worker into the inventory.

* An artefact is upserted by fingerprint within its system, so the same
  certificate or algorithm keeps one identity and its history across scans.
* Every finding becomes an occurrence (evidence) for this scan; related
  artefacts (a certificate's key, a cloud key's algorithm) get their own
  occurrence and a link.
* When a scan finishes, each artefact of the system is marked ``active`` if
  the latest successful scan of any source still sees it, ``resolved`` if not.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from ...kernel.database import utcnow
from .models import Artefact, ArtefactLink, Occurrence, Scan, Source


def classify(kind: str, identity: dict[str, Any], properties: dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
    """Returns (family, quantum status, classical status, primitive)."""
    assessment = properties.get("assessment") or {}
    quantum, classical, primitive = assessment.get("quantum"), assessment.get("classical"), assessment.get("primitive")
    if kind == "algorithm":
        family = identity.get("algorithm")
    elif kind in ("key", "certificate"):
        family = (properties.get("key_algorithm") or "").split("-")[0].split(" ")[0] or None
    elif kind == "protocol":
        family = identity.get("protocol")
    elif kind == "library":
        family = identity.get("library")
        quantum = classical = None
        primitive = "library"
    elif kind == "hardware":
        family = identity.get("type")
        primitive = "hardware"
    else:  # cloud_service
        family = f"{identity.get('provider')}:{identity.get('service')}"
        primitive = "key-management"
    return family, quantum, classical, primitive


class Consolidator:
    def __init__(self, session_factory: sessionmaker[Session], scan_id: str, system_id: str, source_id: str) -> None:
        self.session_factory = session_factory
        self.scan_id = scan_id
        self.system_id = system_id
        self.source_id = source_id
        self.ids: dict[str, str] = {}
        self.new_ids: set[str] = set()
        self.seen_occurrences: set[tuple[str, str, int | None, str | None]] = set()
        self.seen_links: set[tuple[str, str, str]] = set()
        self.seen_in_scan: set[str] = set()
        self.evidence = 0
        with session_factory() as db:
            for fingerprint, artefact_id in db.execute(
                select(Artefact.fingerprint, Artefact.id).where(Artefact.system_id == system_id)
            ):
                self.ids[fingerprint] = artefact_id

    def _upsert(self, db: Session, fingerprint: str, kind: str, identity: dict, name: str, properties: dict,
                confidence: float, related_assessment: dict | None = None) -> str:
        now = utcnow()
        family, quantum, classical, primitive = classify(kind, identity, properties)
        if kind == "cloud_service" and related_assessment:
            quantum, classical = related_assessment.get("quantum"), related_assessment.get("classical")
        artefact_id = self.ids.get(fingerprint)
        if artefact_id:
            artefact = db.get(Artefact, artefact_id)
            if artefact is not None:
                artefact.name = name[:300]
                artefact.properties = {**(artefact.properties or {}), **properties}
                artefact.quantum = quantum or artefact.quantum
                artefact.classical = classical or artefact.classical
                artefact.confidence = max(artefact.confidence, confidence)
                artefact.last_seen_at = now
                artefact.last_scan_id = self.scan_id
                artefact.status = "active"
                return artefact_id
        artefact = Artefact(
            system_id=self.system_id, fingerprint=fingerprint, kind=kind, name=name[:300], family=family,
            identity=identity, properties=properties, quantum=quantum, classical=classical, primitive=primitive,
            confidence=confidence, status="active", first_seen_at=now, last_seen_at=now,
            first_scan_id=self.scan_id, last_scan_id=self.scan_id,
        )
        db.add(artefact)
        db.flush()
        self.ids[fingerprint] = artefact.id
        self.new_ids.add(artefact.id)
        return artefact.id

    def _occurrence(self, db: Session, artefact_id: str, message: dict, via: str | None) -> None:
        evidence = message["evidence"]
        key = (artefact_id, evidence["path"], evidence.get("line"), via)
        if key in self.seen_occurrences:
            return
        self.seen_occurrences.add(key)
        self.evidence += 1
        db.add(Occurrence(
            artefact_id=artefact_id, scan_id=self.scan_id, source_id=self.source_id, path=evidence["path"][:2000],
            line=evidence.get("line"), col=evidence.get("column"), snippet=evidence.get("snippet"),
            detector=message["detector"][:40], rule=message["rule"][:80], confidence=message["confidence"],
            function=(message.get("function") or None) and message["function"][:40], via=via,
        ))

    def ingest(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Persist a batch; returns summaries of artefacts first seen in this batch."""
        discovered: list[dict[str, Any]] = []
        with self.session_factory() as db:
            for message in messages:
                before = len(self.new_ids)
                related_assessment = next((r["properties"].get("assessment") for r in message.get("related", [])
                                           if r["kind"] == "algorithm" and r["properties"].get("assessment")), None)
                artefact_id = self._upsert(db, message["fingerprint"], message["kind"], message["identity"], message["name"],
                                           message.get("properties") or {}, message["confidence"], related_assessment)
                self._occurrence(db, artefact_id, message, None)
                if artefact_id not in self.seen_in_scan:
                    # First sighting in this scan; "new" means the system had never seen it.
                    self.seen_in_scan.add(artefact_id)
                    props = message.get("properties") or {}
                    discovered.append({
                        "id": artefact_id, "kind": message["kind"], "name": message["name"], "new": len(self.new_ids) > before,
                        "quantum": (props.get("assessment") or {}).get("quantum") or (related_assessment or {}).get("quantum"),
                        "path": message["evidence"]["path"], "line": message["evidence"].get("line"),
                    })
                for relation in message.get("related", []):
                    related_id = self._upsert(db, relation["fingerprint"], relation["kind"], relation["identity"], relation["name"],
                                              relation.get("properties") or {}, message["confidence"])
                    self._occurrence(db, related_id, message, relation["relation"])
                    link = (artefact_id, related_id, relation["relation"])
                    if link not in self.seen_links:
                        self.seen_links.add(link)
                        exists = db.scalar(select(ArtefactLink.id).where(
                            ArtefactLink.from_id == artefact_id, ArtefactLink.to_id == related_id, ArtefactLink.relation == relation["relation"]))
                        if not exists:
                            db.add(ArtefactLink(from_id=artefact_id, to_id=related_id, relation=relation["relation"]))
            db.commit()
        return discovered

    def finalize(self, db: Session) -> tuple[int, int]:
        """Returns (distinct artefacts in this scan, artefacts new to the system)."""
        counts = dict(db.execute(
            select(Occurrence.artefact_id, func.count()).where(Occurrence.scan_id == self.scan_id).group_by(Occurrence.artefact_id)
        ).all())
        for artefact_id, count in counts.items():
            db.execute(update(Artefact).where(Artefact.id == artefact_id).values(occurrence_count=count))
        recompute_status(db, self.system_id)
        return len(counts), len(self.new_ids)


def latest_scan_ids(db: Session, system_id: str) -> list[str]:
    """The most recent successful scan of each source in the system."""
    rows = db.execute(
        select(Scan.source_id, Scan.id, Scan.finished_at).join(Source, Source.id == Scan.source_id)
        .where(Scan.system_id == system_id, Scan.status == "succeeded").order_by(Scan.finished_at.desc())
    ).all()
    latest: dict[str, str] = {}
    for source_id, scan_id, _ in rows:
        latest.setdefault(source_id, scan_id)
    return list(latest.values())


def recompute_status(db: Session, system_id: str) -> None:
    scan_ids = latest_scan_ids(db, system_id)
    current = set(db.scalars(select(Occurrence.artefact_id).where(Occurrence.scan_id.in_(scan_ids)).distinct()).all()) if scan_ids else set()
    for artefact_id, status in db.execute(select(Artefact.id, Artefact.status).where(Artefact.system_id == system_id)).all():
        wanted = "active" if artefact_id in current else "resolved"
        if wanted != status:
            db.execute(update(Artefact).where(Artefact.id == artefact_id).values(status=wanted))
    # Artefacts with no remaining evidence at all (their sources were removed) are dropped.
    orphans = select(Artefact.id).where(Artefact.system_id == system_id, ~Artefact.id.in_(select(Occurrence.artefact_id).distinct()))
    for artefact_id in db.scalars(orphans).all():
        db.delete(db.get(Artefact, artefact_id))
