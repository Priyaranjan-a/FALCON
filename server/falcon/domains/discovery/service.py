"""Discovery use-cases: sources, scans and inventory queries."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ...discovery import catalogue, workspace
from ...discovery.detectors.dependencies import knowledge_version
from ...discovery.endpoints import EndpointError, parse_endpoints
from ...discovery.engine import ENGINE_VERSION
from ...kernel import audit
from ...kernel.access import Principal
from ...kernel.database import utcnow
from ...kernel.problems import Problem, conflict, not_found
from ...settings import get_settings
from ..identity.service import actor_fields
from ..systems.models import System
from .consolidate import latest_scan_ids, recompute_status
from .models import Artefact, ArtefactLink, Occurrence, Scan, Source

SOURCE_KINDS = {
    "directory": "Folder",
    "archive": "Archive",
    "git": "Git repository",
    "image-archive": "Container image (saved tarball)",
    "image-registry": "Container image (registry)",
    "endpoint": "TLS endpoints",
}
ACTIVE = ("queued", "running")


# ---------------------------------------------------------------- capabilities

def capabilities() -> dict[str, Any]:
    settings = get_settings()
    git = shutil.which("git") is not None
    kinds = []
    for kind, label in SOURCE_KINDS.items():
        available, reason = True, None
        if kind == "git" and not git:
            available, reason = False, "Git is not installed on the FALCON server"
        if kind == "endpoint" and not settings.network_probes_allowed:
            available, reason = False, "Network probing is disabled (FALCON_ALLOW_NETWORK_PROBES)"
        if kind == "directory" and not settings.any_folder_allowed and not settings.scan_roots:
            available, reason = False, "No scan roots are configured (FALCON_SCAN_ROOTS)"
        kinds.append({"kind": kind, "label": label, "available": available, "reason": reason})
    return {
        "desktop": settings.desktop,
        "source_kinds": kinds,
        "scan_roots": [str(p) for p in settings.scan_roots],
        "any_folder": settings.any_folder_allowed,
        "upload_max_mb": settings.upload_max_mb,
        "engine_version": ENGINE_VERSION,
        "knowledge": {"algorithms": catalogue.version(), "libraries": knowledge_version()},
    }


# -------------------------------------------------------------------- sources

def _validate_path(locator: str, *, folder: bool) -> str:
    """A local folder (or, for archives on the same machine, a file) the server may read."""
    settings = get_settings()
    noun = "folder" if folder else "file"
    path = Path(locator.strip().strip("\"'")).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Problem(422, f"That {noun} does not exist or cannot be read by FALCON.", code="source_invalid",
                      errors=[{"field": "locator", "message": f"{noun.capitalize()} not found"}])
    if folder and not resolved.is_dir():
        raise Problem(422, "Choose a folder, not a file.", code="source_invalid", errors=[{"field": "locator", "message": "Not a folder"}])
    if not folder and not resolved.is_file():
        raise Problem(422, "Choose an archive file, not a folder.", code="source_invalid", errors=[{"field": "locator", "message": "Not a file"}])
    if not settings.any_folder_allowed:
        roots = [r.resolve() for r in settings.scan_roots]
        if not any(resolved == root or root in resolved.parents for root in roots):
            raise Problem(403, f"This {noun} is outside the scan roots an administrator has allowed.", code="source_forbidden",
                          errors=[{"field": "locator", "message": "Outside the allowed scan roots"}])
    return str(resolved)


def validate_source(kind: str, locator: str, options: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    caps = {k["kind"]: k for k in capabilities()["source_kinds"]}
    if kind not in caps:
        raise Problem(422, "Unknown source type.", code="source_invalid")
    if not caps[kind]["available"]:
        raise Problem(409, caps[kind]["reason"] or "This source type is unavailable.", code="source_unavailable")
    clean_options: dict[str, Any] = {}
    try:
        if kind == "directory":
            locator = _validate_path(locator, folder=True)
        elif kind in ("archive", "image-archive"):
            locator = _validate_path(locator, folder=False)
        elif kind == "git":
            locator = workspace.validate_git_url(locator)
            ref = (options.get("ref") or "").strip()
            if ref:
                if not re.match(r"^[\w./-]{1,200}$", ref):
                    raise Problem(422, "The branch or tag name contains unsupported characters.", code="source_invalid",
                                  errors=[{"field": "ref", "message": "Unsupported characters"}])
                clean_options["ref"] = ref
        elif kind == "image-registry":
            registry, repo, reference = workspace.parse_image_ref(locator)
            locator = locator.strip()
            clean_options["resolved"] = f"{registry}/{repo}:{reference}" if not reference.startswith("sha256:") else f"{registry}/{repo}@{reference}"
        elif kind == "endpoint":
            endpoints = parse_endpoints(locator)
            locator = "\n".join(f"{h}:{p}" for h, p in endpoints)
            timeout = options.get("timeout")
            if timeout is not None:
                clean_options["timeout"] = max(2, min(30, int(timeout)))
    except workspace.AcquisitionError as err:
        raise Problem(422, str(err), code="source_invalid", errors=[{"field": "locator", "message": str(err)}])
    except EndpointError as err:
        raise Problem(422, str(err), code="source_invalid", errors=[{"field": "locator", "message": str(err)}])
    return locator, clean_options


def _system(db: Session, system_id: str) -> System:
    system = db.get(System, system_id)
    if system is None:
        raise not_found("System")
    return system


def uploaded(source: Source) -> bool:
    return source.kind in ("archive", "image-archive") and bool((source.options or {}).get("filename"))


def source_payload(db: Session, source: Source) -> dict[str, Any]:
    last = db.get(Scan, source.last_scan_id) if source.last_scan_id else None
    active = db.scalar(select(Scan).where(Scan.source_id == source.id, Scan.status.in_(ACTIVE)).order_by(Scan.queued_at.desc()).limit(1))
    return {
        "id": source.id, "system_id": source.system_id, "kind": source.kind, "kind_label": SOURCE_KINDS.get(source.kind, source.kind),
        # Uploaded files live in FALCON's data folder: show their original name, not the storage path.
        "name": source.name, "locator": Path(source.locator).name if uploaded(source) else source.locator,
        "options": {k: v for k, v in (source.options or {}).items() if k != "credentials"},
        "created_at": source.created_at, "updated_at": source.updated_at,
        "last_scan": scan_payload(last, brief=True) if last else None,
        "active_scan": scan_payload(active, brief=True) if active else None,
    }


def list_sources(db: Session, system_id: str) -> list[dict[str, Any]]:
    _system(db, system_id)
    sources = db.scalars(select(Source).where(Source.system_id == system_id).order_by(Source.created_at)).all()
    return [source_payload(db, s) for s in sources]


def _default_name(kind: str, locator: str) -> str:
    if kind == "endpoint":
        first = locator.split("\n")[0]
        more = locator.count("\n")
        return first + (f" and {more} more" if more else "")
    tail = re.split(r"[\\/]", locator.rstrip("/\\"))[-1] or locator
    return tail.removesuffix(".git")[:160]


def create_source(db: Session, principal: Principal, system_id: str, *, kind: str, locator: str, name: str | None,
                  options: dict[str, Any], ip: str | None, scan_now: bool = True) -> tuple[Source, Scan | None]:
    system = _system(db, system_id)
    locator, clean = validate_source(kind, locator, options)
    source = Source(system_id=system.id, kind=kind, name=(name or "").strip()[:160] or _default_name(kind, locator),
                    locator=locator, options=clean, created_by=principal.user_id)
    db.add(source)
    db.flush()
    audit.append(db, action="source.added", summary=f"{principal.name} added {SOURCE_KINDS[kind].lower()} “{source.name}” to {system.name}",
                 target_type="source", target_id=source.id, detail={"kind": kind, "system_id": system.id},
                 **actor_fields(principal, ip))
    scan = _queue(db, principal, source, ip) if scan_now else None
    db.commit()
    return source, scan


def store_upload(db: Session, principal: Principal, system_id: str, *, kind: str, filename: str, stream: BinaryIO,
                 name: str | None, ip: str | None) -> tuple[Source, Scan]:
    settings = get_settings()
    system = _system(db, system_id)
    if kind not in ("archive", "image-archive"):
        raise Problem(422, "Uploads must be archives or saved container images.", code="source_invalid")
    safe = re.sub(r"[^\w.-]", "_", Path(filename or "upload").name)[:120] or "upload"
    source = Source(system_id=system.id, kind=kind, name=(name or "").strip()[:160] or safe, locator="", options={},
                    created_by=principal.user_id)
    db.add(source)
    db.flush()
    target_dir = settings.uploads_dir / source.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe
    limit = settings.upload_max_mb * 1024 * 1024
    written = 0
    try:
        with target.open("wb") as out:
            while chunk := stream.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise Problem(413, f"The upload is larger than {settings.upload_max_mb} MB.", code="upload_too_large")
                out.write(chunk)
    except Problem:
        db.rollback()
        shutil.rmtree(target_dir, ignore_errors=True)
        raise
    source.locator = str(target)
    source.options = {"size": written, "filename": safe}
    audit.append(db, action="source.added", summary=f"{principal.name} uploaded “{safe}” to {system.name}",
                 target_type="source", target_id=source.id, detail={"kind": kind, "bytes": written, "system_id": system.id},
                 **actor_fields(principal, ip))
    scan = _queue(db, principal, source, ip)
    db.commit()
    return source, scan


def update_source(db: Session, principal: Principal, source_id: str, *, name: str | None, ip: str | None) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    if name and name.strip() and name.strip() != source.name:
        previous = source.name
        source.name = name.strip()[:160]
        audit.append(db, action="source.updated", summary=f"{principal.name} renamed source “{previous}” to “{source.name}”",
                     target_type="source", target_id=source.id, detail={"system_id": source.system_id}, **actor_fields(principal, ip))
        db.commit()
    return source


def delete_source(db: Session, principal: Principal, source_id: str, ip: str | None) -> None:
    source = db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    if db.scalar(select(Scan.id).where(Scan.source_id == source.id, Scan.status.in_(ACTIVE))):
        raise conflict("Cancel the running scan before removing this source.", code="scan_active")
    system_id = source.system_id
    audit.append(db, action="source.removed", summary=f"{principal.name} removed source “{source.name}”",
                 target_type="source", target_id=source.id, detail={"kind": source.kind, "system_id": system_id},
                 **actor_fields(principal, ip))
    if uploaded(source):
        shutil.rmtree(get_settings().uploads_dir / source.id, ignore_errors=True)
    db.delete(source)
    db.flush()
    recompute_status(db, system_id)
    db.commit()


# ---------------------------------------------------------------------- scans

def _queue(db: Session, principal: Principal, source: Source, ip: str | None) -> Scan:
    if db.scalar(select(Scan.id).where(Scan.source_id == source.id, Scan.status.in_(ACTIVE))):
        raise conflict("A scan of this source is already queued or running.", code="scan_active")
    scan = Scan(source_id=source.id, system_id=source.system_id, status="queued", requested_by=principal.user_id,
                requested_by_label=principal.name, queued_at=utcnow())
    db.add(scan)
    db.flush()
    audit.append(db, action="scan.queued", summary=f"{principal.name} started discovery of “{source.name}”",
                 target_type="scan", target_id=scan.id, detail={"source_id": source.id, "system_id": source.system_id},
                 **actor_fields(principal, ip))
    return scan


def queue_scan(db: Session, principal: Principal, source_id: str, ip: str | None) -> Scan:
    source = db.get(Source, source_id)
    if source is None:
        raise not_found("Source")
    if source.kind == "directory" or (source.kind in ("archive", "image-archive") and not uploaded(source)):
        validate_source(source.kind, source.locator, source.options or {})
    scan = _queue(db, principal, source, ip)
    db.commit()
    return scan


def request_cancel(db: Session, principal: Principal, scan_id: str, ip: str | None) -> Scan:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise not_found("Scan")
    if scan.status not in ACTIVE:
        raise conflict("This scan has already finished.", code="scan_finished")
    if scan.status == "queued":
        scan.status = "cancelled"
        scan.finished_at = utcnow()
        scan.error = "Cancelled before it started."
    scan.cancel_requested = True
    source = db.get(Source, scan.source_id)
    audit.append(db, action="scan.cancel_requested", summary=f"{principal.name} cancelled the scan of “{source.name if source else 'a source'}”",
                 target_type="scan", target_id=scan.id, detail={"system_id": scan.system_id}, **actor_fields(principal, ip))
    db.commit()
    return scan


def scan_payload(scan: Scan, brief: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": scan.id, "source_id": scan.source_id, "system_id": scan.system_id, "status": scan.status, "stage": scan.stage,
        "stage_detail": scan.stage_detail, "files_total": scan.files_total, "files_done": scan.files_done,
        "bytes_done": scan.bytes_done, "evidence": scan.evidence_count, "artefacts": scan.artefact_count,
        "new_artefacts": scan.new_artefacts, "error": scan.error, "requested_by": scan.requested_by_label,
        "queued_at": scan.queued_at, "started_at": scan.started_at, "finished_at": scan.finished_at,
        "duration_seconds": round((scan.finished_at - scan.started_at).total_seconds(), 1) if scan.finished_at and scan.started_at else None,
    }
    if not brief:
        payload["coverage"] = scan.coverage or {}
        payload["stats"] = scan.stats or {}
    return payload


def scan_detail(db: Session, scan_id: str) -> dict[str, Any]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise not_found("Scan")
    source = db.get(Source, scan.source_id)
    system = db.get(System, scan.system_id)
    payload = scan_payload(scan)
    payload["source"] = {"id": source.id, "name": source.name, "kind": source.kind, "kind_label": SOURCE_KINDS.get(source.kind)} if source else None
    payload["system"] = {"id": system.id, "name": system.name, "code": system.code} if system else None
    if scan.status == "succeeded":
        payload["summary"] = inventory_summary(db, system_id=scan.system_id, scan_id=scan.id)
    return payload


def list_scans(db: Session, *, system_id: str | None, status: list[str] | None, limit: int) -> list[dict[str, Any]]:
    stmt = select(Scan, Source.name, Source.kind, System.name, System.code).join(Source, Source.id == Scan.source_id).join(
        System, System.id == Scan.system_id).order_by(Scan.queued_at.desc()).limit(limit)
    if system_id:
        stmt = stmt.where(Scan.system_id == system_id)
    if status:
        stmt = stmt.where(Scan.status.in_(status))
    out = []
    for scan, source_name, source_kind, system_name, system_code in db.execute(stmt).all():
        payload = scan_payload(scan, brief=True)
        payload.update(source_name=source_name, source_kind=source_kind, source_kind_label=SOURCE_KINDS.get(source_kind),
                       system_name=system_name, system_code=system_code)
        out.append(payload)
    return out


# ------------------------------------------------------------------ inventory

SORTS = {
    "risk": (Artefact.quantum, Artefact.classical, Artefact.name),
    "name": (Artefact.name,),
    "recent": (Artefact.last_seen_at.desc(),),
    "evidence": (Artefact.occurrence_count.desc(),),
}
QUANTUM_ORDER = ["vulnerable", "weakened", "unknown", "hybrid", "resistant", "pqc"]


def _artefact_query(*, system_id: str | None, kind: list[str] | None, quantum: list[str] | None, classical: list[str] | None,
                    status: str | None, q: str | None, scan_id: str | None, family: str | None):
    stmt = select(Artefact)
    if system_id:
        stmt = stmt.where(Artefact.system_id == system_id)
    if kind:
        stmt = stmt.where(Artefact.kind.in_(kind))
    if quantum:
        stmt = stmt.where(Artefact.quantum.in_(quantum))
    if classical:
        stmt = stmt.where(Artefact.classical.in_(classical))
    if status and status != "all":
        stmt = stmt.where(Artefact.status == status)
    if family:
        stmt = stmt.where(Artefact.family == family)
    if q:
        stmt = stmt.where(Artefact.name.ilike(f"%{q.strip()}%"))
    if scan_id:
        stmt = stmt.where(Artefact.id.in_(select(Occurrence.artefact_id).where(Occurrence.scan_id == scan_id)))
    return stmt


def artefact_payload(artefact: Artefact, system: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "id": artefact.id, "system_id": artefact.system_id, "kind": artefact.kind, "name": artefact.name, "family": artefact.family,
        "quantum": artefact.quantum, "classical": artefact.classical, "primitive": artefact.primitive,
        "confidence": round(artefact.confidence, 2), "status": artefact.status, "occurrences": artefact.occurrence_count,
        "first_seen_at": artefact.first_seen_at, "last_seen_at": artefact.last_seen_at, "identity": artefact.identity,
        "properties": artefact.properties, **({"system": system} if system else {}),
    }


def list_artefacts(db: Session, *, system_id: str | None, kind: list[str] | None, quantum: list[str] | None,
                   classical: list[str] | None, status: str | None, q: str | None, scan_id: str | None, family: str | None,
                   sort: str, limit: int, offset: int) -> dict[str, Any]:
    stmt = _artefact_query(system_id=system_id, kind=kind, quantum=quantum, classical=classical, status=status, q=q,
                           scan_id=scan_id, family=family)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt).all()
    if sort == "risk":
        rank = {k: i for i, k in enumerate(QUANTUM_ORDER)}
        classical_rank = {"broken": 0, "weak": 1, "legacy": 2, "acceptable": 3, "strong": 4}
        rows = sorted(rows, key=lambda a: (rank.get(a.quantum or "unknown", 2), classical_rank.get(a.classical or "", 5), a.kind, a.name))
    elif sort == "name":
        rows = sorted(rows, key=lambda a: a.name.lower())
    elif sort == "recent":
        rows = sorted(rows, key=lambda a: a.last_seen_at, reverse=True)
    elif sort == "evidence":
        rows = sorted(rows, key=lambda a: a.occurrence_count, reverse=True)
    page = rows[offset: offset + limit]
    systems = {s.id: {"id": s.id, "name": s.name, "code": s.code} for s in db.scalars(select(System).where(System.id.in_({a.system_id for a in page}))).all()}
    return {"items": [artefact_payload(a, systems.get(a.system_id)) for a in page], "total": total}


def artefact_detail(db: Session, artefact_id: str) -> dict[str, Any]:
    artefact = db.get(Artefact, artefact_id)
    if artefact is None:
        raise not_found("Artefact")
    system = db.get(System, artefact.system_id)
    # Current evidence: what the latest scan of each source saw. A resolved artefact
    # keeps the evidence from the last scan that still found it.
    current = [s for s in latest_scan_ids(db, artefact.system_id)
               if db.scalar(select(Occurrence.id).where(Occurrence.scan_id == s, Occurrence.artefact_id == artefact.id).limit(1))]
    scan_ids = current or [artefact.last_scan_id]
    occurrences = db.execute(
        select(Occurrence, Scan.finished_at, Source.name).join(Scan, Scan.id == Occurrence.scan_id).join(Source, Source.id == Occurrence.source_id)
        .where(Occurrence.artefact_id == artefact.id, Occurrence.scan_id.in_(scan_ids))
        .order_by(Source.name, Occurrence.path, Occurrence.line).limit(200)
    ).all()
    links = []
    for link, other in db.execute(select(ArtefactLink, Artefact).join(Artefact, Artefact.id == ArtefactLink.to_id).where(ArtefactLink.from_id == artefact.id)).all():
        links.append({"direction": "out", "relation": link.relation, "artefact": {"id": other.id, "name": other.name, "kind": other.kind, "quantum": other.quantum}})
    for link, other in db.execute(select(ArtefactLink, Artefact).join(Artefact, Artefact.id == ArtefactLink.from_id).where(ArtefactLink.to_id == artefact.id)).all():
        links.append({"direction": "in", "relation": link.relation, "artefact": {"id": other.id, "name": other.name, "kind": other.kind, "quantum": other.quantum}})
    payload = artefact_payload(artefact, {"id": system.id, "name": system.name, "code": system.code} if system else None)
    payload["evidence"] = [
        {"id": o.id, "scan_id": o.scan_id, "source": source_name, "path": o.path, "line": o.line, "column": o.col, "snippet": o.snippet,
         "detector": o.detector, "rule": o.rule, "confidence": o.confidence, "function": o.function, "via": o.via, "scanned_at": finished}
        for o, finished, source_name in occurrences
    ]
    payload["links"] = links
    assessment = (artefact.properties or {}).get("assessment") or {}
    ref_identity = artefact.identity if artefact.kind == "algorithm" else None
    if ref_identity:
        entry = catalogue.algorithm(ref_identity.get("algorithm", "")) or {}
        payload["catalogue"] = {"description": entry.get("description"), "standard": entry.get("standard"),
                                "class": entry.get("class"), "primitives": entry.get("primitives")}
    payload["assessment"] = assessment
    return payload


def inventory_summary(db: Session, *, system_id: str | None = None, scan_id: str | None = None) -> dict[str, Any]:
    base = _artefact_query(system_id=system_id, kind=None, quantum=None, classical=None, status="active" if not scan_id else "all",
                           q=None, scan_id=scan_id, family=None).subquery()
    by_kind = dict(db.execute(select(base.c.kind, func.count()).group_by(base.c.kind)).all())
    by_quantum = dict(db.execute(select(base.c.quantum, func.count()).group_by(base.c.quantum)).all())
    by_classical = dict(db.execute(select(base.c.classical, func.count()).group_by(base.c.classical)).all())
    top = db.execute(select(base.c.family, func.count()).where(base.c.kind == "algorithm").group_by(base.c.family)
                     .order_by(func.count().desc()).limit(10)).all()
    matrix: dict[str, dict[str, int]] = {}
    for kind, quantum, count in db.execute(select(base.c.kind, base.c.quantum, func.count()).group_by(base.c.kind, base.c.quantum)).all():
        matrix.setdefault(kind, {})[quantum or "unknown"] = count
    systems = db.scalar(select(func.count(func.distinct(base.c.system_id)))) or 0

    # Health of the two classes whose risk is not a quantum status: libraries and certificates.
    libraries = {"total": 0, "pqc_capable": 0, "end_of_life": 0, "abandoned": 0}
    certificates = {"total": 0, "expired": 0, "expiring_90_days": 0, "self_signed": 0}
    for kind, properties in db.execute(select(base.c.kind, base.c.properties).where(base.c.kind.in_(("library", "certificate")))).all():
        props = properties or {}
        if kind == "library":
            libraries["total"] += 1
            libraries["pqc_capable"] += bool((props.get("pqc") or {}).get("capable"))
            libraries["end_of_life"] += bool((props.get("eol") or {}).get("reached"))
            libraries["abandoned"] += props.get("status") == "abandoned"
        else:
            certificates["total"] += 1
            days = props.get("days_remaining")
            certificates["expired"] += bool(props.get("expired"))
            certificates["expiring_90_days"] += isinstance(days, int) and 0 <= days <= 90
            certificates["self_signed"] += bool(props.get("self_signed"))

    total = sum(by_kind.values())
    return {
        "total": total,
        "systems": systems,
        "by_kind": {k: by_kind.get(k, 0) for k in ("algorithm", "key", "certificate", "protocol", "library", "hardware", "cloud_service")},
        "by_quantum": {(k or "unknown"): v for k, v in by_quantum.items()},
        "by_classical": {(k or "unknown"): v for k, v in by_classical.items()},
        "matrix": matrix,
        "top_families": [{"family": f, "count": c} for f, c in top if f],
        "libraries": libraries,
        "certificates": certificates,
    }


def systems_inventory(db: Session) -> dict[str, dict[str, Any]]:
    """Per-system counts for the systems register."""
    rows = db.execute(
        select(Artefact.system_id, func.count(), func.sum(case((Artefact.quantum == "vulnerable", 1), else_=0)))
        .where(Artefact.status == "active").group_by(Artefact.system_id)
    ).all()
    last = dict(db.execute(select(Scan.system_id, func.max(Scan.finished_at)).where(Scan.status == "succeeded").group_by(Scan.system_id)).all())
    out = {sid: {"artefacts": count, "vulnerable": int(vulnerable or 0), "last_scan_at": last.get(sid)} for sid, count, vulnerable in rows}
    for sid, finished in last.items():
        out.setdefault(sid, {"artefacts": 0, "vulnerable": 0, "last_scan_at": finished})
    return out


# --------------------------------------------------------------- verification

SAFE = {"pqc", "hybrid", "resistant"}


def scan_diff(db: Session, scan_id: str, against: str | None) -> dict[str, Any]:
    """What changed between two scans of the same source: artefacts that appeared,
    disappeared or stayed. Removed vulnerable cryptography alongside newly found
    post-quantum or hybrid cryptography is how a migration is verified."""
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise not_found("Scan")
    if against:
        base = db.get(Scan, against)
        if base is None or base.source_id != scan.source_id:
            raise Problem(422, "Compare scans of the same source.", code="scan_mismatch")
    else:
        base = db.scalar(select(Scan).where(Scan.source_id == scan.source_id, Scan.status == "succeeded", Scan.queued_at < scan.queued_at)
                         .order_by(Scan.queued_at.desc()).limit(1))
    def seen(sid: str) -> dict[str, set[str]]:
        places: dict[str, set[str]] = {}
        for aid, path in db.execute(select(Occurrence.artefact_id, Occurrence.path).where(Occurrence.scan_id == sid).distinct()).all():
            places.setdefault(aid, set()).add(path)
        return places
    after_places = seen(scan.id)
    before_places = seen(base.id) if base else {}
    after, before = set(after_places), set(before_places)
    ids = after | before
    artefacts = {a.id: a for a in db.scalars(select(Artefact).where(Artefact.id.in_(ids))).all()} if ids else {}

    def brief(aid: str) -> dict[str, Any]:
        a = artefacts[aid]
        return {"id": a.id, "name": a.name, "kind": a.kind, "quantum": a.quantum, "classical": a.classical}

    added = [brief(a) for a in sorted(after - before, key=lambda x: artefacts[x].name) if a in artefacts]
    removed = [brief(a) for a in sorted(before - after, key=lambda x: artefacts[x].name) if a in artefacts]
    def tally(rows: set[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for aid in rows:
            if aid in artefacts:
                key = artefacts[aid].quantum or "unknown"
                out[key] = out.get(key, 0) + 1
        return out
    # Present in both, but found in new places: post-quantum cryptography spreading is migration too.
    spread = [{**brief(aid), "new_locations": sorted(after_places[aid] - before_places[aid])[:10]}
              for aid in sorted(after & before, key=lambda x: artefacts[x].name)
              if aid in artefacts and after_places[aid] - before_places[aid]]
    retired = [r for r in removed if r["quantum"] == "vulnerable" or r["classical"] in ("broken", "weak")]
    introduced = [r for r in added if r["quantum"] in ("pqc", "hybrid")] + [r for r in spread if r["quantum"] in ("pqc", "hybrid")]
    regressions = [r for r in added if r["quantum"] == "vulnerable" or r["classical"] in ("broken", "weak")]
    return {
        "scan": scan_payload(scan, brief=True),
        "base": scan_payload(base, brief=True) if base else None,
        "added": added,
        "removed": removed,
        "spread": spread,
        "unchanged": len(after & before),
        "before": tally(before),
        "after": tally(after),
        "verified": {"retired": len(retired), "introduced": len(introduced), "regressions": len(regressions)},
        "verdict": ("improved" if (retired or introduced) and not regressions else "regressed" if regressions and not (retired or introduced)
                    else "mixed" if regressions else "unchanged") if base else "baseline",
    }
