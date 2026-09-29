"""The systems register: applications, products and infrastructure whose
cryptography FALCON inventories. Business context lives here, on the system,
because data shelf-life, criticality and exposure are properties of what a
system does, not of any single algorithm inside it."""
from __future__ import annotations

from sqlalchemy import JSON, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...kernel.database import Base, IdMixin, TimestampMixin


class System(IdMixin, TimestampMixin, Base):
    __tablename__ = "systems"

    code: Mapped[str] = mapped_column(String(24), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    environment: Mapped[str] = mapped_column(String(16), nullable=False, default="production")
    exposure: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    criticality: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    data_classification: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    data_shelf_life_years: Mapped[int] = mapped_column(Integer, nullable=False)  # Mosca X
    migration_years: Mapped[float] = mapped_column(Float, nullable=False)  # Mosca Y
    owner: Mapped[str | None] = mapped_column(String(160))
    team: Mapped[str | None] = mapped_column(String(160))
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str | None] = mapped_column(String(36))
