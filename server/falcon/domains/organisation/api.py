"""First-run setup and organisation endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ... import __version__
from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ...kernel.http import client_ip
from ...kernel.validation import Email
from ...settings import get_settings
from ..horizon.api import catalogue as horizon_catalogue
from ..identity.api import account_payload
from ..identity.guard import current_principal, require, set_session_cookie
from ..identity.schemas import clean_person_name
from . import service
from .schemas import SECTORS, OrganisationProfileIn, OrganisationProfilePatch, ThreatModelIn

setup = APIRouter(prefix="/api/v1/setup", tags=["Setup"])
organisation = APIRouter(prefix="/api/v1/organisation", tags=["Organisation"])


class OwnerIn(BaseModel):
    email: Email
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return clean_person_name(value)


class SetupIn(BaseModel):
    organisation: OrganisationProfileIn
    threat_model: ThreatModelIn
    owner: OwnerIn


@setup.get("")
def setup_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    initialised = service.is_initialised(db)
    status: dict[str, Any] = {"initialised": initialised, "version": __version__, "desktop": get_settings().desktop}
    if not initialised:
        # The setup assistant needs the vocabulary before anyone can sign in.
        status["sectors"] = list(SECTORS)
        status["horizon"] = horizon_catalogue()
    return status


@setup.post("", status_code=201)
def run_setup(payload: SetupIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _, owner, secret = service.run_setup(
        db,
        profile=payload.organisation,
        threat=payload.threat_model,
        email=str(payload.owner.email),
        name=payload.owner.name,
        password=payload.owner.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, secret)
    return account_payload(db, owner)


@organisation.get("")
def get_organisation(_: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict[str, Any]:
    return service.organisation_payload(service.require_organisation(db))


@organisation.patch("")
def update_organisation(
    payload: OrganisationProfilePatch,
    request: Request,
    principal: Principal = Depends(require(Permission.ORG_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return service.organisation_payload(service.update_profile(db, principal, payload, client_ip(request)))


@organisation.put("/threat-model")
def update_threat_model(
    payload: ThreatModelIn,
    request: Request,
    principal: Principal = Depends(require(Permission.THREAT_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return service.organisation_payload(service.update_threat_model(db, principal, payload, client_ip(request)))
