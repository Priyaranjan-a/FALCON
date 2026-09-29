"""Systems register use-cases."""
from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...kernel import audit
from ...kernel.access import Principal
from ...kernel.problems import conflict, not_found
from ..horizon.model import ThreatModel, mosca
from ..identity.service import actor_fields
from .catalogue import CLASSIFICATION, CRITICALITY, EXPOSURE, KINDS
from .models import System
from .schemas import SystemIn, SystemPatch

SORTS = {
    "exposure": lambda p: (-p["mosca"]["exposure_years"], p["code"]),
    "criticality": lambda p: (-CRITICALITY[p["criticality"]]["rank"], p["code"]),
    "name": lambda p: (p["name"].lower(), p["code"]),
    "code": lambda p: (p["code"],),
    "updated": lambda p: (-p["updated_at"].timestamp(), p["code"]),
}


def payload(system: System, model: ThreatModel) -> dict[str, Any]:
    return {
        "id": system.id,
        "code": system.code,
        "name": system.name,
        "description": system.description,
        "kind": system.kind,
        "lifecycle": system.lifecycle,
        "environment": system.environment,
        "exposure": system.exposure,
        "criticality": system.criticality,
        "data_classification": system.data_classification,
        "data_shelf_life_years": system.data_shelf_life_years,
        "migration_years": system.migration_years,
        "owner": system.owner,
        "team": system.team,
        "tags": list(system.tags or []),
        "created_at": system.created_at,
        "updated_at": system.updated_at,
        "mosca": mosca(model, system.data_shelf_life_years, system.migration_years),
    }


def _get(db: Session, system_id: str) -> System:
    system = db.get(System, system_id)
    if system is None:
        raise not_found("System")
    return system


def _code_taken(db: Session, code: str, exclude_id: str | None = None) -> bool:
    stmt = select(System.id).where(System.code == code)
    if exclude_id:
        stmt = stmt.where(System.id != exclude_id)
    return db.scalar(stmt) is not None


def list_systems(
    db: Session,
    model: ThreatModel,
    *,
    q: str | None = None,
    kind: list[str] | None = None,
    criticality: list[str] | None = None,
    exposure: list[str] | None = None,
    classification: list[str] | None = None,
    status: list[str] | None = None,
    sort: str = "exposure",
) -> list[dict[str, Any]]:
    stmt = select(System)
    if kind:
        stmt = stmt.where(System.kind.in_(kind))
    if criticality:
        stmt = stmt.where(System.criticality.in_(criticality))
    if exposure:
        stmt = stmt.where(System.exposure.in_(exposure))
    if classification:
        stmt = stmt.where(System.data_classification.in_(classification))
    rows = [payload(s, model) for s in db.scalars(stmt).all()]
    if q:
        needle = q.strip().lower()
        rows = [
            r for r in rows
            if needle in r["name"].lower() or needle in r["code"].lower()
            or needle in (r["owner"] or "").lower() or needle in (r["team"] or "").lower()
            or any(needle in t for t in r["tags"])
        ]
    if status:
        rows = [r for r in rows if r["mosca"]["status"] in status]
    rows.sort(key=SORTS.get(sort, SORTS["exposure"]))
    return rows


def get_system(db: Session, model: ThreatModel, system_id: str) -> dict[str, Any]:
    return payload(_get(db, system_id), model)


def create_system(db: Session, principal: Principal, data: SystemIn, model: ThreatModel, ip: str | None) -> dict[str, Any]:
    if _code_taken(db, data.code):
        raise conflict(f"A system with code {data.code} already exists.", code="system_code_taken")
    system = System(**data.model_dump(), created_by=principal.user_id)
    db.add(system)
    db.flush()
    audit.append(
        db, action="system.registered", summary=f"{principal.name} registered {system.name} ({system.code})",
        target_type="system", target_id=system.id,
        detail={"kind": system.kind, "criticality": system.criticality, "classification": system.data_classification},
        **actor_fields(principal, ip),
    )
    db.commit()
    return payload(system, model)


def update_system(db: Session, principal: Principal, system_id: str, patch: SystemPatch, model: ThreatModel, ip: str | None) -> dict[str, Any]:
    system = _get(db, system_id)
    changes: dict[str, dict[str, Any]] = {}
    for field, value in patch.model_dump(exclude_unset=True).items():
        if value is None and field not in ("description", "owner", "team"):
            continue
        if field == "code" and value != system.code and _code_taken(db, value, exclude_id=system.id):
            raise conflict(f"A system with code {value} already exists.", code="system_code_taken")
        current = getattr(system, field)
        if current != value:
            changes[field] = {"from": current, "to": value}
            setattr(system, field, value)
    if changes:
        audit.append(
            db, action="system.updated",
            summary=f"{principal.name} updated {system.name} ({', '.join(f.replace('_', ' ') for f in changes)})",
            target_type="system", target_id=system.id, detail=changes, **actor_fields(principal, ip),
        )
        db.commit()
    return payload(system, model)


def delete_system(db: Session, principal: Principal, system_id: str, ip: str | None) -> None:
    system = _get(db, system_id)
    audit.append(
        db, action="system.removed", summary=f"{principal.name} removed {system.name} ({system.code}) from the register",
        target_type="system", target_id=system.id, detail={"code": system.code, "name": system.name},
        **actor_fields(principal, ip),
    )
    db.delete(system)
    db.commit()


def summary(db: Session, model: ThreatModel) -> dict[str, Any]:
    rows = [payload(s, model) for s in db.scalars(select(System)).all()]
    active = [r for r in rows if r["lifecycle"] != "retired"]
    statuses = Counter(r["mosca"]["status"] for r in active)

    def tally(field: str, vocabulary: dict) -> list[dict[str, Any]]:
        counts = Counter(r[field] for r in active)
        return [{"key": k, "label": v["label"], "count": counts.get(k, 0)} for k, v in vocabulary.items()]

    exposed = sorted(active, key=lambda r: -r["mosca"]["exposure_years"])
    probabilities = [r["mosca"]["probability"] for r in active]
    return {
        "total": len(rows),
        "active": len(active),
        "retired": len(rows) - len(active),
        "mosca": {
            "exposed": statuses.get("exposed", 0),
            "watch": statuses.get("watch", 0),
            "clear": statuses.get("clear", 0),
            "mean_probability": round(sum(probabilities) / len(probabilities), 6) if probabilities else 0.0,
            "max_probability": round(max(probabilities), 6) if probabilities else 0.0,
            "overdue": sum(1 for r in active if r["mosca"]["overdue_years"] > 0),
        },
        "by_criticality": tally("criticality", CRITICALITY),
        "by_classification": tally("data_classification", CLASSIFICATION),
        "by_exposure": tally("exposure", EXPOSURE),
        "by_kind": tally("kind", KINDS),
        "plane": [
            {
                "id": r["id"], "code": r["code"], "name": r["name"], "criticality": r["criticality"],
                "kind": r["kind"], **{k: r["mosca"][k] for k in ("x", "y", "z", "exposure_years", "status", "probability", "start_by")},
            }
            for r in exposed
        ],
    }
