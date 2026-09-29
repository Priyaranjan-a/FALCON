"""Quantum threat horizon endpoints."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...kernel.access import Principal
from ...kernel.database import get_db
from ...kernel.problems import Problem
from ..identity.guard import current_principal
from ..organisation.service import require_organisation, threat_model
from . import milestones
from .model import SCENARIOS, TOLERANCES, UNCERTAINTY, ThreatModel

router = APIRouter(prefix="/api/v1/horizon", tags=["Threat horizon"])


def catalogue() -> dict[str, Any]:
    return {
        "scenarios": SCENARIOS,
        "uncertainty": UNCERTAINTY,
        "tolerances": list(TOLERANCES),
    }


def _document(model: ThreatModel) -> dict[str, Any]:
    return {"model": model.summary(), "curve": model.curve()}


@router.get("")
def horizon(_: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict[str, Any]:
    model = threat_model(require_organisation(db))
    return {**_document(model), "catalogue": catalogue()}


@router.get("/evaluate")
def evaluate(
    scenario: Literal["aggressive", "moderate", "conservative", "custom"] = "moderate",
    median_year: float | None = Query(default=None, ge=2027, le=2070),
    uncertainty: Literal["narrow", "moderate", "wide"] | None = None,
    tolerance: float = 0.05,
    _: Principal = Depends(current_principal),
) -> dict[str, Any]:
    """Evaluate a candidate threat model without saving it."""
    if tolerance not in TOLERANCES:
        raise Problem(422, "Unsupported risk tolerance.", code="validation_failed")
    if scenario == "custom" and median_year is None:
        raise Problem(422, "A custom scenario needs a median arrival year.", code="validation_failed")
    return _document(ThreatModel.build(scenario, median_year, uncertainty, tolerance))


@router.get("/milestones")
def regulatory_milestones(_: Principal = Depends(current_principal)) -> dict[str, Any]:
    return milestones.catalogue()
