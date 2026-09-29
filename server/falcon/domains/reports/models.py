"""Signed CBOM snapshots: the inventory as it stood at a moment, attested."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...kernel.database import Base, IdMixin, UTCDateTime, utcnow


class CbomSnapshot(IdMixin, Base):
    __tablename__ = "cbom_snapshots"

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(160))
    system_id: Mapped[str | None] = mapped_column(String(36), index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of the canonical CBOM
    components: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    cbom: Mapped[str] = mapped_column(Text, nullable=False)  # canonical CycloneDX JSON
    envelope: Mapped[str] = mapped_column(Text, nullable=False)  # DSSE envelope signed with ML-DSA-65
    key_id: Mapped[str] = mapped_column(String(64), nullable=False)


class ReportExport(IdMixin, Base):
    """A file FALCON wrote: to the user's export folder (desktop) or its own library (server)."""

    __tablename__ = "report_exports"

    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(160))
    user_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # inventory | snapshot | key
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    scope: Mapped[str] = mapped_column(String(200), nullable=False)
    system_id: Mapped[str | None] = mapped_column(String(36))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
