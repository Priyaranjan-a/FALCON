"""Identity endpoints: sign-in, account, sessions, members, access tokens."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ...kernel.access import ASSIGNABLE_ROLES, ROLE_INFO, ROLE_PERMISSIONS, Permission, Principal
from ...kernel.database import get_db
from ...kernel.http import client_ip
from ...kernel.problems import Problem
from ...kernel.ratelimit import SlidingWindowLimiter
from ...settings import get_settings
from ..organisation import service as organisation
from . import service
from .guard import clear_session_cookie, current_principal, require, require_session, set_session_cookie
from .models import User
from .schemas import (
    ActivateIn, InviteIn, MemberOut, MemberPatch, PasswordChangeIn, ProfilePatch, SessionOut,
    SignInIn, TokenIn, TokenOut,
)

auth = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
members = APIRouter(prefix="/api/v1/members", tags=["Members"])
tokens = APIRouter(prefix="/api/v1/tokens", tags=["Access tokens"])

_sign_in_limiter = SlidingWindowLimiter(get_settings().login_rate_per_minute, 60)


def _throttle(request: Request) -> None:
    retry = _sign_in_limiter.hit(client_ip(request) or "unknown")
    if retry is not None:
        raise Problem(
            429, "Too many attempts from this address. Wait a moment and try again.",
            code="rate_limited", headers={"Retry-After": str(int(retry) + 1)},
        )


def account_payload(db: Session, user: User, principal: Principal | None = None) -> dict[str, Any]:
    org = organisation.get_organisation(db)
    return {
        "user": {
            "id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "role_label": ROLE_INFO[user.role]["label"] if user.role in ROLE_INFO else user.role,
            "last_sign_in_at": user.last_sign_in_at, "password_changed_at": user.password_changed_at,
        },
        "permissions": sorted(p.value for p in (principal.permissions if principal else ROLE_PERMISSIONS[user.role])),
        "via": principal.via if principal else "session",
        "organisation": {"id": org.id, "name": org.name} if org else None,
    }


# ----------------------------------------------------------------------------- auth

@auth.post("/sign-in")
def sign_in(payload: SignInIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _throttle(request)
    user, secret = service.sign_in(
        db, payload.email, payload.password, client_ip(request), request.headers.get("user-agent"),
    )
    set_session_cookie(response, secret)
    return account_payload(db, user)


@auth.post("/sign-out", status_code=204)
def sign_out(request: Request, response: Response, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> None:
    service.sign_out(db, principal, client_ip(request))
    clear_session_cookie(response)


@auth.get("/me")
def me(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict[str, Any]:
    user = db.get(User, principal.user_id)
    return account_payload(db, user, principal)


@auth.get("/session")
def session(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Like /me, but a signed-out caller gets 200 with ``null`` rather than 401,
    so the console can check for a session without logging an error."""
    try:
        principal = current_principal(request, db)
    except Problem:
        return {"account": None}
    return {"account": account_payload(db, db.get(User, principal.user_id), principal)}


@auth.patch("/me")
def update_me(payload: ProfilePatch, request: Request, principal: Principal = Depends(require_session), db: Session = Depends(get_db)) -> dict[str, Any]:
    user = service.update_profile(db, principal, payload.name, client_ip(request))
    return account_payload(db, user, principal)


@auth.post("/password", status_code=204)
def change_password(payload: PasswordChangeIn, request: Request, principal: Principal = Depends(require_session), db: Session = Depends(get_db)) -> None:
    service.change_password(db, principal, payload.current_password, payload.new_password, client_ip(request))


@auth.get("/sessions", response_model=list[SessionOut])
def sessions(principal: Principal = Depends(require_session), db: Session = Depends(get_db)) -> list[SessionOut]:
    return [
        SessionOut(
            id=s.id, created_at=s.created_at, last_seen_at=s.last_seen_at, expires_at=s.expires_at,
            ip=s.ip, user_agent=s.user_agent, current=s.id == principal.session_id,
        )
        for s in service.list_sessions(db, principal)
    ]


@auth.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, request: Request, principal: Principal = Depends(require_session), db: Session = Depends(get_db)) -> None:
    if session_id == principal.session_id:
        raise Problem(400, "Use sign out to end the current session.", code="current_session")
    service.revoke_session(db, principal, session_id, client_ip(request))


