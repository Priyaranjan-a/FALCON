"""Database engine, declarative base and session dependency.

* Identifiers are UUIDv7 strings: globally unique and time-ordered, so primary
  key order follows creation order on every backend.
* Timestamps are always timezone-aware UTC, including on SQLite, which does not
  store offsets natively (see ``UTCDateTime``).
* SQLite runs in WAL mode with foreign keys enforced; PostgreSQL gets a sized,
  self-healing connection pool.
"""
from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import DateTime, Engine, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from ..settings import get_settings


def _uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7 for Pythons older than 3.14: 48-bit Unix milliseconds,
    version 7, RFC variant, 74 random bits."""
    ms = time.time_ns() // 1_000_000
    value = (ms & ((1 << 48) - 1)) << 80 | int.from_bytes(os.urandom(10), "big")
    value = (value & ~(0xF << 76)) | (0x7 << 76)
    value = (value & ~(0x3 << 62)) | (0x2 << 62)
    return uuid.UUID(int=value)


_make_uuid7 = getattr(uuid, "uuid7", _uuid7)


def new_id() -> str:
    return str(_make_uuid7())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores UTC and always returns timezone-aware datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not accepted; use utcnow()")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record) -> None:  # pragma: no cover - driver hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})
        _configure_sqlite(engine)
        return engine
    return create_engine(
        url, pool_size=10, max_overflow=20, pool_recycle=1800, pool_pre_ping=True
    )


@lru_cache
def get_engine() -> Engine:
    return build_engine(get_settings().resolved_database_url)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rolled back on error."""
    session = get_sessionmaker()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
