"""The migration roadmap: artefacts grouped into waves and scheduled per system.

Waves, in the order they are started:

    1  Fix what is broken today     classically broken or already disallowed
    2  Stop the harvest              harvest-now-decrypt-later exposures, and the
                                     libraries those systems need upgraded first
    3  Long lead times               CA hierarchies, hardware, cloud KMS and
                                     library replacements (a year or more of work)
    4  Before the 2030 deprecation   remaining critical and high risks, and
                                     112-bit public-key cryptography
    5  Complete the transition       everything else quantum-vulnerable or weakened

Waves 1-3 start now and run in parallel lanes; wave 4 starts when wave 2
finishes and wave 5 when wave 4 finishes. Within a system a wave lasts as long
as its longest artefact migration plus coordination time for its size.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..domains.horizon.model import ThreatModel

WAVES = [
    {"key": "fix-now", "title": "Fix what is broken today", "summary": "Classically broken or already disallowed: attackable without a quantum computer."},
    {"key": "stop-harvest", "title": "Stop the harvest", "summary": "Hybrid key exchange where recorded traffic outlives the horizon, and the library upgrades it depends on."},
    {"key": "long-lead", "title": "Long lead times", "summary": "PKI hierarchies, hardware, cloud keys and library replacements: start early, finish late."},
    {"key": "before-2030", "title": "Before the 2030 deprecation", "summary": "Remaining critical and high risks, and 112-bit public-key cryptography NIST deprecates after 2030."},
    {"key": "complete", "title": "Complete the transition", "summary": "Everything else quantum-vulnerable or weakened, before the 2035 disallowance."},
]


@dataclass
class Item:
    artefact_id: str
    system_id: str
    band: str
    score: int
    years: float
    wave: str
    payload: dict[str, Any]


def wave_for(row: dict[str, Any], system_needs_harvest_fix: bool) -> str | None:
    """The wave an artefact belongs to, or None when nothing needs doing."""
    rec = row["recommendation"]
    if rec["action"] == "keep":
        return None
    likelihood = row["likelihood"]
    if row["classical"] in ("broken", "weak") or likelihood.get("policy", 0) >= 0.99:
        return "fix-now"
    if row["hndl"]["exposed"]:
        return "stop-harvest"
    if row["kind"] == "library" and system_needs_harvest_fix and rec["action"] in ("upgrade", "replace", "enable"):
        return "stop-harvest"
    if row["migration"]["years"] >= 1.5 or row["kind"] in ("hardware", "cloud_service") or (rec["action"] == "reissue" and row.get("ca")):
        return "long-lead"
    deadline = likelihood.get("policy_deadline")
    if row["band"] in ("critical", "high") or (deadline is not None and deadline <= 2031.01):
        return "before-2030"
    return "complete"


def schedule(items: list[Item], systems: dict[str, dict[str, Any]], model: ThreatModel) -> dict[str, Any]:
    now = model.now
    by_wave: dict[str, list[Item]] = {w["key"]: [] for w in WAVES}
    for item in items:
        by_wave[item.wave].append(item)

    def duration(group: list[Item]) -> float:
        if not group:
            return 0.0
        return round(max(i.years for i in group) + 0.1 * math.log2(1 + len(group)), 2)

    lanes: dict[str, list[dict[str, Any]]] = {sid: [] for sid in systems}
    waves_out = []
    starts: dict[str, float] = {}
    finishes: dict[str, float] = {}
    for w in WAVES:
        key = w["key"]
        if key in ("fix-now", "stop-harvest", "long-lead"):
            start = now
        elif key == "before-2030":
            start = finishes.get("stop-harvest", now)
        else:
            start = finishes.get("before-2030", finishes.get("stop-harvest", now))
        group = by_wave[key]
        per_system: dict[str, list[Item]] = {}
        for i in group:
            per_system.setdefault(i.system_id, []).append(i)
        finish = start
        for sid, sys_items in per_system.items():
            end = start + duration(sys_items)
            finish = max(finish, end)
            lanes.setdefault(sid, []).append({"wave": key, "start": round(start, 3), "finish": round(end, 3), "count": len(sys_items),
                                              "worst": min((i.band for i in sys_items), key=_band_rank)})
        starts[key], finishes[key] = start, finish if group else start
        deadline = {"fix-now": now, "stop-harvest": model.planning_year, "before-2030": 2031.0, "complete": 2036.0}.get(key)
        waves_out.append({
            **w,
            "start": round(start, 3),
            "finish": round(finishes[key], 3),
            "artefacts": len(group),
            "systems": len(per_system),
            "effort_years": round(sum(i.years for i in group), 2),
            "deadline": round(deadline, 3) if deadline else None,
            "on_time": None if not group or deadline is None or key == "fix-now" else finishes[key] <= deadline,
            "items": [i.payload for i in sorted(group, key=lambda i: (-i.score, i.payload["name"]))],
        })

    completion = max((w["finish"] for w in waves_out if w["artefacts"]), default=now)
    return {
        "waves": waves_out,
        "lanes": [{"system": systems[sid], "bars": bars} for sid, bars in lanes.items() if bars],
        "completion": round(completion, 3),
        "completion_probability": round(model.probability_by(completion - now), 5),
        "horizon": round(model.planning_year, 3),
    }


def _band_rank(band: str) -> int:
    return ["critical", "high", "medium", "low", "none"].index(band)
