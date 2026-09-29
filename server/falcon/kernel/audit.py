"""Tamper-evident audit ledger.

Every event carries ``hash = SHA-256(canonical(event) || prev_hash)``. Altering,
deleting or re-ordering any committed event breaks every hash after it, which
``verify_chain`` detects.

Events are appended inside the caller's transaction, so an audited change and
its audit record commit (or roll back) together. The single ``audit_head`` row
serialises writers: ``append`` first *updates* that row, which takes the
database write lock (SQLite) or the row lock (PostgreSQL) before the previous
hash is read. Two concurrent writers can therefore never fork the chain.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, String, Text, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, IdMixin, UTCDateTime, utcnow

GENESIS_HASH = "0" * 64


class AuditEvent(IdMixin, Base):
    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditHead(Base):
    __tablename__ = "audit_head"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, default=GENESIS_HASH)


def _canonical(event: AuditEvent) -> bytes:
    payload = {
        "seq": event.seq,
        "occurred_at": event.occurred_at.isoformat(timespec="microseconds"),
        "actor_id": event.actor_id,
        "actor_label": event.actor_label,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "summary": event.summary,
        "detail": event.detail,
        "ip": event.ip,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def compute_hash(event: AuditEvent, prev_hash: str) -> str:
    return hashlib.sha256(_canonical(event) + prev_hash.encode("ascii")).hexdigest()


def append(
    db: Session,
    *,
    action: str,
    summary: str,
    actor_id: str | None = None,
    actor_label: str = "system",
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditEvent:
    """Append an event to the ledger within the caller's transaction."""
    row = db.execute(
        update(AuditHead).where(AuditHead.id == 1).values(seq=AuditHead.seq + 1)
        .returning(AuditHead.seq, AuditHead.hash)
    ).one()
    seq, prev_hash = row.seq, row.hash
    event = AuditEvent(
        seq=seq,
        occurred_at=utcnow(),
        actor_id=actor_id,
        actor_label=actor_label,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        detail=detail,
        ip=ip,
        prev_hash=prev_hash,
    )
    event.hash = compute_hash(event, prev_hash)
    db.add(event)
    db.execute(update(AuditHead).where(AuditHead.id == 1).values(hash=event.hash))
    return event


def verify_chain(db: Session, batch: int = 1000) -> dict[str, Any]:
    """Recompute the full chain. Reports the first broken sequence, if any."""
    head = db.get(AuditHead, 1)
    expected_prev = GENESIS_HASH
    expected_seq = 1
    checked = 0
    last_seq = 0
    while True:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.seq > last_seq).order_by(AuditEvent.seq).limit(batch)
        ).all()
        if not events:
            break
        for event in events:
            problem = None
            if event.seq != expected_seq:
                problem = f"sequence gap: expected {expected_seq}, found {event.seq}"
            elif event.prev_hash != expected_prev:
                problem = "link to the previous event is broken"
            elif compute_hash(event, event.prev_hash) != event.hash:
                problem = "event content does not match its hash"
            if problem:
                return {
                    "valid": False, "checked": checked, "broken_at": event.seq,
                    "reason": problem, "head_seq": head.seq if head else None,
                }
            expected_prev = event.hash
            expected_seq += 1
            checked += 1
            last_seq = event.seq
    if head is not None and (head.seq != checked or head.hash != expected_prev):
        return {
            "valid": False, "checked": checked, "broken_at": checked + 1,
            "reason": "ledger head does not match the last event (events removed from the end)",
            "head_seq": head.seq,
        }
    return {"valid": True, "checked": checked, "broken_at": None, "reason": None,
            "head_seq": head.seq if head else 0, "head_hash": expected_prev}
