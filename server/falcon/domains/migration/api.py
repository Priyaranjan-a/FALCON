"""PQC migration planning endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...kernel import audit
from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ...kernel.http import client_ip
from ..identity.guard import require
from ..identity.service import actor_fields
from . import service

router = APIRouter(prefix="/api/v1/migration", tags=["Migration"])
readers = require(Permission.INVENTORY_READ)
runners = require(Permission.SCANS_RUN)


@router.get("/recommendations/{artefact_id}")
def recommendation(artefact_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.artefact_recommendation(db, artefact_id)


@router.get("/plan")
def plan(system: str | None = None, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.plan(db, system_id=system)


@router.get("/graph")
def graph(_: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.graph(db)


@router.get("/benchmarks")
def benchmarks(_: Principal = Depends(readers)) -> dict[str, Any]:
    return {"report": service.benchmarks()}


@router.post("/benchmarks")
def run_benchmarks(request: Request, principal: Principal = Depends(runners), db: Session = Depends(get_db)) -> dict[str, Any]:
    report = service.run_benchmarks()
    audit.append(db, action="migration.benchmarked", summary=f"{principal.name} ran the post-quantum benchmark lab",
                 target_type="benchmark", detail={"duration_seconds": report["duration_seconds"], "openssl": report["host"]["openssl"]},
                 **actor_fields(principal, client_ip(request)))
    db.commit()
    return {"report": report}
