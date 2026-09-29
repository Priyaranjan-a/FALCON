"""Regulatory milestone catalogue (versioned knowledge base)."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOGUE = Path(__file__).resolve().parents[2] / "knowledge" / "regulatory_milestones.json"


@lru_cache
def catalogue() -> dict[str, Any]:
    with _CATALOGUE.open(encoding="utf-8") as fh:
        data = json.load(fh)
    authorities = data["authorities"]
    milestones = []
    for item in data["milestones"]:
        when = date.fromisoformat(item["date"])
        milestones.append({
            **item,
            "authority_name": authorities[item["authority"]]["name"],
            "region": authorities[item["authority"]]["region"],
            "year": when.year,
            "decimal_year": round(when.year + (when.timetuple().tm_yday - 1) / 365.25, 4),
        })
    milestones.sort(key=lambda m: (m["date"], m["id"]))
    return {"version": data["version"], "note": data["note"], "authorities": authorities, "milestones": milestones}


def upcoming(today: date | None = None, limit: int = 5) -> list[dict[str, Any]]:
    today = today or date.today()
    return [m for m in catalogue()["milestones"] if date.fromisoformat(m["date"]) >= today][:limit]
