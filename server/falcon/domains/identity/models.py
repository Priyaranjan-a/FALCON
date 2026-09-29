"""Identity: members, their sessions, personal access tokens and invitations.

No secret is stored in plaintext. Session ids, invitation links and access
tokens are persisted as SHA-256 digests; passwords as Argon2id hashes.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...kernel.database import Base, IdMixin, TimestampMixin, UTCDateTime, utcnow


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # invited -> active -> (disabled <-> active)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="invited", index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    failed_sign_ins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_sign_in_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    invited_by: Mapped[str | None] = mapped_column(String(36))

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", cascade="all, delete-orphan", passive_deletes=True)


class UserSession(IdMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))

    user: Mapped[User] = relationship(back_populates="sessions")


class AccessToken(IdMixin, Base):
    __tablename__ = "access_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Invitation(IdMixin, Base):
    __tablename__ = "invitations"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_by: Mapped[str | None] = mapped_column(String(36))
