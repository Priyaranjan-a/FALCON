"""Drift between two CBOMs: what appeared, what went, and what changed.

Works on CycloneDX documents alone, so any two snapshots (or a snapshot and a
CBOM from a CI run) can be compared. Components are matched by ``bom-ref``,
which FALCON keeps stable across exports.
"""
from __future__ import annotations

from typing import Any

_BAND_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
_QUANTUM_RANK = {"vulnerable": 0, "weakened": 1, "unknown": 2, "resistant": 3, "hybrid": 4, "pqc": 5}
_WATCHED = ("falcon:quantum-status", "falcon:classical-status", "falcon:risk:band", "falcon:risk:score", "falcon:hndl",
            "falcon:occurrences")


def _assets(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for c in doc.get("components", []):
        ref = c.get("bom-ref", "")
        if not ref.startswith("crypto/"):
            continue
        props = {p["name"]: p["value"] for p in c.get("properties", [])}
        out[ref] = {
            "ref": ref, "name": c.get("name"), "kind": props.get("falcon:artefact-kind") or c.get("type"),
            "system": props.get("falcon:system"), "quantum": props.get("falcon:quantum-status"),
            "band": props.get("falcon:risk:band"), "score": int(props.get("falcon:risk:score") or 0), "props": props,
        }
    return out


def _brief(a: dict[str, Any]) -> dict[str, Any]:
    return {k: a[k] for k in ("ref", "name", "kind", "system", "quantum", "band", "score")}


def compare(base: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    before, after = _assets(base), _assets(head)
    added = [_brief(after[r]) for r in sorted(set(after) - set(before))]
    removed = [_brief(before[r]) for r in sorted(set(before) - set(after))]
    changed: list[dict[str, Any]] = []
    for ref in sorted(set(before) & set(after)):
        b, a = before[ref], after[ref]
        diffs = {k.removeprefix("falcon:"): {"from": b["props"].get(k), "to": a["props"].get(k)}
                 for k in _WATCHED if b["props"].get(k) != a["props"].get(k)}
        if diffs:
            changed.append({**_brief(a), "changes": diffs,
                            "direction": _direction(b, a)})

    def vulnerable(rows: list[dict[str, Any]]) -> int:
        return sum(1 for r in rows if r.get("quantum") == "vulnerable")

    def pqc(rows: list[dict[str, Any]]) -> int:
        return sum(1 for r in rows if r.get("quantum") in ("pqc", "hybrid"))

    retired, introduced = vulnerable(removed), pqc(added)
    regressions = vulnerable(added) + sum(1 for c in changed if c["direction"] == "worse")
    improvements = retired + introduced + sum(1 for c in changed if c["direction"] == "better")
    verdict = ("unchanged" if not (added or removed or changed) else "improved" if improvements and not regressions
               else "regressed" if regressions and not improvements else "mixed" if regressions else "changed")
    score = lambda assets: sum(x["score"] for x in assets.values())  # noqa: E731
    return {
        "base": {"serial": base.get("serialNumber"), "timestamp": base.get("metadata", {}).get("timestamp"), "components": len(before)},
        "head": {"serial": head.get("serialNumber"), "timestamp": head.get("metadata", {}).get("timestamp"), "components": len(after)},
        "added": added, "removed": removed, "changed": changed,
        "unchanged": len(set(before) & set(after)) - len(changed),
        "totals": {"risk_before": score(before), "risk_after": score(after),
                   "vulnerable_before": vulnerable(list(before.values())), "vulnerable_after": vulnerable(list(after.values())),
                   "pqc_before": pqc(list(before.values())), "pqc_after": pqc(list(after.values()))},
        "verified": {"retired": retired, "introduced": introduced, "regressions": regressions},
        "verdict": verdict,
    }


def _direction(b: dict[str, Any], a: dict[str, Any]) -> str:
    q = _QUANTUM_RANK.get(a["quantum"] or "unknown", 2) - _QUANTUM_RANK.get(b["quantum"] or "unknown", 2)
    band = _BAND_RANK.get(a["band"] or "none", 0) - _BAND_RANK.get(b["band"] or "none", 0)
    if q > 0 or (q == 0 and band < 0):
        return "better"
    if q < 0 or band > 0:
        return "worse"
    return "same"
