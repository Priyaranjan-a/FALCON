from __future__ import annotations

import math
from datetime import date

import pytest
from fastapi.testclient import TestClient

from falcon.domains.horizon import milestones
from falcon.domains.horizon.model import SCENARIOS, TOLERANCES, ThreatModel, mosca

NOW = 2026.75


@pytest.mark.parametrize("scenario", list(SCENARIOS))
@pytest.mark.parametrize("tolerance", TOLERANCES)
def test_quantile_and_cdf_are_inverse(scenario: str, tolerance: float) -> None:
    model = ThreatModel.build(scenario, None, None, tolerance, now=NOW)
    assert model.probability_by(model.planning_years) == pytest.approx(tolerance, abs=1e-9)


def test_median_is_the_50th_percentile() -> None:
    model = ThreatModel.build("moderate", None, None, 0.5, now=NOW)
    assert model.planning_year == pytest.approx(SCENARIOS["moderate"]["median_year"], abs=1e-9)


def test_reference_values() -> None:
    """Pinned against an independent calculation (shared with the console's tests)."""
    model = ThreatModel.build("moderate", None, None, 0.05, now=NOW)
    # m = 2036 - 2026.75 = 9.25 years, sigma = 0.40, z(0.05) = -1.6448536
    assert model.planning_years == pytest.approx(9.25 * math.exp(0.40 * -1.6448536269514722), rel=1e-9)
    assert model.planning_year == pytest.approx(2031.5407, abs=1e-3)
    assert model.probability_by_year(2036.0) == pytest.approx(0.5, abs=1e-12)


def test_scenarios_are_ordered() -> None:
    years = [ThreatModel.build(s, None, None, 0.05, now=NOW).planning_year for s in ("aggressive", "moderate", "conservative")]
    assert years == sorted(years)


def test_custom_scenario_and_past_median_is_clamped() -> None:
    custom = ThreatModel.build("custom", 2040, "wide", 0.10, now=NOW)
    assert custom.sigma == 0.60 and custom.median_year == 2040
    past = ThreatModel.build("custom", 2020, "narrow", 0.10, now=NOW)
    assert past.median_years == 0.25


def test_curve_is_monotonic() -> None:
    curve = ThreatModel.build("aggressive", None, None, 0.05, now=NOW).curve()
    probabilities = [p["p"] for p in curve]
    assert probabilities == sorted(probabilities)
    assert curve[0]["p"] < 0.01 and curve[-1]["p"] > 0.99


def test_mosca_statuses() -> None:
    model = ThreatModel.build("moderate", None, None, 0.05, now=NOW)  # Z ~ 4.79
    assert mosca(model, 10, 2)["status"] == "exposed"
    assert mosca(model, 2, 1.5)["status"] == "watch"
    clear = mosca(model, 0, 0.5)
    assert clear["status"] == "clear" and clear["overdue_years"] == 0
    exposed = mosca(model, 10, 2)
    assert exposed["start_by"] == pytest.approx(NOW + model.planning_years - 12, abs=1e-3)
    assert exposed["overdue_years"] == pytest.approx(12 - model.planning_years, abs=1e-3)


def test_milestone_catalogue() -> None:
    data = milestones.catalogue()
    dates = [m["date"] for m in data["milestones"]]
    assert dates == sorted(dates)
    assert {m["authority"] for m in data["milestones"]} <= set(data["authorities"])
    upcoming = milestones.upcoming(date(2029, 1, 1), limit=3)
    assert len(upcoming) == 3 and all(m["date"] >= "2029-01-01" for m in upcoming)


def test_horizon_api(owner: TestClient) -> None:
    body = owner.get("/api/v1/horizon").json()
    assert body["model"]["scenario"] == "moderate"
    assert body["catalogue"]["tolerances"] == list(TOLERANCES)
    preview = owner.get("/api/v1/horizon/evaluate", params={"scenario": "custom", "median_year": 2045, "uncertainty": "narrow", "tolerance": 0.1}).json()
    assert preview["model"]["median_year"] == 2045
    assert owner.get("/api/v1/horizon/evaluate", params={"tolerance": 0.07}).status_code == 422
    assert len(owner.get("/api/v1/horizon/milestones").json()["milestones"]) >= 20


def test_uuid7_fallback_is_valid_and_time_ordered() -> None:
    import time
    import uuid

    from falcon.kernel.database import _uuid7

    first = _uuid7()
    time.sleep(0.002)
    second = _uuid7()
    assert first.version == 7 and first.variant == uuid.RFC_4122
    assert str(first) < str(second)
