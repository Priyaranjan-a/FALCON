"""The organisation that owns this FALCON deployment, and its threat model.

A deployment serves exactly one organisation (on-premises and air-gap first),
so this table holds a single row created by the setup assistant.
"""
from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from ...kernel.database import Base, IdMixin, TimestampMixin


class Organisation(IdMixin, TimestampMixin, Base):
    __tablename__ = "organisation"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sector: Mapped[str] = mapped_column(String(48), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2

    # Threat model (see domains.horizon.model).
    crqc_scenario: Mapped[str] = mapped_column(String(16), nullable=False, default="moderate")
    crqc_median_year: Mapped[float | None] = mapped_column(Float)  # custom scenario only
    crqc_uncertainty: Mapped[str | None] = mapped_column(String(16))  # custom scenario only
    risk_tolerance: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
