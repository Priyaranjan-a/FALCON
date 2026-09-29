"""Identity use-cases. Every state change writes to the audit ledger in the
same transaction, then commits."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ...kernel import audit
from ...kernel.access import Principal, Role, permissions_for
from ...kernel.database import utcnow
from ...kernel.problems import Problem, conflict, forbidden, not_found
from ...kernel.security import (
    digest, hash_password, new_access_token, new_secret, password_needs_rehash,
    password_problems, verify_password,
)
from ...settings import get_settings
from .models import AccessToken, Invitation, User, UserSession

TOUCH_INTERVAL = timedelta(seconds=60)


# --------------------------------------------------------------------------- helpers

def actor_fields(principal: Principal | None, ip: str | None = None) -> dict:
    if principal is None:
        return {"actor_id": None, "actor_label": "system", "ip": ip}
    return {"actor_id": principal.user_id, "actor_label": principal.name, "ip": ip}


def principal_for(user: User, *, via: str, session_id: str | None = None, token_id: str | None = None) -> Principal:
    return Principal(
        user_id=user.id, email=user.email, name=user.name, role=Role(user.role), via=via,
        session_id=session_id, token_id=token_id, permissions=permissions_for(user.role),
    )


def require_password_policy(password: str, *, email: str, name: str) -> None:
    problems = password_problems(password, email=email, name=name)
    if problems:
        raise Problem(
            422, problems[0], code="weak_password",
            errors=[{"field": "password", "message": p} for p in problems],
        )


def _user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


# --------------------------------------------------------------------------- sessions

def start_session(db: Session, user: User, ip: str | None, user_agent: str | None) -> tuple[UserSession, str]:
    secret = new_secret()
    now = utcnow()
    session = UserSession(
        user_id=user.id,
        secret_hash=digest(secret),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=get_settings().session_absolute_hours),
        ip=ip,
        user_agent=(user_agent or "")[:400] or None,
    )
    db.add(session)
    return session, secret


def resolve_session(db: Session, secret: str) -> tuple[UserSession, User] | None:
    session = db.scalar(select(UserSession).where(UserSession.secret_hash == digest(secret)))
    if session is None or session.revoked_at is not None:
        return None
    now = utcnow()
    idle = timedelta(minutes=get_settings().session_idle_minutes)
    if session.expires_at <= now or session.last_seen_at + idle <= now:
        return None
    user = session.user
    if user.status != "active":
        return None
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return session, user


def resolve_token(db: Session, plaintext: str) -> tuple[AccessToken, User] | None:
    token = db.scalar(select(AccessToken).where(AccessToken.secret_hash == digest(plaintext)))
    if token is None or token.revoked_at is not None:
        return None
    now = utcnow()
    if token.expires_at is not None and token.expires_at <= now:
        return None
    user = db.get(User, token.user_id)
    if user is None or user.status != "active":
        return None
    if token.last_used_at is None or now - token.last_used_at >= TOUCH_INTERVAL:
        token.last_used_at = now
        db.commit()
    return token, user


def _revoke_sessions(db: Session, user_id: str, *, keep: str | None = None) -> int:
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    if keep:
        stmt = stmt.where(UserSession.id != keep)
    return db.execute(stmt).rowcount or 0


def _revoke_tokens(db: Session, user_id: str) -> int:
    return db.execute(
        update(AccessToken)
        .where(AccessToken.user_id == user_id, AccessToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    ).rowcount or 0


# --------------------------------------------------------------------------- sign in / out

def sign_in(db: Session, email: str, password: str, ip: str | None, user_agent: str | None) -> tuple[User, str]:
    settings = get_settings()
    user = _user_by_email(db, email)
    now = utcnow()

    if user is not None and user.locked_until is not None and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise Problem(
            423, f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            code="account_locked",
        )

    usable_hash = user.password_hash if user is not None and user.status == "active" else None
    if not verify_password(password, usable_hash):
        if user is not None:
            user.failed_sign_ins += 1
            if user.failed_sign_ins >= settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
                user.failed_sign_ins = 0
        audit.append(
            db, action="identity.sign_in_failed", summary=f"Failed sign-in for {email.strip().lower()}",
            actor_id=user.id if user else None, actor_label=email.strip().lower()[:254],
            target_type="user", target_id=user.id if user else None, ip=ip,
        )
        db.commit()
        raise Problem(401, "The email or password is incorrect.", code="invalid_credentials")

    user.failed_sign_ins = 0
    user.locked_until = None
    user.last_sign_in_at = now
    if password_needs_rehash(user.password_hash or ""):
        user.password_hash = hash_password(password)
    session, secret = start_session(db, user, ip, user_agent)
    db.flush()
    audit.append(
        db, action="identity.signed_in", summary=f"{user.name} signed in",
        actor_id=user.id, actor_label=user.name, target_type="session", target_id=session.id, ip=ip,
    )
    db.commit()
    return user, secret


def sign_out(db: Session, principal: Principal, ip: str | None) -> None:
    if principal.session_id:
        session = db.get(UserSession, principal.session_id)
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            audit.append(
                db, action="identity.signed_out", summary=f"{principal.name} signed out",
                target_type="session", target_id=session.id, **actor_fields(principal, ip),
            )
            db.commit()


def list_sessions(db: Session, principal: Principal) -> list[UserSession]:
    now = utcnow()
    idle = timedelta(minutes=get_settings().session_idle_minutes)
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == principal.user_id, UserSession.revoked_at.is_(None), UserSession.expires_at > now)
        .order_by(UserSession.last_seen_at.desc())
    ).all()
    return [s for s in rows if s.last_seen_at + idle > now]


def revoke_session(db: Session, principal: Principal, session_id: str, ip: str | None) -> None:
    session = db.get(UserSession, session_id)
    if session is None or session.user_id != principal.user_id or session.revoked_at is not None:
        raise not_found("Session")
    session.revoked_at = utcnow()
    audit.append(
        db, action="identity.session_revoked", summary=f"{principal.name} signed out a device",
        target_type="session", target_id=session.id, **actor_fields(principal, ip),
    )
    db.commit()


def revoke_other_sessions(db: Session, principal: Principal, ip: str | None) -> int:
    count = _revoke_sessions(db, principal.user_id, keep=principal.session_id)
    if count:
        audit.append(
            db, action="identity.sessions_revoked",
            summary=f"{principal.name} signed out {count} other device{'s' if count != 1 else ''}",
            target_type="user", target_id=principal.user_id, detail={"count": count},
            **actor_fields(principal, ip),
        )
    db.commit()
    return count


def change_password(db: Session, principal: Principal, current: str, new: str, ip: str | None) -> None:
    user = db.get(User, principal.user_id)
    if user is None or not verify_password(current, user.password_hash):
        raise Problem(
            422, "The current password is incorrect.", code="invalid_current_password",
            errors=[{"field": "current_password", "message": "The current password is incorrect."}],
        )
    if verify_password(new, user.password_hash):
        raise Problem(422, "Choose a password you have not used here before.", code="password_reused",
                      errors=[{"field": "new_password", "message": "Choose a different password."}])
    require_password_policy(new, email=user.email, name=user.name)
    user.password_hash = hash_password(new)
    user.password_changed_at = utcnow()
    revoked = _revoke_sessions(db, user.id, keep=principal.session_id)
    audit.append(
        db, action="identity.password_changed", summary=f"{user.name} changed their password",
        target_type="user", target_id=user.id, detail={"other_sessions_revoked": revoked},
        **actor_fields(principal, ip),
    )
    db.commit()


def update_profile(db: Session, principal: Principal, name: str, ip: str | None) -> User:
    user = db.get(User, principal.user_id)
    if user is None:
        raise not_found("Account")
    if user.name != name:
        previous = user.name
        user.name = name
        audit.append(
            db, action="identity.profile_updated", summary=f"{previous} is now {name}",
            target_type="user", target_id=user.id, detail={"name": {"from": previous, "to": name}},
            **actor_fields(principal, ip),
        )
        db.commit()
    return user


# --------------------------------------------------------------------------- members

def create_owner(db: Session, *, email: str, name: str, password: str) -> User:
    require_password_policy(password, email=email, name=name)
    now = utcnow()
    user = User(
        email=email.strip().lower(), name=name, role=Role.OWNER.value, status="active",
        password_hash=hash_password(password), password_changed_at=now,
    )
    db.add(user)
    db.flush()
    return user


def list_members(db: Session) -> list[tuple[User, Invitation | None]]:
    users = db.scalars(select(User).order_by(User.created_at)).all()
    pending = {
        inv.user_id: inv
        for inv in db.scalars(select(Invitation).where(Invitation.consumed_at.is_(None))).all()
    }
    return [(u, pending.get(u.id) if u.status == "invited" else None) for u in users]


def _issue_invitation(db: Session, user: User, created_by: str | None) -> tuple[Invitation, str]:
    db.execute(
        update(Invitation)
        .where(Invitation.user_id == user.id, Invitation.consumed_at.is_(None))
        .values(consumed_at=utcnow())
    )
    secret = new_secret()
    invitation = Invitation(
        user_id=user.id, secret_hash=digest(secret), created_by=created_by,
        expires_at=utcnow() + timedelta(hours=get_settings().invitation_valid_hours),
    )
    db.add(invitation)
    return invitation, secret


def invite_member(db: Session, principal: Principal, *, email: str, name: str, role: str, ip: str | None) -> tuple[User, Invitation, str]:
    email = email.strip().lower()
    if _user_by_email(db, email) is not None:
        raise conflict(f"{email} is already a member.", code="member_exists")
    user = User(email=email, name=name, role=role, status="invited", invited_by=principal.user_id)
    db.add(user)
    db.flush()
    invitation, secret = _issue_invitation(db, user, principal.user_id)
    audit.append(
        db, action="member.invited", summary=f"{principal.name} invited {name} as {role.replace('_', ' ')}",
        target_type="user", target_id=user.id, detail={"email": email, "role": role},
        **actor_fields(principal, ip),
    )
    db.commit()
    return user, invitation, secret


def issue_sign_in_link(db: Session, principal: Principal, user_id: str, ip: str | None) -> tuple[Invitation, str]:
    """A fresh one-time link. For an invited member it replaces the invitation;
    for an existing member it is an access reset: the password is cleared and
    every session and token is revoked until the link is used."""
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Member")
    if user.role == Role.OWNER.value:
        raise forbidden("The owner's access cannot be reset from the console.")
    if user.id == principal.user_id:
        raise forbidden("Change your own password from Settings.")
    reset = user.status != "invited"
    if reset:
        user.status = "invited"
        user.password_hash = None
        user.failed_sign_ins = 0
        user.locked_until = None
        _revoke_sessions(db, user.id)
        _revoke_tokens(db, user.id)
    invitation, secret = _issue_invitation(db, user, principal.user_id)
    audit.append(
        db,
        action="member.access_reset" if reset else "member.invitation_reissued",
        summary=(f"{principal.name} reset {user.name}'s access and issued a new sign-in link" if reset
                 else f"{principal.name} issued a new invitation link for {user.name}"),
        target_type="user", target_id=user.id, **actor_fields(principal, ip),
    )
    db.commit()
    return invitation, secret


def _open_invitation(db: Session, secret: str) -> tuple[Invitation, User]:
    invitation = db.scalar(select(Invitation).where(Invitation.secret_hash == digest(secret)))
    if invitation is None or invitation.consumed_at is not None:
        raise Problem(404, "This invitation link is not valid. Ask an administrator for a new one.", code="invitation_invalid")
    if invitation.expires_at <= utcnow():
        raise Problem(410, "This invitation link has expired. Ask an administrator for a new one.", code="invitation_expired", title="Expired")
    user = db.get(User, invitation.user_id)
    if user is None or user.status != "invited":
        raise Problem(404, "This invitation link is not valid. Ask an administrator for a new one.", code="invitation_invalid")
    return invitation, user


def recover_owner(db: Session) -> tuple[User, Invitation, str]:
    """Operator recovery (``python -m falcon recover-owner``): requires shell
    access to the server, so it is never exposed over HTTP."""
    owner = db.scalar(select(User).where(User.role == Role.OWNER.value))
    if owner is None:
        raise not_found("Owner")
    owner.status = "invited"
    owner.password_hash = None
    owner.failed_sign_ins = 0
    owner.locked_until = None
    _revoke_sessions(db, owner.id)
    _revoke_tokens(db, owner.id)
    invitation, secret = _issue_invitation(db, owner, None)
    audit.append(
        db, action="member.access_reset", summary=f"A server operator reset {owner.name}'s access from the command line",
        actor_label="server operator", target_type="user", target_id=owner.id,
    )
    db.commit()
    return owner, invitation, secret


def invitation_preview(db: Session, secret: str) -> dict:
    invitation, user = _open_invitation(db, secret)
    return {
        "email": user.email, "name": user.name, "role": user.role, "expires_at": invitation.expires_at,
        "returning": user.password_changed_at is not None,
    }


def activate(db: Session, *, secret: str, name: str, password: str, ip: str | None, user_agent: str | None) -> tuple[User, str]:
    invitation, user = _open_invitation(db, secret)
    require_password_policy(password, email=user.email, name=name)
    now = utcnow()
    invitation.consumed_at = now
    user.name = name
    user.password_hash = hash_password(password)
    user.password_changed_at = now
    user.status = "active"
    user.last_sign_in_at = now
    session, session_secret = start_session(db, user, ip, user_agent)
    db.flush()
    audit.append(
        db, action="member.activated", summary=f"{user.name} activated their account",
        actor_id=user.id, actor_label=user.name, target_type="user", target_id=user.id, ip=ip,
    )
    db.commit()
    return user, session_secret


def update_member(db: Session, principal: Principal, user_id: str, *, role: str | None, status: str | None, ip: str | None) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Member")
    if user.role == Role.OWNER.value:
        raise forbidden("The owner's role and status cannot be changed.")
    if user.id == principal.user_id:
        raise forbidden("You cannot change your own role or status.")
    changes: dict[str, dict[str, str]] = {}
    if role is not None and role != user.role:
        changes["role"] = {"from": user.role, "to": role}
        user.role = role
    if status is not None and status != user.status:
        if user.status == "invited":
            raise conflict("Invited members become active by accepting their invitation.", code="member_invited")
        changes["status"] = {"from": user.status, "to": status}
        user.status = status
        if status == "disabled":
            _revoke_sessions(db, user.id)
            _revoke_tokens(db, user.id)
    if changes:
        parts = []
        if "role" in changes:
            parts.append(f"role to {changes['role']['to'].replace('_', ' ')}")
        if "status" in changes:
            parts.append("access " + ("suspended" if changes["status"]["to"] == "disabled" else "restored"))
        audit.append(
            db, action="member.updated", summary=f"{principal.name} changed {user.name}'s " + " and ".join(parts),
            target_type="user", target_id=user.id, detail=changes, **actor_fields(principal, ip),
        )
        db.commit()
    return user


def remove_member(db: Session, principal: Principal, user_id: str, ip: str | None) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("Member")
    if user.role == Role.OWNER.value:
        raise forbidden("The owner cannot be removed.")
    if user.id == principal.user_id:
        raise forbidden("You cannot remove yourself.")
    audit.append(
        db, action="member.removed", summary=f"{principal.name} removed {user.name}",
        target_type="user", target_id=user.id, detail={"email": user.email, "role": user.role},
        **actor_fields(principal, ip),
    )
    db.delete(user)
    db.commit()


# --------------------------------------------------------------------------- access tokens

def list_tokens(db: Session, principal: Principal) -> list[AccessToken]:
    now = utcnow()
    rows = db.scalars(
        select(AccessToken)
        .where(AccessToken.user_id == principal.user_id, AccessToken.revoked_at.is_(None))
        .order_by(AccessToken.created_at.desc())
    ).all()
    return [t for t in rows if t.expires_at is None or t.expires_at > now]


def create_token(db: Session, principal: Principal, *, name: str, expires_in_days: int | None, ip: str | None) -> tuple[AccessToken, str]:
    plaintext, prefix = new_access_token()
    expires_at: datetime | None = utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
    token = AccessToken(
        user_id=principal.user_id, name=name.strip(), prefix=prefix,
        secret_hash=digest(plaintext), expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    audit.append(
        db, action="token.created", summary=f"{principal.name} created access token “{token.name}”",
        target_type="token", target_id=token.id,
        detail={"expires_in_days": expires_in_days, "prefix": prefix}, **actor_fields(principal, ip),
    )
    db.commit()
    return token, plaintext


def revoke_token(db: Session, principal: Principal, token_id: str, ip: str | None) -> None:
    token = db.get(AccessToken, token_id)
    if token is None or token.user_id != principal.user_id or token.revoked_at is not None:
        raise not_found("Access token")
    token.revoked_at = utcnow()
    audit.append(
        db, action="token.revoked", summary=f"{principal.name} revoked access token “{token.name}”",
        target_type="token", target_id=token.id, **actor_fields(principal, ip),
    )
    db.commit()
