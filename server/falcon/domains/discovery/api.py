"""Discovery endpoints: sources, scans (with a live event stream) and the inventory."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...kernel.access import Permission, Principal
from ...kernel.database import get_db, get_sessionmaker
from ...kernel.events import hub
from ...kernel.http import client_ip
from ..identity.guard import require
from . import service
from .runner import runner, scan_topic

router = APIRouter(prefix="/api/v1", tags=["Discovery"])

readers = require(Permission.INVENTORY_READ)
managers = require(Permission.SOURCES_MANAGE)
scanners = require(Permission.SCANS_RUN)


class SourceIn(BaseModel):
    # Archives are normally uploaded; a local path is accepted where folders are (desktop, scan roots).
    kind: Literal["directory", "archive", "image-archive", "git", "image-registry", "endpoint"]
    locator: str = Field(min_length=1, max_length=4000)
    name: str | None = Field(default=None, max_length=160)
    options: dict[str, Any] = Field(default_factory=dict)
    scan_now: bool = True


class SourcePatch(BaseModel):
    name: str = Field(min_length=1, max_length=160)


LIVE_FIELDS = ("stage", "stage_detail", "files_total", "files_done", "bytes_done", "evidence", "new_artefacts", "coverage")


def _json(data: Any) -> str:
    return json.dumps(data, default=str, separators=(",", ":"))


# ---------------------------------------------------------------- capabilities

@router.get("/discovery/capabilities")
def capabilities(_: Principal = Depends(readers)) -> dict[str, Any]:
    return service.capabilities()


# -------------------------------------------------------------------- sources

@router.get("/systems/{system_id}/sources")
def list_sources(system_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return service.list_sources(db, system_id)


@router.post("/systems/{system_id}/sources", status_code=201)
def create_source(system_id: str, payload: SourceIn, request: Request, principal: Principal = Depends(managers),
                  db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.scan_now and not principal.can(Permission.SCANS_RUN):
        payload.scan_now = False
    source, scan = service.create_source(db, principal, system_id, kind=payload.kind, locator=payload.locator, name=payload.name,
                                         options=payload.options, ip=client_ip(request), scan_now=payload.scan_now)
    if scan:
        runner.wake()
    return {"source": service.source_payload(db, source), "scan": service.scan_payload(scan, brief=True) if scan else None}


@router.post("/systems/{system_id}/sources/upload", status_code=201)
def upload_source(system_id: str, request: Request, file: UploadFile = File(...), kind: Literal["archive", "image-archive"] = Form(...),
                  name: str | None = Form(default=None), principal: Principal = Depends(scanners),
                  db: Session = Depends(get_db)) -> dict[str, Any]:
    source, scan = service.store_upload(db, principal, system_id, kind=kind, filename=file.filename or "upload", stream=file.file,
                                        name=name, ip=client_ip(request))
    runner.wake()
    return {"source": service.source_payload(db, source), "scan": service.scan_payload(scan, brief=True)}


@router.patch("/sources/{source_id}")
def update_source(source_id: str, payload: SourcePatch, request: Request, principal: Principal = Depends(managers),
                  db: Session = Depends(get_db)) -> dict[str, Any]:
    source = service.update_source(db, principal, source_id, name=payload.name, ip=client_ip(request))
    return service.source_payload(db, source)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, request: Request, principal: Principal = Depends(managers), db: Session = Depends(get_db)) -> None:
    service.delete_source(db, principal, source_id, client_ip(request))


@router.post("/sources/{source_id}/scans", status_code=202)
def start_scan(source_id: str, request: Request, principal: Principal = Depends(scanners), db: Session = Depends(get_db)) -> dict[str, Any]:
    scan = service.queue_scan(db, principal, source_id, client_ip(request))
    runner.wake()
    return service.scan_payload(scan, brief=True)


# ---------------------------------------------------------------------- scans

@router.get("/scans")
def list_scans(system: str | None = None, status: list[str] | None = Query(default=None), limit: int = Query(default=50, ge=1, le=500),
               _: Principal = Depends(readers), db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return service.list_scans(db, system_id=system, status=status, limit=limit)


@router.get("/scans/{scan_id}")
def get_scan(scan_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.scan_detail(db, scan_id)


@router.get("/scans/{scan_id}/diff")
def scan_diff(scan_id: str, against: str | None = None, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Before and after: how this scan differs from an earlier one of the same source."""
    return service.scan_diff(db, scan_id, against)


@router.post("/scans/{scan_id}/cancel", status_code=202)
def cancel_scan(scan_id: str, request: Request, principal: Principal = Depends(scanners), db: Session = Depends(get_db)) -> dict[str, Any]:
    scan = service.request_cancel(db, principal, scan_id, client_ip(request))
    runner.cancel(scan_id)
    return service.scan_payload(scan, brief=True)


@router.get("/scans/{scan_id}/events")
async def scan_events(scan_id: str, request: Request, _: Principal = Depends(readers)) -> StreamingResponse:
    """Server-Sent Events: a snapshot first, then live stage, progress and
    discovery events until the scan finishes."""
    queue = hub.subscribe(scan_topic(scan_id))

    async def stream() -> AsyncIterator[str]:
        try:
            with get_sessionmaker()() as db:
                snapshot = service.scan_detail(db, scan_id)
            live = runner.live(scan_id) if snapshot["status"] in service.ACTIVE else None
            if live:
                snapshot.update({k: v for k, v in live.items() if k in LIVE_FIELDS})
            yield f"event: snapshot\ndata: {_json(snapshot)}\n\n"
            if snapshot["status"] not in service.ACTIVE:
                return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {event['type']}\ndata: {_json(event)}\n\n"
                if event["type"] == "finished":
                    return
        finally:
            hub.unsubscribe(scan_topic(scan_id), queue)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ------------------------------------------------------------------ inventory

@router.get("/artefacts")
def list_artefacts(
    system: str | None = None,
    kind: list[str] | None = Query(default=None),
    quantum: list[str] | None = Query(default=None),
    classical: list[str] | None = Query(default=None),
    status: Literal["active", "resolved", "all"] = "active",
    family: str | None = None,
    q: str | None = Query(default=None, max_length=120),
    scan: str | None = None,
    sort: Literal["risk", "name", "recent", "evidence"] = "risk",
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    _: Principal = Depends(readers),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return service.list_artefacts(db, system_id=system, kind=kind, quantum=quantum, classical=classical, status=status, q=q,
                                  scan_id=scan, family=family, sort=sort, limit=limit, offset=offset)


@router.get("/artefacts/{artefact_id}")
def get_artefact(artefact_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.artefact_detail(db, artefact_id)


@router.get("/inventory/summary")
def summary(system: str | None = None, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.inventory_summary(db, system_id=system)