@auth.delete("/sessions", status_code=200)
def revoke_other_sessions(request: Request, principal: Principal = Depends(require_session), db: Session = Depends(get_db)) -> dict[str, int]:
    return {"revoked": service.revoke_other_sessions(db, principal, client_ip(request))}


@auth.get("/invitations/{token}")
def invitation(token: str, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    _throttle(request)
    preview = service.invitation_preview(db, token)
    org = organisation.get_organisation(db)
    return {**preview, "organisation": org.name if org else None,
            "role_label": ROLE_INFO[preview["role"]]["label"]}


@auth.post("/activate")
def activate(payload: ActivateIn, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    _throttle(request)
    user, secret = service.activate(
        db, secret=payload.token, name=payload.name, password=payload.password,
        ip=client_ip(request), user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, secret)
    return account_payload(db, user)


# ----------------------------------------------------------------------------- roles & members

@members.get("/roles")
def roles(_: Principal = Depends(current_principal)) -> list[dict[str, Any]]:
    return [
        {
            "key": role.value, **ROLE_INFO[role], "assignable": role in ASSIGNABLE_ROLES,
            "permissions": sorted(p.value for p in ROLE_PERMISSIONS[role]),
        }
        for role in ROLE_INFO
    ]


def _member_out(user: User, invitation) -> MemberOut:
    return MemberOut(
        id=user.id, email=user.email, name=user.name, role=user.role, status=user.status,
        created_at=user.created_at, last_sign_in_at=user.last_sign_in_at,
        invitation_expires_at=invitation.expires_at if invitation else None,
    )


def _invitation_link(request: Request, secret: str) -> str:
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    return f"{origin}/activate#{secret}"


@members.get("", response_model=list[MemberOut])
def list_members(_: Principal = Depends(require(Permission.MEMBERS_READ)), db: Session = Depends(get_db)) -> list[MemberOut]:
    return [_member_out(u, inv) for u, inv in service.list_members(db)]


@members.post("", status_code=201)
def invite(payload: InviteIn, request: Request, principal: Principal = Depends(require(Permission.MEMBERS_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    user, invitation, secret = service.invite_member(
        db, principal, email=str(payload.email), name=payload.name, role=payload.role, ip=client_ip(request),
    )
    return {"member": _member_out(user, invitation), "activation_link": _invitation_link(request, secret)}


@members.post("/{user_id}/invitation")
def issue_link(user_id: str, request: Request, principal: Principal = Depends(require(Permission.MEMBERS_MANAGE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    invitation, secret = service.issue_sign_in_link(db, principal, user_id, client_ip(request))
    return {"expires_at": invitation.expires_at, "activation_link": _invitation_link(request, secret)}


@members.patch("/{user_id}", response_model=MemberOut)
def update_member(user_id: str, payload: MemberPatch, request: Request, principal: Principal = Depends(require(Permission.MEMBERS_MANAGE)), db: Session = Depends(get_db)) -> MemberOut:
    user = service.update_member(db, principal, user_id, role=payload.role, status=payload.status, ip=client_ip(request))
    return _member_out(user, None)


@members.delete("/{user_id}", status_code=204)
def remove_member(user_id: str, request: Request, principal: Principal = Depends(require(Permission.MEMBERS_MANAGE)), db: Session = Depends(get_db)) -> None:
    service.remove_member(db, principal, user_id, client_ip(request))


# ----------------------------------------------------------------------------- access tokens

@tokens.get("", response_model=list[TokenOut])
def list_tokens(principal: Principal = Depends(require(Permission.TOKENS_USE)), db: Session = Depends(get_db)) -> list[TokenOut]:
    return [TokenOut.model_validate(t, from_attributes=True) for t in service.list_tokens(db, principal)]


@tokens.post("", status_code=201)
def create_token(payload: TokenIn, request: Request, principal: Principal = Depends(require(Permission.TOKENS_USE)), db: Session = Depends(get_db)) -> dict[str, Any]:
    if principal.via != "session":
        raise Problem(403, "Access tokens can only be created from the console.", code="session_required")
    token, plaintext = service.create_token(
        db, principal, name=payload.name, expires_in_days=payload.expires_in_days, ip=client_ip(request),
    )
    return {"token": TokenOut.model_validate(token, from_attributes=True), "secret": plaintext}


@tokens.delete("/{token_id}", status_code=204)
def revoke_token(token_id: str, request: Request, principal: Principal = Depends(require(Permission.TOKENS_USE)), db: Session = Depends(get_db)) -> None:
    service.revoke_token(db, principal, token_id, client_ip(request))
