"""Request authentication and authorisation.

Two credential kinds:

* **Session cookie** (the console). ``HttpOnly`` so scripts cannot read it and
  ``SameSite=Strict`` so other sites cannot send it. As defence in depth,
  state-changing requests must also carry ``X-Falcon-Request: 1``; browsers
  refuse to attach custom headers to cross-origin requests without a CORS
  pre-flight, which FALCON never grants.
* **Personal access token** (automation): ``Authorization: Bearer flc_…``.
"""
from __future__ import annotations

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from ...kernel.access import Permission, Principal
from ...kernel.database import get_db
from ...kernel.problems import Problem
from ...kernel.security import TOKEN_PREFIX
from ...settings import get_settings
from . import service

CSRF_HEADER = "x-falcon-request"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def session_cookie_name() -> str:
    # The __Host- prefix pins the cookie to this exact origin; it requires Secure.
    return "__Host-falcon_session" if get_settings().cookies_secure else "falcon_session"


def set_session_cookie(response: Response, secret: str) -> None:
    settings = get_settings()
    response.set_cookie(
        session_cookie_name(), secret,
        max_age=settings.session_absolute_hours * 3600,
        httponly=True, secure=settings.cookies_secure, samesite="strict", path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        session_cookie_name(), path="/", httponly=True, secure=settings.cookies_secure, samesite="strict",
    )


def _unauthenticated(detail: str = "Sign in to continue.") -> Problem:
    return Problem(401, detail, code="unauthenticated", headers={"WWW-Authenticate": 'Bearer realm="falcon"'})


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        plaintext = authorization[7:].strip()
        if not plaintext.startswith(TOKEN_PREFIX):
            raise _unauthenticated("The access token is not valid.")
        resolved = service.resolve_token(db, plaintext)
        if resolved is None:
            raise _unauthenticated("The access token is not valid or has expired.")
        token, user = resolved
        return service.principal_for(user, via="token", token_id=token.id)

    secret = request.cookies.get(session_cookie_name())
    if not secret:
        raise _unauthenticated()
    resolved = service.resolve_session(db, secret)
    if resolved is None:
        raise _unauthenticated("Your session has ended. Sign in again.")
    if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise Problem(403, "Request rejected: missing request-origin header.", code="csrf_rejected")
    session, user = resolved
    return service.principal_for(user, via="session", session_id=session.id)


def require(permission: Permission):
    """Dependency factory: the caller must hold ``permission``."""

    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.can(permission):
            raise Problem(403, "Your role does not allow this action.", code="forbidden")
        return principal

    dependency.__name__ = f"require_{permission.value.replace('.', '_')}"
    return dependency


def require_session(principal: Principal = Depends(current_principal)) -> Principal:
    """For account-level actions that access tokens must never perform."""
    if principal.via != "session":
        raise Problem(403, "This action requires an interactive session.", code="session_required")
    return principal
