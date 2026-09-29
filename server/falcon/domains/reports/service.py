"""Reports: standard exports, signed CBOM snapshots, drift and verification."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...kernel import audit
from ...kernel.access import Principal
from ...kernel.problems import Problem, not_found
from ...reporting import attest, cbom, drift, sarif, spdx, tabular
from ...reporting.inventory import from_database
from ...settings import get_settings
from ..identity.service import actor_fields
from ..systems.models import System
from . import library
from .models import CbomSnapshot, ReportExport

FORMATS: dict[str, dict[str, str]] = {
    "cyclonedx-json": {"label": "CycloneDX 1.6 CBOM", "extension": "cdx.json", "media": "application/vnd.cyclonedx+json",
                       "summary": "The cryptography bill of materials: every asset with its crypto properties, evidence and FALCON's assessment."},
    "cyclonedx-xml": {"label": "CycloneDX 1.6 CBOM (XML)", "extension": "cdx.xml", "media": "application/vnd.cyclonedx+xml",
                      "summary": "The same CBOM for XML toolchains, valid against the 1.6 schema."},
    "sarif": {"label": "SARIF 2.1.0", "extension": "sarif", "media": "application/sarif+json",
              "summary": "Findings for code scanning in GitHub, GitLab, Azure DevOps and IDEs, one per line of code."},
    "spdx": {"label": "SPDX 2.3", "extension": "spdx.json", "media": "application/spdx+json",
             "summary": "Software bill of materials: systems, cryptographic libraries and assets, with the assessment as annotations."},
    "csv": {"label": "Risk register (CSV)", "extension": "csv", "media": "text/csv; charset=utf-8",
            "summary": "One row per artefact with risk, Mosca terms, compliance and the recommended replacement."},
    "json": {"label": "FALCON report (JSON)", "extension": "json", "media": "application/json",
             "summary": "FALCON's complete assessment in its own format, for scripts and dashboards."},
}


def keystore() -> attest.KeyStore:
    return attest.KeyStore(get_settings().data_dir / "keys")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "inventory"


def _system(db: Session, system_id: str | None) -> System | None:
    if not system_id:
        return None
    system = db.get(System, system_id)
    if system is None:
        raise not_found("System")
    return system


def _render(db: Session, fmt: str, system_id: str | None) -> tuple[str, str, str, str, int]:
    """Returns (content, media type, filename, scope, artefacts)."""
    if fmt not in FORMATS:
        raise Problem(422, f"Unknown format {fmt!r}. Choose one of: {', '.join(FORMATS)}.", code="unknown_format")
    system = _system(db, system_id)
    report = from_database(db, system_id=system_id)
    if fmt == "cyclonedx-json":
        content = cbom.to_json(cbom.build(report))
    elif fmt == "cyclonedx-xml":
        content = cbom.to_xml(cbom.build(report))
    elif fmt == "sarif":
        content = json.dumps(sarif.build(report), indent=2, ensure_ascii=False)
    elif fmt == "spdx":
        content = json.dumps(spdx.build(report), indent=2, ensure_ascii=False)
    elif fmt == "csv":
        content = tabular.to_csv(report)
    else:
        content = json.dumps(tabular.to_native(report), indent=2, ensure_ascii=False, default=str)
    meta = FORMATS[fmt]
    stamp = report.generated_at.strftime("%Y%m%d-%H%M")
    filename = f"falcon-{_slug(system.code if system else report.organisation)}-{stamp}.{meta['extension']}"
    return content, meta["media"], filename, report.scope, len(report.items)


def export(db: Session, principal: Principal, fmt: str, system_id: str | None, ip: str | None) -> tuple[str, str, str]:
    """A direct download for API clients: returns (content, media type, filename)."""
    content, media, filename, scope, artefacts = _render(db, fmt, system_id)
    audit.append(db, action="report.exported", summary=f"{principal.name} exported {FORMATS[fmt]['label']} for {scope}",
                 target_type="report", target_id=system_id,
                 detail={"format": fmt, "artefacts": artefacts, "system_id": system_id},
                 **actor_fields(principal, ip))
    db.commit()
    return content, media, filename


# ------------------------------------------------------------ export library

_MEDIA_BY_SUFFIX = {".json": "application/json", ".xml": "application/xml", ".csv": "text/csv; charset=utf-8",
                    ".sarif": "application/sarif+json", ".pem": "application/x-pem-file"}


def export_payload(e: ReportExport) -> dict[str, Any]:
    path = Path(e.path)
    return {
        "id": e.id, "created_at": e.created_at.isoformat(), "created_by": e.created_by, "kind": e.kind, "format": e.format,
        "label": e.label, "scope": e.scope, "system_id": e.system_id, "filename": path.name, "size": e.size, "sha256": e.sha256,
        "path": str(path) if get_settings().desktop else None, "available": path.exists(),
    }


def create_export(db: Session, principal: Principal, *, kind: str, fmt: str | None, system_id: str | None,
                  snapshot_id: str | None, part: str | None, ip: str | None) -> dict[str, Any]:
    """Writes an export to the library (server) or the user's export folder (desktop) and records it."""
    if kind == "inventory":
        content, _, filename, scope, artefacts = _render(db, fmt or "", system_id)
        label, fmt_key, detail = FORMATS[fmt]["label"], fmt, {"artefacts": artefacts}
    elif kind == "snapshot":
        if part not in ("cbom", "envelope"):
            raise Problem(422, "Choose the CBOM or the signed attestation.", code="unknown_part")
        s = _snapshot(db, snapshot_id or "")
        content, _, filename = snapshot_file(db, s.id, part)
        scope, system_id = s.label, s.system_id
        label = "Snapshot CBOM (CycloneDX 1.6)" if part == "cbom" else "Signed attestation (DSSE, ML-DSA-65)"
        fmt_key, detail = f"snapshot-{part}", {"snapshot_id": s.id}
    elif kind == "key":
        info = key_info()
        content, filename, scope = info["public_key_pem"], "falcon-attestation.pub.pem", "Attestation public key"
        label, fmt_key, detail = "Public key (ML-DSA-65, PEM)", "key-pem", {"key_id": info["key_id"]}
    else:
        raise Problem(422, "Unknown export.", code="unknown_export")

    data = content.encode("utf-8")
    path = library.write(filename, data)
    record = ReportExport(created_by=principal.name, user_id=principal.user_id, kind=kind, format=fmt_key, label=label[:160],
                          scope=scope[:200], system_id=system_id, filename=path.name[:255], size=len(data),
                          sha256=hashlib.sha256(data).hexdigest(), path=str(path))
    db.add(record)
    db.flush()
    audit.append(db, action="report.exported", summary=f"{principal.name} exported {label} for {scope}",
                 target_type="export", target_id=record.id,
                 detail={"format": fmt_key, "system_id": system_id, "file": path.name, "sha256": record.sha256, **detail},
                 **actor_fields(principal, ip))
    db.commit()
    return export_payload(record)


