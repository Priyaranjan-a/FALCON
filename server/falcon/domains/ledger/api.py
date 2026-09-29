"""Audit ledger endpoints: browse events and verify the hash chain."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...kernel import audit
from ...kernel.access import Permission, Principal
from ...kernel.audit import AuditEvent, AuditHead
from ...kernel.database import get_db
from ...kernel.http import client_ip
from ..identity.guard import require
from ..identity.service import actor_fields

router = APIRouter(prefix="/api/v1/audit", tags=["Audit ledger"])

readers = require(Permission.AUDIT_READ)

CATEGORIES = {
    "identity": "identity.",
    "members": "member.",
    "tokens": "token.",
    "organisation": ("organisation.", "threat_model."),
    "systems": "system.",
    "discovery": ("source.", "scan."),
    "reports": "report.",
    "ledger": "ledger.",
}


def _event(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.id, "seq": e.seq, "occurred_at": e.occurred_at, "actor_id": e.actor_id,
        "actor_label": e.actor_label, "action": e.action, "target_type": e.target_type,
        "target_id": e.target_id, "summary": e.summary, "detail": e.detail, "ip": e.ip,
        "hash": e.hash, "prev_hash": e.prev_hash,
    }


@router.get("")
def list_events(
    before: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    target: str | None = Query(default=None, max_length=64),
    _: Principal = Depends(readers),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit + 1)
    if before:
        stmt = stmt.where(AuditEvent.seq < before)
    if category in CATEGORIES:
        prefixes = CATEGORIES[category]
        prefixes = prefixes if isinstance(prefixes, tuple) else (prefixes,)
        stmt = stmt.where(or_(*(AuditEvent.action.startswith(p) for p in prefixes)))
    if target:
        # A system's history includes its sources and scans, which name it in their detail.
        stmt = stmt.where(or_(AuditEvent.target_id == target, AuditEvent.detail["system_id"].as_string() == target))
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(AuditEvent.summary.ilike(needle), AuditEvent.actor_label.ilike(needle)))
    rows = db.scalars(stmt).all()
    more = len(rows) > limit
    rows = rows[:limit]
    head = db.get(AuditHead, 1)
    return {
        "events": [_event(e) for e in rows],
        "next_before": rows[-1].seq if more and rows else None,
        "head": {"seq": head.seq, "hash": head.hash} if head else None,
        "categories": list(CATEGORIES),
    }


@router.post("/verify")
def verify(request: Request, principal: Principal = Depends(readers), db: Session = Depends(get_db)) -> dict[str, Any]:
    result = audit.verify_chain(db)
    outcome = "intact" if result["valid"] else f"broken at event {result['broken_at']}"
    audit.append(
        db, action="ledger.verified",
        summary=f"{principal.name} verified the audit ledger: {result['checked']} events, {outcome}",
        target_type="ledger", detail={k: v for k, v in result.items() if k != "head_hash"},
        **actor_fields(principal, client_ip(request)),
    )
    db.commit()
    return result
