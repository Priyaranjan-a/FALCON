"""SPDX 2.3 (JSON) software bill of materials with the cryptographic assessment.

SPDX 2.3 has no cryptography profile, so each system is an application
package, each cryptographic library and hardware module a package with its
package URL, and each cryptographic asset a package of purpose ``OTHER``
whose FALCON assessment travels as a review annotation. Tools that only read
SPDX still see which software carries which cryptography.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from .cbom import _purl
from .inventory import TOOL_NAME, TOOL_URI, TOOL_VERSION, Item, Report

_ID = re.compile(r"[^A-Za-z0-9.-]+")


def _spdx_id(*parts: str) -> str:
    return "SPDXRef-" + "-".join(_ID.sub("-", p).strip("-") for p in parts if p)


def _annotation(item: Item, created: str) -> dict[str, Any]:
    r, rec = item.risk, item.recommendation or {}
    bits = [f"quantum: {item.facts.quantum or 'n/a'}", f"classical: {item.facts.classical or 'n/a'}",
            f"risk: {r.band} ({r.score}/100)", f"mosca: X {r.mosca['x']:g} + Y {r.mosca['y']:g} vs Z {r.mosca['z']:g} ({r.mosca['status']})"]
    if r.hndl.get("exposed"):
        bits.append("harvest-now-decrypt-later exposed")
    if rec.get("primary") and rec.get("action") != "keep":
        bits.append(f"replace with {rec['primary']['name']}")
    return {"annotationDate": created, "annotationType": "REVIEW", "annotator": f"Tool: {TOOL_NAME}-{TOOL_VERSION}",
            "comment": "; ".join(bits)}


def build(report: Report) -> dict[str, Any]:
    created = report.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    packages: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    system_ids: dict[str, str] = {}
    for sid, s in sorted(report.systems.items(), key=lambda kv: kv[1].code):
        if not any(i.system.id == sid for i in report.items):
            continue
        spdx_id = _spdx_id("system", s.code)
        system_ids[sid] = spdx_id
        packages.append({
            "SPDXID": spdx_id, "name": s.name, "downloadLocation": "NOASSERTION", "filesAnalyzed": False,
            "primaryPackagePurpose": "APPLICATION", "supplier": f"Organization: {report.organisation}",
            "comment": f"System {s.code}: {s.criticality} criticality, {s.exposure} exposure, {s.classification} data "
                       f"kept {s.shelf_life_years:g} years.",
        })
        relationships.append({"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": spdx_id})

    for item in sorted(report.items, key=lambda i: (i.system.code, i.facts.kind, i.facts.name)):
        a = item.facts
        spdx_id = _spdx_id(a.kind, item.system.code, item.fingerprint[:20])
        package: dict[str, Any] = {"SPDXID": spdx_id, "name": a.name, "downloadLocation": "NOASSERTION", "filesAnalyzed": False}
        if a.kind == "library":
            package["primaryPackagePurpose"] = "LIBRARY"
            if a.identity.get("version"):
                package["versionInfo"] = str(a.identity["version"])
            purl = _purl(item)
            if purl:
                package["externalRefs"] = [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": purl}]
            relation = "DEPENDS_ON"
        elif a.kind == "hardware":
            package["primaryPackagePurpose"] = "DEVICE"
            if a.properties.get("vendor"):
                package["supplier"] = f"Organization: {a.properties['vendor']}"
            relation = "DEPENDS_ON"
        else:
            package["primaryPackagePurpose"] = "OTHER"
            package["comment"] = f"Cryptographic {a.kind.replace('_', ' ')} ({a.family or 'unclassified'})."
            relation = "CONTAINS"
        first = item.occurrences[0] if item.occurrences else None
        if first:
            package["sourceInfo"] = f"Found at {first.path}{f':{first.line}' if first.line else ''}" + (
                f" and {item.occurrence_total - 1} other places" if item.occurrence_total > 1 else "")
        package["annotations"] = [_annotation(item, created)]
        packages.append(package)
        relationships.append({"spdxElementId": system_ids[item.system.id], "relationshipType": relation, "relatedSpdxElement": spdx_id})

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{report.organisation} cryptographic inventory: {report.scope}",
        "documentNamespace": f"{TOOL_URI}spdx/{uuid.uuid4()}",
        "creationInfo": {"created": created, "creators": [f"Tool: {TOOL_NAME}-{TOOL_VERSION}", f"Organization: {report.organisation}"]},
        "packages": packages,
        "relationships": relationships,
    }
