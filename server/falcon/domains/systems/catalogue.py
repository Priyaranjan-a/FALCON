"""Vocabulary of the systems register, with defaults that seed Mosca's X and Y.

Defaults are starting points for a planner, not measurements. Phase 3 refines
migration time (Y) from the cryptography actually discovered in each system.
"""
from __future__ import annotations

KINDS: dict[str, dict] = {
    "application": {"label": "Application", "migration_years": 2.0,
                    "summary": "Business application or web/mobile front end"},
    "service": {"label": "Service", "migration_years": 1.5,
                "summary": "API, microservice or integration endpoint"},
    "product": {"label": "Product", "migration_years": 3.0,
                "summary": "Software or hardware shipped to customers"},
    "platform": {"label": "Platform", "migration_years": 3.0,
                 "summary": "Shared platform such as a mainframe, ERP or cloud landing zone"},
    "infrastructure": {"label": "Infrastructure", "migration_years": 4.0,
                       "summary": "PKI, HSMs, identity, VPN, network and storage"},
    "device": {"label": "Device", "migration_years": 6.0,
               "summary": "Embedded, IoT, OT or field equipment with long refresh cycles"},
    "data_store": {"label": "Data store", "migration_years": 2.0,
                   "summary": "Database, archive, backup or data lake"},
}

CRITICALITY: dict[str, dict] = {
    "critical": {"label": "Mission-critical", "rank": 4},
    "high": {"label": "Business-critical", "rank": 3},
    "moderate": {"label": "Important", "rank": 2},
    "low": {"label": "Supporting", "rank": 1},
}

CLASSIFICATION: dict[str, dict] = {
    "secret": {"label": "Secret", "rank": 5, "shelf_life_years": 25},
    "restricted": {"label": "Restricted", "rank": 4, "shelf_life_years": 15},
    "confidential": {"label": "Confidential", "rank": 3, "shelf_life_years": 7},
    "internal": {"label": "Internal", "rank": 2, "shelf_life_years": 3},
    "public": {"label": "Public", "rank": 1, "shelf_life_years": 0},
}

EXPOSURE: dict[str, dict] = {
    "external": {"label": "Internet-facing", "rank": 4},
    "partner": {"label": "Partner-facing", "rank": 3},
    "internal": {"label": "Internal", "rank": 2},
    "isolated": {"label": "Isolated", "rank": 1},
}

LIFECYCLE: dict[str, dict] = {
    "planned": {"label": "Planned"},
    "active": {"label": "Active"},
    "sunsetting": {"label": "Sunsetting"},
    "retired": {"label": "Retired"},
}

ENVIRONMENT: dict[str, dict] = {
    "production": {"label": "Production"},
    "staging": {"label": "Staging"},
    "development": {"label": "Development"},
    "disaster_recovery": {"label": "Disaster recovery"},
}


def vocabulary() -> dict:
    return {
        "kinds": KINDS, "criticality": CRITICALITY, "classification": CLASSIFICATION,
        "exposure": EXPOSURE, "lifecycle": LIFECYCLE, "environment": ENVIRONMENT,
    }
