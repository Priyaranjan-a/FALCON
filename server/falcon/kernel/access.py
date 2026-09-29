"""Roles and permissions.

Authorisation checks name a *permission*, never a role, so the role matrix can
evolve without touching endpoint code. The console receives the caller's
permission set and gates its UI with the same names.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Permission(StrEnum):
    ORG_MANAGE = "org.manage"
    THREAT_MANAGE = "threat.manage"
    MEMBERS_READ = "members.read"
    MEMBERS_MANAGE = "members.manage"
    SYSTEMS_READ = "systems.read"
    SYSTEMS_WRITE = "systems.write"
    SYSTEMS_DELETE = "systems.delete"
    AUDIT_READ = "audit.read"
    TOKENS_USE = "tokens.use"
    INVENTORY_READ = "inventory.read"
    SOURCES_MANAGE = "sources.manage"
    SCANS_RUN = "scans.run"
    REPORTS_SIGN = "reports.sign"


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    SECURITY_LEAD = "security_lead"
    ANALYST = "analyst"
    AUDITOR = "auditor"
    VIEWER = "viewer"


P = Permission

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(Permission),
    Role.SECURITY_LEAD: frozenset({
        P.THREAT_MANAGE, P.MEMBERS_READ, P.SYSTEMS_READ, P.SYSTEMS_WRITE,
        P.SYSTEMS_DELETE, P.AUDIT_READ, P.TOKENS_USE, P.INVENTORY_READ, P.SOURCES_MANAGE, P.SCANS_RUN, P.REPORTS_SIGN,
    }),
    Role.ANALYST: frozenset({P.MEMBERS_READ, P.SYSTEMS_READ, P.SYSTEMS_WRITE, P.TOKENS_USE,
                             P.INVENTORY_READ, P.SOURCES_MANAGE, P.SCANS_RUN}),
    Role.AUDITOR: frozenset({P.MEMBERS_READ, P.SYSTEMS_READ, P.AUDIT_READ, P.INVENTORY_READ}),
    Role.VIEWER: frozenset({P.SYSTEMS_READ, P.INVENTORY_READ}),
}

ROLE_INFO: dict[Role, dict[str, str]] = {
    Role.OWNER: {"label": "Owner", "summary": "Full control. Created at setup; cannot be removed."},
    Role.ADMIN: {"label": "Administrator", "summary": "Manages the organisation, members and every workspace setting."},
    Role.SECURITY_LEAD: {"label": "Security lead", "summary": "Owns the threat model and the systems register; reads the audit ledger."},
    Role.ANALYST: {"label": "Analyst", "summary": "Registers and maintains systems; runs day-to-day analysis."},
    Role.AUDITOR: {"label": "Auditor", "summary": "Read-only access plus the audit ledger, for assurance and compliance."},
    Role.VIEWER: {"label": "Viewer", "summary": "Read-only access to the systems register and dashboards."},
}

# Roles an administrator may grant. Ownership is never granted, only created.
ASSIGNABLE_ROLES = (Role.ADMIN, Role.SECURITY_LEAD, Role.ANALYST, Role.AUDITOR, Role.VIEWER)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller."""

    user_id: str
    email: str
    name: str
    role: Role
    via: str  # "session" | "token"
    session_id: str | None = None
    token_id: str | None = None
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


def permissions_for(role: Role | str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(Role(role), frozenset())
