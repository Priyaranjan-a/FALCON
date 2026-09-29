"""Reports endpoints: exports, signed CBOM snapshots, drift and verification."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ...kernel.http import client_ip
from ..identity.guard import require
from . import library, service

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])
readers = require(Permission.INVENTORY_READ)
signers = require(Permission.REPORTS_SIGN)
managers = require(Permission.ORG_MANAGE)

MAX_ENVELOPE = 64 * 1024 * 1024


def _download(content: str, media: str, filename: str) -> Response:
    return Response(content.encode("utf-8"), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


class SnapshotIn(BaseModel):
    label: str | None = Field(default=None, max_length=160)
    system_id: str | None = None


class VerifyIn(BaseModel):
    envelope: dict[str, Any] | str
    public_key: str | None = Field(default=None, max_length=10_000)


@router.get("/formats")
def formats(_: Principal = Depends(readers)) -> dict[str, Any]:
    return {"formats": [{"id": k, **v} for k, v in service.FORMATS.items()]}


@router.get("/export")
def export(request: Request, format: str = Query(...), system: str | None = None,
           principal: Principal = Depends(readers), db: Session = Depends(get_db)) -> Response:
    return _download(*service.export(db, principal, format, system, client_ip(request)))


class ExportIn(BaseModel):
    kind: Literal["inventory", "snapshot", "key"] = "inventory"
    format: str | None = Field(default=None, max_length=32)
    system_id: str | None = None
    snapshot_id: str | None = None
    part: Literal["cbom", "envelope"] | None = None


class LocationIn(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


@router.get("/exports")
def exports(_: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.list_exports(db)


@router.post("/exports", status_code=201)
def create_export(body: ExportIn, request: Request, principal: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.create_export(db, principal, kind=body.kind, fmt=body.format, system_id=body.system_id,
                                 snapshot_id=body.snapshot_id, part=body.part, ip=client_ip(request))


@router.get("/exports/location")
def export_location(_: Principal = Depends(readers)) -> dict[str, Any]:
    return library.describe()


@router.put("/exports/location")
def set_export_location(body: LocationIn, _: Principal = Depends(readers)) -> dict[str, Any]:
    return library.set_location(body.path)


@router.delete("/exports/location")
def reset_export_location(_: Principal = Depends(readers)) -> dict[str, Any]:
    return library.reset_location()


@router.post("/exports/location/open")
def open_export_location(_: Principal = Depends(readers)) -> dict[str, Any]:
    return library.open_folder()


@router.get("/exports/{export_id}/file")
def export_file(export_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> Response:
    data, media, filename = service.export_file(db, export_id)
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.post("/exports/{export_id}/reveal", status_code=204)
def reveal_export(export_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> Response:
    service.reveal_export(db, export_id)
    return Response(status_code=204)


@router.delete("/exports/{export_id}", status_code=204)
def remove_export(export_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> Response:
    service.remove_export(db, export_id)
    return Response(status_code=204)


@router.get("/snapshots")
def snapshots(system: str | None = None, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"items": service.list_snapshots(db, system_id=system)}


@router.post("/snapshots", status_code=201)
def create_snapshot(body: SnapshotIn, request: Request, principal: Principal = Depends(signers),
                    db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.create_snapshot(db, principal, label=body.label, system_id=body.system_id, ip=client_ip(request))


@router.get("/snapshots/{snapshot_id}")
def snapshot(snapshot_id: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.snapshot_detail(db, snapshot_id)


@router.get("/snapshots/{snapshot_id}/{part}")
def snapshot_file(snapshot_id: str, part: str, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> Response:
    return _download(*service.snapshot_file(db, snapshot_id, part))


@router.get("/drift")
def drift(base: str, head: str | None = None, _: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.drift_between(db, base, head)


@router.get("/key")
def key(_: Principal = Depends(readers)) -> dict[str, Any]:
    return service.key_info()


@router.get("/key.pem")
def key_pem(_: Principal = Depends(readers)) -> Response:
    info = service.key_info()
    return _download(info["public_key_pem"], "application/x-pem-file", "falcon-attestation.pub.pem")


@router.post("/key/rotate")
def rotate_key(request: Request, principal: Principal = Depends(managers), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.rotate_key(db, principal, client_ip(request))


@router.post("/verify")
def verify(body: VerifyIn, _: Principal = Depends(readers)) -> dict[str, Any]:
    return service.verify_envelope(body.envelope, body.public_key)
