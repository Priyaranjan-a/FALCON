"""Overview: one read-model that composes the organisation's posture."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ..discovery import service as discovery
from ..discovery.models import Scan
from ..horizon import milestones
from ..horizon.model import format_decimal_year
from ..identity.guard import require
from ..risk import service as risk
from ..identity.models import User
from ..organisation.service import organisation_payload, require_organisation, threat_model
from ..systems import service as systems
from ..systems.models import System

router = APIRouter(prefix="/api/v1/overview", tags=["Overview"])


@router.get("")
def overview(_: Principal = Depends(require(Permission.SYSTEMS_READ)), db: Session = Depends(get_db)) -> dict[str, Any]:
    org = require_organisation(db)
    model = threat_model(org)
    summary = systems.summary(db, model)
    members = db.scalar(select(func.count()).select_from(User).where(User.status != "disabled")) or 0
    unowned = db.scalar(
        select(func.count()).select_from(System)
        .where(System.lifecycle != "retired", (System.owner.is_(None)) | (System.owner == ""))
    ) or 0

    scans = db.scalar(select(func.count()).select_from(Scan).where(Scan.status == "succeeded")) or 0

    checklist = [
        {"key": "threat_model", "title": "Set the quantum threat model", "done": True,
         "detail": f"Planning horizon {format_decimal_year(model.planning_year)} at {model.tolerance:.0%} tolerance"},
        {"key": "systems", "title": "Register your systems", "done": summary["active"] > 0,
         "detail": f"{summary['active']} system{'s' if summary['active'] != 1 else ''} registered"},
        {"key": "owners", "title": "Assign an owner to every system", "done": summary["active"] > 0 and unowned == 0,
         "detail": "Every system has an owner" if summary["active"] and not unowned
         else f"{unowned} system{'s' if unowned != 1 else ''} without an owner" if unowned else "Register a system first"},
        {"key": "team", "title": "Invite your team", "done": members > 1,
         "detail": f"{members} member{'s' if members != 1 else ''}"},
        {"key": "discovery", "title": "Run discovery on a system", "done": scans > 0,
         "detail": f"{scans} completed scan{'s' if scans != 1 else ''}" if scans else "Add a source to a system and scan it"},
    ]

    return {
        "organisation": organisation_payload(org),
        "horizon": model.summary(),
        "systems": summary,
        "milestones": milestones.upcoming(limit=6),
        "checklist": checklist,
        "discovery": {
            "inventory": discovery.inventory_summary(db),
            "recent_scans": discovery.list_scans(db, system_id=None, status=None, limit=6),
        },
        "risk": _risk_block(db),
    }


def _risk_block(db: Session) -> dict[str, Any]:
    full = risk.summary(db)
    return {k: full[k] for k in ("bands", "hndl", "total", "assessed")} | {"systems": full["systems"][:5], "top": full["top"][:5]}