def list_exports(db: Session, limit: int = 100) -> dict[str, Any]:
    rows = db.scalars(select(ReportExport).order_by(ReportExport.created_at.desc()).limit(limit)).all()
    return {"items": [export_payload(e) for e in rows], "location": library.describe()}


def _export(db: Session, export_id: str) -> ReportExport:
    e = db.get(ReportExport, export_id)
    if e is None:
        raise not_found("Export")
    return e


def export_file(db: Session, export_id: str) -> tuple[bytes, str, str]:
    e = _export(db, export_id)
    path = Path(e.path)
    if not path.exists():
        raise Problem(404, "The file is no longer there. It may have been moved or deleted.", code="export_missing")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != e.sha256:
        raise Problem(409, "The file has changed since FALCON wrote it, so it is not served. Export it again.", code="export_modified")
    return data, _MEDIA_BY_SUFFIX.get(path.suffix, "application/octet-stream"), path.name


def reveal_export(db: Session, export_id: str) -> None:
    library.reveal(Path(_export(db, export_id).path))


def remove_export(db: Session, export_id: str) -> None:
    """Removes an export from the list. On a server its stored copy goes too; on the desktop the user's file stays."""
    e = _export(db, export_id)
    if not get_settings().desktop:
        Path(e.path).unlink(missing_ok=True)
    db.delete(e)
    db.commit()


# ------------------------------------------------------------------ snapshots

def snapshot_payload(s: CbomSnapshot) -> dict[str, Any]:
    return {"id": s.id, "label": s.label, "created_at": s.created_at.isoformat(), "created_by": s.created_by,
            "system_id": s.system_id, "digest": s.digest, "components": s.components, "summary": s.summary, "key_id": s.key_id}


