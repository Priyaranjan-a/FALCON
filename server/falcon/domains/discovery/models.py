"""Discovery: sources, scans and the cryptographic inventory they build.

    System ─┬─ Source ── Scan ── Occurrence ─┐
            └─ Artefact ◄────────────────────┘ (evidence)
                  └─ ArtefactLink (certificate → key, cloud key → algorithm …)

An artefact is unique per system by fingerprint and keeps its history across
scans; an occurrence records where one scan saw it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ...kernel.database import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow


class Source(IdMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    system_id: Mapped[str] = mapped_column(ForeignKey("systems.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36))
    last_scan_id: Mapped[str | None] = mapped_column(String(36))


class Scan(IdMixin, Base):
    __tablename__ = "scans"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False)
    system_id: Mapped[str] = mapped_column(ForeignKey("systems.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), index=True, nullable=False, default="queued")
    stage: Mapped[str | None] = mapped_column(String(16))
    stage_detail: Mapped[str | None] = mapped_column(String(200))
    files_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_done: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artefact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_artefacts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str | None] = mapped_column(String(36))
    requested_by_label: Mapped[str | None] = mapped_column(String(160))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    queued_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    coverage: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Artefact(IdMixin, Base):
    __tablename__ = "artefacts"
    __table_args__ = (UniqueConstraint("system_id", "fingerprint", name="uq_artefact_system_fingerprint"),)

    system_id: Mapped[str] = mapped_column(ForeignKey("systems.id", ondelete="CASCADE"), index=True, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    family: Mapped[str | None] = mapped_column(String(80), index=True)
    identity: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    quantum: Mapped[str | None] = mapped_column(String(16), index=True)
    classical: Mapped[str | None] = mapped_column(String(16), index=True)
    primitive: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(12), index=True, nullable=False, default="active")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    first_scan_id: Mapped[str | None] = mapped_column(String(36))
    last_scan_id: Mapped[str | None] = mapped_column(String(36), index=True)


class Occurrence(IdMixin, Base):
    __tablename__ = "occurrences"

    artefact_id: Mapped[str] = mapped_column(ForeignKey("artefacts.id", ondelete="CASCADE"), index=True, nullable=False)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer)
    col: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[list[Any] | None] = mapped_column(JSON)
    detector: Mapped[str] = mapped_column(String(40), nullable=False)
    rule: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    function: Mapped[str | None] = mapped_column(String(40))
    via: Mapped[str | None] = mapped_column(String(32))


class ArtefactLink(IdMixin, Base):
    __tablename__ = "artefact_links"
    __table_args__ = (UniqueConstraint("from_id", "to_id", "relation", name="uq_artefact_link"),)

    from_id: Mapped[str] = mapped_column(ForeignKey("artefacts.id", ondelete="CASCADE"), index=True, nullable=False)
    to_id: Mapped[str] = mapped_column(ForeignKey("artefacts.id", ondelete="CASCADE"), index=True, nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)
