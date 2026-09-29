"""Flat exports: the risk register as CSV, and FALCON's own JSON report."""
from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from ..domains.horizon.model import format_decimal_year
from ..risk import policies as policy_rules
from .inventory import TOOL_NAME, TOOL_VERSION, Report

_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _cell(value: Any) -> Any:
    """Neutralises spreadsheet formula injection (a file path or name that starts with =, +, - or @)."""
    if isinstance(value, str) and value.startswith(_FORMULA):
        return "'" + value
    return value


def to_csv(report: Report) -> str:
    frameworks = list(policy_rules.frameworks())
    now = report.model.now
    header = ["system_code", "system", "kind", "name", "family", "quantum", "classical", "risk_score", "risk_band", "hndl_exposed",
              "mosca_x_years", "mosca_y_years", "mosca_z_years", "mosca_status", "crqc_probability", "at_risk_from", "broken_from",
              *[f"policy_{f}" for f in frameworks], "recommendation", "replace_with", "hybrid", "effort_years",
              "occurrences", "first_location", "fingerprint"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    for item in sorted(report.items, key=lambda i: (-i.risk.score, i.system.code, i.facts.name)):
        a, r, rec = item.facts, item.risk, item.recommendation or {}
        policy = {p.framework: p.status_at(now) for p in r.policies}
        first = item.occurrences[0] if item.occurrences else None
        writer.writerow([_cell(v) for v in [
            item.system.code, item.system.name, a.kind, a.name, a.family or "", a.quantum or "", a.classical or "", r.score, r.band,
            "yes" if r.hndl.get("exposed") else "no", r.mosca["x"], r.mosca["y"], r.mosca["z"], r.mosca["status"],
            r.mosca["probability"],
            format_decimal_year(r.timeline["at_risk"]) if r.timeline.get("at_risk") else "",
            format_decimal_year(r.timeline["broken"]) if r.timeline.get("broken") else "",
            *[policy.get(f, "") for f in frameworks],
            rec.get("title", "") if rec.get("action") != "keep" else "",
            (rec.get("primary") or {}).get("name", ""), (rec.get("hybrid") or {}).get("name", ""),
            (rec.get("effort") or {}).get("years", ""),
            item.occurrence_total, f"{first.path}:{first.line}" if first and first.line else (first.path if first else ""),
            item.fingerprint,
        ]])
    return "﻿" + buffer.getvalue()  # BOM so spreadsheet software reads UTF-8


def summary(report: Report) -> dict[str, Any]:
    bands = Counter(i.risk.band for i in report.items)
    quantum = Counter(i.facts.quantum or "n/a" for i in report.items if i.facts.kind not in ("library", "hardware"))
    kinds = Counter(i.facts.kind for i in report.items)
    return {
        "artefacts": len(report.items),
        "kinds": dict(kinds),
        "bands": {b: bands.get(b, 0) for b in ("critical", "high", "medium", "low", "none")},
        "quantum": dict(quantum),
        "hndl_exposed": sum(1 for i in report.items if i.risk.hndl.get("exposed")),
        "broken_or_weak": sum(1 for i in report.items if i.facts.classical in ("broken", "weak")),
        "max_score": max((i.risk.score for i in report.items), default=0),
    }


def to_native(report: Report) -> dict[str, Any]:
    """FALCON's own report: the summary and the full assessment of every artefact."""
    now = report.model.now
    return {
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "generated_at": report.generated_at.isoformat(),
        "organisation": report.organisation,
        "scope": report.scope,
        "threat_model": {"scenario": report.model.scenario, "planning_horizon": format_decimal_year(report.model.planning_year),
                         "tolerance": report.model.tolerance},
        "summary": summary(report),
        "artefacts": [{
            "ref": i.ref, "kind": i.facts.kind, "name": i.facts.name, "family": i.facts.family,
            "quantum": i.facts.quantum, "classical": i.facts.classical, "system": i.system.code,
            "risk": {"score": i.risk.score, "band": i.risk.band, "roles": i.risk.roles, "drivers": i.risk.drivers,
                     "mosca": i.risk.mosca, "hndl": i.risk.hndl, "timeline": i.risk.timeline},
            "policies": [p.as_dict(now) for p in i.risk.policies],
            "recommendation": {k: v for k, v in (i.recommendation or {}).items() if k in ("action", "title", "summary", "primary", "hybrid", "effort")},
            "occurrences": [{"path": o.path, "line": o.line, "detector": o.detector, "rule": o.rule} for o in i.occurrences],
            "occurrence_total": i.occurrence_total,
        } for i in sorted(report.items, key=lambda i: (-i.risk.score, i.facts.name))],
    }
