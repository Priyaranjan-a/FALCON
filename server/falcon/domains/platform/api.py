"""Platform health and build information."""
from __future__ import annotations

import platform
import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ... import __version__
from ...kernel.access import Principal
from ...kernel.database import get_db, get_engine
from ...kernel.problems import Problem
from ..horizon.milestones import catalogue
from ..identity.guard import current_principal

router = APIRouter(prefix="/api/v1/platform", tags=["Platform"])

_STARTED = time.monotonic()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report, do not leak internals
        raise Problem(503, "The database is not reachable.", code="database_unavailable") from exc
    return {"status": "ok"}


@router.get("/about")
def about(_: Principal = Depends(current_principal)) -> dict[str, Any]:
    from cryptography import __version__ as cryptography_version
    from cryptography.hazmat.backends.openssl.backend import backend

    return {
        "product": "FALCON",
        "version": __version__,
        "database": get_engine().dialect.name,
        "python": platform.python_version(),
        "cryptography": cryptography_version,
        "openssl": backend.openssl_version_text(),
        "uptime_seconds": int(time.monotonic() - _STARTED),
        "knowledge": {"regulatory_milestones": catalogue()["version"]},
    }
