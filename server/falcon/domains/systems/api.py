"""Systems register endpoints."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ...kernel.http import client_ip
from ..discovery.service import systems_inventory
from ..identity.guard import require
from ..organisation.service import require_organisation, threat_model
from . import service
from .catalogue import vocabulary
from .schemas import SystemIn, SystemPatch

router = APIRouter(prefix="/api/v1/systems", tags=["Systems"])

readers = require(Permission.SYSTEMS_READ)


def _model(db: Session):
    return threat_model(require_organisation(db))


@router.get("/vocabulary")
def system_vocabulary(_: Principal = Depends(readers)) -> dict[str, Any]:
    return vocabulary()


@router.get("/summary")
def systems_summary(_: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.summary(db, _model(db))


@router.get("")
def list_systems(
    q: str | None = Query(default=None, max_length=120),
    kind: list[str] | None = Query(default=None),
    criticality: list[str] | None = Query(default=None),
    exposure: list[str] | None = Query(default=None),
    classification: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    sort: Literal["exposure", "criticality", "name", "code", "updated"] = "exposure",
    _: Principal = Depends(readers),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items = service.list_systems(
        db, _model(db), q=q, kind=kind, criticality=criticality, exposure=exposure,
        classification=classification, status=status, sort=sort,
    )
    inventory = systems_inventory(db)
    empty = {"artefacts": 0, "vulnerable": 0, "last_scan_at": None}
    for item in items:
        item["inventory"] = inventory.get(item["id"], empty)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
def create_system(
    payload: SystemIn, request: Request,
    principal: Principal = Depends(require(Permission.SYSTEMS_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return service.create_system(db, principal, payload, _model(db), client_ip(request))


@router.get("/{system_id}")
def get_system(system_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    system = service.get_system(db, _model(db), system_id)
    system["inventory"] = systems_inventory(db).get(system_id, {"artefacts": 0, "vulnerable": 0, "last_scan_at": None})
    return system


@router.patch("/{system_id}")
def update_system(
    system_id: str, payload: SystemPatch, request: Request,
    principal: Principal = Depends(require(Permission.SYSTEMS_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return service.update_system(db, principal, system_id, payload, _model(db), client_ip(request))


@router.delete("/{system_id}", status_code=204)
def delete_system(
    system_id: str, request: Request,
    principal: Principal = Depends(require(Permission.SYSTEMS_DELETE)),
    db: Session = Depends(get_db),
) -> None:
    service.delete_system(db, principal, system_id, client_ip(request))
