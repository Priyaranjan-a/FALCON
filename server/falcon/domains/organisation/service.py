"""Organisation profile, threat model and first-run setup."""
from __future__ import annotations

import threading

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...kernel import audit
from ...kernel.access import Principal
from ...kernel.problems import Problem
from ..horizon.model import ThreatModel, format_decimal_year
from ..identity import service as identity
from ..identity.models import User
from .models import Organisation
from .schemas import OrganisationProfileIn, OrganisationProfilePatch, ThreatModelIn

_setup_lock = threading.Lock()


def get_organisation(db: Session) -> Organisation | None:
    return db.scalar(select(Organisation).limit(1))


def require_organisation(db: Session) -> Organisation:
    org = get_organisation(db)
    if org is None:
        raise Problem(409, "FALCON has not been set up yet.", code="setup_required")
    return org


def is_initialised(db: Session) -> bool:
    return get_organisation(db) is not None


def threat_model(org: Organisation) -> ThreatModel:
    return ThreatModel.build(org.crqc_scenario, org.crqc_median_year, org.crqc_uncertainty, org.risk_tolerance)


def run_setup(
    db: Session,
    *,
    profile: OrganisationProfileIn,
    threat: ThreatModelIn,
    email: str,
    name: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[Organisation, User, str]:
    with _setup_lock:
        if is_initialised(db) or db.scalar(select(func.count()).select_from(User)):
            raise Problem(409, "FALCON is already set up. Sign in instead.", code="already_initialised")
        org = Organisation(
            name=profile.name, sector=profile.sector, country=profile.country,
            crqc_scenario=threat.crqc_scenario, crqc_median_year=threat.crqc_median_year,
            crqc_uncertainty=threat.crqc_uncertainty, risk_tolerance=threat.risk_tolerance,
        )
        db.add(org)
        owner = identity.create_owner(db, email=email, name=name, password=password)
        session, secret = identity.start_session(db, owner, ip, user_agent)
        db.flush()
        audit.append(
            db, action="organisation.created", summary=f"{owner.name} set up FALCON for {org.name}",
            actor_id=owner.id, actor_label=owner.name, target_type="organisation", target_id=org.id,
            detail={"sector": org.sector, "country": org.country, "scenario": org.crqc_scenario,
                    "risk_tolerance": org.risk_tolerance},
            ip=ip,
        )
        db.commit()
        return org, owner, secret


def update_profile(db: Session, principal: Principal, patch: OrganisationProfilePatch, ip: str | None) -> Organisation:
    org = require_organisation(db)
    changes = {}
    for field, value in patch.model_dump(exclude_unset=True, exclude_none=True).items():
        if getattr(org, field) != value:
            changes[field] = {"from": getattr(org, field), "to": value}
            setattr(org, field, value)
    if changes:
        audit.append(
            db, action="organisation.updated",
            summary=f"{principal.name} updated the organisation profile ({', '.join(changes)})",
            target_type="organisation", target_id=org.id, detail=changes,
            **identity.actor_fields(principal, ip),
        )
        db.commit()
    return org


def update_threat_model(db: Session, principal: Principal, data: ThreatModelIn, ip: str | None) -> Organisation:
    org = require_organisation(db)
    before = threat_model(org)
    org.crqc_scenario = data.crqc_scenario
    org.crqc_median_year = data.crqc_median_year
    org.crqc_uncertainty = data.crqc_uncertainty
    org.risk_tolerance = data.risk_tolerance
    after = threat_model(org)
    if before.summary() | {"evaluated_at": 0} != after.summary() | {"evaluated_at": 0}:
        audit.append(
            db, action="threat_model.updated",
            summary=(
                f"{principal.name} set the threat model to {after.scenario} at {after.tolerance:.0%} tolerance "
                f"(planning horizon {format_decimal_year(after.planning_year)})"
            ),
            target_type="organisation", target_id=org.id,
            detail={
                "from": {"scenario": before.scenario, "median_year": before.median_year, "sigma": before.sigma,
                         "tolerance": before.tolerance, "planning_year": round(before.planning_year, 2)},
                "to": {"scenario": after.scenario, "median_year": after.median_year, "sigma": after.sigma,
                       "tolerance": after.tolerance, "planning_year": round(after.planning_year, 2)},
            },
            **identity.actor_fields(principal, ip),
        )
        db.commit()
    return org


def organisation_payload(org: Organisation) -> dict:
    model = threat_model(org)
    return {
        "id": org.id,
        "name": org.name,
        "sector": org.sector,
        "country": org.country,
        "created_at": org.created_at,
        "threat_model": {
            "crqc_scenario": org.crqc_scenario,
            "crqc_median_year": org.crqc_median_year,
            "crqc_uncertainty": org.crqc_uncertainty,
            "risk_tolerance": org.risk_tolerance,
            **{k: v for k, v in model.summary().items() if k not in ("scenario", "tolerance")},
        },
    }
