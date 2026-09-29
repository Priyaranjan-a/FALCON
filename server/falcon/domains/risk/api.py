"""Quantum risk intelligence endpoints."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ..identity.guard import require
from . import service

router = APIRouter(prefix="/api/v1/risk", tags=["Risk"])
readers = require(Permission.INVENTORY_READ)


@router.get("/summary")
def summary(system: str | None = None, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.summary(db, system_id=system)


@router.get("/register")
def register(
    system: str | None = None,
    band: list[str] | None = Query(default=None),
    kind: list[str] | None = Query(default=None),
    role: Literal["confidentiality", "authenticity", "integrity", "enabling"] | None = None,
    hndl: bool | None = None,
    lifetime: str | None = None,
    framework: str | None = None,
    policy_status: list[str] | None = Query(default=None),
    likelihood: str | None = None,
    impact: str | None = None,
    q: str | None = Query(default=None, max_length=120),
    sort: Literal["score", "exposure", "probability", "name"] = "score",
    limit: int = Query(default=100, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    _: Principal = Depends(readers),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return service.register(db, system_id=system, band=band, kind=kind, role=role, hndl=hndl, lifetime=lifetime,
                            framework=framework, policy_status=policy_status, likelihood=likelihood, impact=impact,
                            q=q, sort=sort, limit=limit, offset=offset)


@router.get("/artefacts/{artefact_id}")
def artefact(artefact_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.detail(db, artefact_id)


@router.get("/timeline")
def timeline(system: str | None = None, until: int = Query(default=2045, ge=2027, le=2060), _: Principal = Depends(readers),
             db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.timeline(db, system_id=system, until=until)


@router.get("/policies")
def policies(_: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.policy_overview(db)
