"""First-run demonstration data.

``falcon serve --demo`` (what ``scripts/start`` and ``docker compose`` run)
seeds a fresh installation so it opens as a working platform:

* an organisation and its threat model, and an owner account whose
  credentials are printed at start-up (and documented in the README);
* ten systems with their business context (criticality, exposure, data
  classification, shelf-life, migration time);
* sources on the bundled sample estates, scanned by the real discovery
  engine (so the inventory, risk, migration plan and reports are all live);
* once the scans finish, the post-quantum benchmark lab and a signed CBOM
  snapshot.

Nothing happens on an installation that is already set up. Change the admin
password after signing in (Settings → Password & devices).
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

from .settings import REPO_DIR, get_settings

logger = logging.getLogger("falcon.demo")

ORGANISATION = {"name": "Example National Agency", "sector": "government", "country": "IN"}
ADMIN_NAME = "Aarav Sharma"

SYSTEMS: list[dict[str, Any]] = [
    {"code": "PAY-GW", "name": "Payments Gateway", "kind": "service", "exposure": "external", "criticality": "critical", "data_classification": "restricted",
     "data_shelf_life_years": 10, "migration_years": 2.5, "owner": "Treasury Platform", "team": "Payments Engineering", "tags": ["payments", "pci"],
     "description": "Card and account-to-account payments for citizen services."},
    {"code": "CITIZEN-ID", "name": "Citizen Identity Portal", "kind": "application", "exposure": "external", "criticality": "critical",
     "data_classification": "restricted", "data_shelf_life_years": 15, "migration_years": 3, "owner": "Digital Identity Office", "team": "Identity Platform",
     "tags": ["identity"], "description": "Sign-in, token issuance and identity verification for public services."},
    {"code": "PKI-ROOT", "name": "National Root CA", "kind": "infrastructure", "exposure": "isolated", "criticality": "critical", "data_classification": "secret",
     "data_shelf_life_years": 25, "migration_years": 5, "owner": "PKI Governance Board", "team": "Trust Services", "tags": ["pki", "hsm"],
     "description": "Offline root and issuing certificate authorities."},
    {"code": "MAIL-SEC", "name": "Secure Email", "kind": "platform", "exposure": "partner", "criticality": "high", "data_classification": "secret",
     "data_shelf_life_years": 20, "migration_years": 3, "owner": "CIO Office", "team": "Collaboration", "tags": ["smime"]},
    {"code": "GRID-TEL", "name": "Grid Telemetry", "kind": "device", "exposure": "partner", "criticality": "high", "data_classification": "confidential",
     "data_shelf_life_years": 8, "migration_years": 7, "owner": "Energy Operations", "team": "OT Security", "tags": ["scada", "ot"]},
    {"code": "ARCHIVE", "name": "National Archive", "kind": "data_store", "exposure": "isolated", "criticality": "high", "data_classification": "secret",
     "data_shelf_life_years": 30, "migration_years": 2, "owner": "Records Directorate", "team": "Data Platform", "tags": ["backup"]},
    {"code": "VPN-GW", "name": "Remote Access VPN", "kind": "infrastructure", "exposure": "external", "criticality": "high", "data_classification": "confidential",
     "data_shelf_life_years": 3, "migration_years": 2, "owner": "Network Operations", "team": "Network Security", "tags": ["ipsec", "tls"]},
    {"code": "HR-SUITE", "name": "HR Suite", "kind": "application", "exposure": "internal", "criticality": "moderate", "data_classification": "confidential",
     "data_shelf_life_years": 7, "migration_years": 1.5, "owner": "Human Resources", "team": "Enterprise Apps"},
    {"code": "INTRANET", "name": "Staff Intranet", "kind": "application", "exposure": "internal", "criticality": "low", "data_classification": "internal",
     "data_shelf_life_years": 1, "migration_years": 0.5, "team": "Enterprise Apps"},
    {"code": "DEV-PORTAL", "name": "Developer Portal", "kind": "service", "exposure": "external", "criticality": "low", "data_classification": "public",
     "data_shelf_life_years": 0, "migration_years": 1, "owner": "Developer Relations", "team": "API Platform", "tags": ["docs"]},
]


def fixtures_dir() -> Path | None:
    """The bundled sample estates: in the repository, or mounted at /scan in the container."""
    settings = get_settings()
    for candidate in [REPO_DIR / "fixtures", *settings.scan_roots, Path("/scan")]:
        if (candidate / "estates").is_dir():
            return candidate
    return None


def _sources(fixtures: Path) -> list[tuple[str, str, str, str]]:
    """(system code, kind, locator, name)."""
    estates = fixtures / "estates"
    out = [
        ("PAY-GW", "directory", str(estates / "payments-platform"), "Payments monorepo"),
        ("CITIZEN-ID", "directory", str(estates / "identity-service"), "Identity service"),
        ("PKI-ROOT", "directory", str(estates / "payments-platform" / "deploy" / "pki"), "Issuing CA material"),
    ]
    image = fixtures / "images" / "payments-api-3.8.1.tar"
    if image.exists():
        out.append(("PAY-GW", "image-archive", str(image), "payments-api 3.8.1 container image"))
    return out


def credentials() -> tuple[str, str]:
    settings = get_settings()
    return settings.demo_admin_email, settings.demo_admin_password.get_secret_value()


def banner(fresh: bool) -> None:
    settings = get_settings()
    email, password = credentials()
    url = f"http://{'127.0.0.1' if settings.host in ('0.0.0.0', '::') else settings.host}:{settings.port}"
    # Plain ASCII: Windows consoles and redirected logs often use a legacy code page.
    rule = "  " + "-" * 64
    lines = [
        "",
        rule,
        f"  FALCON {'demo created' if fresh else 'demo'} - open {url}",
        f"    Email:     {email}",
        f"    Password:  {password}",
        "  Change this password after signing in: Settings > Password & devices.",
        rule,
        "",
    ]
    try:
        print("\n".join(lines), flush=True)
    except (OSError, ValueError):  # no usable console (a service, a closed pipe)
        logger.info("Demo sign-in: %s", email)


def existing(owner_email: str | None) -> None:
    """This installation is already set up, but not with the demo account."""
    settings = get_settings()
    url = f"http://{'127.0.0.1' if settings.host in ('0.0.0.0', '::') else settings.host}:{settings.port}"
    rule = "  " + "-" * 64
    lines = [
        "",
        rule,
        f"  FALCON is already set up - open {url}",
        f"    Sign in as:  {owner_email}" if owner_email else "    Sign in with the account you created.",
        "",
        "  This installation has its own data, so the demonstration account was",
        "  not created. To start fresh instead, stop FALCON and remove:",
        f"    {settings.data_dir.resolve()}",
        rule,
        "",
    ]
    try:
        print("\n".join(lines), flush=True)
    except (OSError, ValueError):
        logger.info("FALCON is already set up; sign in as %s", owner_email)


def seed() -> bool:
    """Creates the demonstration organisation if FALCON is not set up yet. Returns True if it did."""
    from .domains.discovery import service as discovery
    from .domains.identity.models import User
    from .domains.identity.service import principal_for
    from .domains.organisation.schemas import OrganisationProfileIn, ThreatModelIn
    from .domains.organisation.service import is_initialised, run_setup, threat_model
    from .domains.systems.schemas import SystemIn
    from .domains.systems.service import create_system
    from .kernel.database import get_sessionmaker
    from .kernel.security import verify_password

    email, password = credentials()
    with get_sessionmaker()() as db:
        if is_initialised(db):
            admin = db.scalar(select(User).where(User.email == email))
            if admin is not None and verify_password(password, admin.password_hash):
                banner(fresh=False)
            else:
                # Already set up under another account: say whose, so nobody is left guessing.
                owner = db.scalar(select(User).where(User.role == "owner"))
                existing(owner.email if owner else None)
            return False
        org, owner, _ = run_setup(
            db, profile=OrganisationProfileIn(**ORGANISATION), threat=ThreatModelIn(crqc_scenario="moderate", risk_tolerance=0.05),
            email=email, name=ADMIN_NAME, password=password, ip=None, user_agent="falcon demo",
        )
        principal = principal_for(owner, via="session")
        model = threat_model(org)
        ids: dict[str, str] = {}
        for spec in SYSTEMS:
            created = create_system(db, principal, SystemIn(**spec), model, None)
            ids[spec["code"]] = created["id"]
        fixtures = fixtures_dir()
        if fixtures is None:
            logger.warning("Demo: sample estates not found; systems created without scans.")
        else:
            for code, kind, locator, name in _sources(fixtures):
                try:
                    discovery.create_source(db, principal, ids[code], kind=kind, locator=locator, name=name, options={}, ip=None)
                except Exception as err:  # noqa: BLE001 - a missing sample must not stop the demo
                    logger.warning("Demo: could not add %s (%s)", name, err)
        user_id = owner.id
    threading.Thread(target=_finish, args=(user_id,), name="falcon-demo", daemon=True).start()
    banner(fresh=True)
    return True


def _finish(user_id: str) -> None:
    """After the demo scans complete: measure the benchmark lab and sign the first snapshot."""
    from .domains.discovery.models import Scan
    from .domains.identity.models import User
    from .domains.identity.service import principal_for
    from .domains.reports import service as reports
    from .kernel.database import get_sessionmaker
    from .migration import bench

    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        with get_sessionmaker()() as db:
            active = db.scalar(select(Scan.id).where(Scan.status.in_(("queued", "running"))).limit(1))
        if active is None:
            break
        time.sleep(1)
    try:
        if get_settings().demo_benchmarks and bench.latest() is None:
            bench.run()
        with get_sessionmaker()() as db:
            owner = db.get(User, user_id)
            if owner is not None:
                reports.create_snapshot(db, principal_for(owner, via="session"), label="First inventory", system_id=None, ip=None)
        logger.info("Demo ready: scans complete, benchmarks measured, first snapshot signed.")
    except Exception:  # noqa: BLE001 - the demo is a convenience; the platform works without it
        logger.exception("Demo: finishing steps failed")