def create_snapshot(db: Session, principal: Principal, *, label: str | None, system_id: str | None, ip: str | None) -> dict[str, Any]:
    _system(db, system_id)
    report = from_database(db, system_id=system_id)
    if not report.items:
        raise Problem(409, "There is nothing to attest yet. Run a scan first.", code="empty_inventory")
    doc = cbom.build(report)
    digest = cbom.digest(doc)
    key = keystore().signing_key()
    name = f"falcon-{_slug(report.scope)}.cdx.json"
    envelope = attest.sign(key, attest.statement(doc, name=name, digest=digest))
    summary = {**tabular.summary(report), "scope": report.scope, "organisation": report.organisation,
               "threat_model": report.model.scenario}
    snapshot = CbomSnapshot(
        created_by=principal.name, system_id=system_id,
        label=(label or "").strip()[:160] or f"{report.scope} · {report.generated_at:%d %b %Y}",
        digest=digest, components=len(doc["components"]), summary=summary,
        cbom=cbom.to_json(doc, indent=None), envelope=json.dumps(envelope, separators=(",", ":")), key_id=key.id,
    )
    db.add(snapshot)
    db.flush()
    audit.append(db, action="report.snapshot_signed",
                 summary=f"{principal.name} signed a CBOM snapshot of {report.scope} ({len(report.items)} artefacts) with ML-DSA-65",
                 target_type="snapshot", target_id=snapshot.id,
                 detail={"digest": digest, "key_id": key.id, "artefacts": len(report.items), "system_id": system_id},
                 **actor_fields(principal, ip))
    db.commit()
    return snapshot_payload(snapshot)


def list_snapshots(db: Session, *, system_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    stmt = select(CbomSnapshot).order_by(CbomSnapshot.created_at.desc()).limit(limit)
    if system_id:
        stmt = stmt.where(CbomSnapshot.system_id == system_id)
    return [snapshot_payload(s) for s in db.scalars(stmt).all()]


def _snapshot(db: Session, snapshot_id: str) -> CbomSnapshot:
    s = db.get(CbomSnapshot, snapshot_id)
    if s is None:
        raise not_found("Snapshot")
    return s


def snapshot_detail(db: Session, snapshot_id: str) -> dict[str, Any]:
    s = _snapshot(db, snapshot_id)
    verdict = attest.verify(s.envelope, keystore().public_keys())
    verdict.pop("cbom", None)
    # The stored CBOM must be the one that was signed.
    verdict["stored_matches"] = cbom.digest(json.loads(s.cbom)) == s.digest
    verdict["valid"] = verdict["valid"] and verdict["stored_matches"]
    return {**snapshot_payload(s), "verification": verdict}


def snapshot_file(db: Session, snapshot_id: str, part: str) -> tuple[str, str, str]:
    s = _snapshot(db, snapshot_id)
    stamp = s.created_at.strftime("%Y%m%d-%H%M")
    if part == "cbom":
        return cbom.to_json(json.loads(s.cbom)), FORMATS["cyclonedx-json"]["media"], f"falcon-snapshot-{stamp}.cdx.json"
    if part == "envelope":
        return json.dumps(json.loads(s.envelope), indent=2), "application/vnd.dsse.envelope.v1+json", f"falcon-snapshot-{stamp}.dsse.json"
    raise not_found("Snapshot file")


def drift_between(db: Session, base_id: str, head_id: str | None) -> dict[str, Any]:
    base = _snapshot(db, base_id)
    base_doc = json.loads(base.cbom)
    if head_id:
        head = _snapshot(db, head_id)
        head_doc, head_meta = json.loads(head.cbom), snapshot_payload(head)
    else:
        head_doc = cbom.build(from_database(db, system_id=base.system_id))
        head_meta = {"id": None, "label": "Current inventory", "created_at": head_doc["metadata"]["timestamp"]}
    result = drift.compare(base_doc, head_doc)
    result["base"].update(snapshot_payload(base))
    result["head"].update(head_meta)
    return result


# ------------------------------------------------------------------------ keys

def key_info() -> dict[str, Any]:
    store = keystore()
    active = store.signing_key().describe()
    return {**active, "known_keys": sorted(store.public_keys())}


def rotate_key(db: Session, principal: Principal, ip: str | None) -> dict[str, Any]:
    old = keystore().signing_key().id
    new = keystore().rotate()
    audit.append(db, action="report.key_rotated", summary=f"{principal.name} rotated the ML-DSA-65 attestation key",
                 target_type="key", target_id=new.id, detail={"previous": old, "key_id": new.id}, **actor_fields(principal, ip))
    db.commit()
    return key_info()


def verify_envelope(envelope: Any, public_key: str | None) -> dict[str, Any]:
    keys: Any = [public_key] if public_key else keystore().public_keys()
    verdict = attest.verify(envelope, keys)
    predicate = verdict.pop("cbom", None)
    if predicate:
        props = {p["name"]: p["value"] for p in predicate.get("metadata", {}).get("properties", [])}
        verdict["scope"] = predicate.get("metadata", {}).get("component", {}).get("name")
        verdict["organisation"] = predicate.get("metadata", {}).get("manufacturer", {}).get("name")
        verdict["artefacts"] = int(props.get("falcon:artefacts", 0) or 0)
    return verdict
