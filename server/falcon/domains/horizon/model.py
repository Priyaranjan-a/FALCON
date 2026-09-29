"""Quantum threat horizon: when might a cryptographically relevant quantum
computer (CRQC) arrive, and what does that mean for Mosca's inequality?

Arrival model
    The time until a CRQC exists, T (years from now), is modelled as a
    log-normal distribution with median ``m`` years and shape ``sigma``:

        P(T <= t) = Phi((ln t - ln m) / sigma)

    The median is expressed as a calendar year so the model stays meaningful
    as time passes. Log-normal suits the question: arrival cannot be in the
    past, and uncertainty grows with distance.

Planning horizon (Mosca's Z)
    An organisation chooses the probability of CRQC arrival it is prepared to
    tolerate, q. The planning horizon is the q-quantile of T:

        Z = exp(ln m + sigma * Phi^-1(q))

    A 5% tolerance means: "plan as though a CRQC arrives at the point where
    there is a 1-in-20 chance it already exists."

Mosca's inequality
    With X the time data must stay confidential and Y the time needed to
    migrate, data is exposed when X + Y > Z. FALCON also reports the
    probabilistic form P(T <= X + Y): the chance that a CRQC exists before
    data protected with today's cryptography reaches the end of its shelf-life.

The presets below are FALCON planning assumptions, not forecasts. Calibrate
them against the threat intelligence your organisation relies on (for example
the Global Risk Institute's annual Quantum Threat Timeline report).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import NormalDist

_STD = NormalDist()

SCENARIOS: dict[str, dict] = {
    "aggressive": {
        "label": "Aggressive",
        "median_year": 2031,
        "sigma": 0.45,
        "summary": "Rapid hardware and error-correction progress; a CRQC early in the 2030s.",
    },
    "moderate": {
        "label": "Moderate",
        "median_year": 2036,
        "sigma": 0.40,
        "summary": "Steady progress in line with public roadmaps; a CRQC in the mid-2030s.",
    },
    "conservative": {
        "label": "Conservative",
        "median_year": 2042,
        "sigma": 0.35,
        "summary": "Engineering obstacles slow scaling; a CRQC in the 2040s.",
    },
}

UNCERTAINTY: dict[str, float] = {"narrow": 0.25, "moderate": 0.40, "wide": 0.60}

TOLERANCES: tuple[float, ...] = (0.01, 0.05, 0.10, 0.25, 0.50)

MIN_MEDIAN_YEARS = 0.25  # a median in the past is clamped to three months out


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_decimal_year(year: float) -> str:
    """2031.54 -> "Jul 2031" (matches the console's formatting)."""
    whole = int(year)
    return f"{_MONTHS[min(11, max(0, int((year - whole) * 12)))]} {whole}"


def decimal_year(moment: datetime | None = None) -> float:
    moment = moment or datetime.now(timezone.utc)
    start = datetime(moment.year, 1, 1, tzinfo=timezone.utc)
    end = datetime(moment.year + 1, 1, 1, tzinfo=timezone.utc)
    return moment.year + (moment - start).total_seconds() / (end - start).total_seconds()


@dataclass(frozen=True)
class ThreatModel:
    scenario: str
    median_year: float
    sigma: float
    tolerance: float
    now: float  # decimal year the model was evaluated at

    @classmethod
    def build(
        cls,
        scenario: str,
        median_year: float | None,
        uncertainty: str | None,
        tolerance: float,
        now: float | None = None,
    ) -> ThreatModel:
        now = decimal_year() if now is None else now
        if scenario in SCENARIOS:
            preset = SCENARIOS[scenario]
            return cls(scenario, float(preset["median_year"]), preset["sigma"], tolerance, now)
        sigma = UNCERTAINTY.get(uncertainty or "moderate", UNCERTAINTY["moderate"])
        return cls("custom", float(median_year or SCENARIOS["moderate"]["median_year"]), sigma, tolerance, now)

    @property
    def median_years(self) -> float:
        return max(MIN_MEDIAN_YEARS, self.median_year - self.now)

    def probability_by(self, years_from_now: float) -> float:
        """P(CRQC exists within ``years_from_now`` years)."""
        if years_from_now <= 0:
            return 0.0
        z = (math.log(years_from_now) - math.log(self.median_years)) / self.sigma
        return _STD.cdf(z)

    def probability_by_year(self, year: float) -> float:
        return self.probability_by(year - self.now)

    def quantile_years(self, q: float) -> float:
        return math.exp(math.log(self.median_years) + self.sigma * _STD.inv_cdf(q))

    @property
    def planning_years(self) -> float:
        """Mosca's Z: years until the tolerated arrival probability is reached."""
        return self.quantile_years(self.tolerance)

    @property
    def planning_year(self) -> float:
        return self.now + self.planning_years

    def curve(self, until_year: int = 2060, points_per_year: int = 4) -> list[dict[str, float]]:
        start = math.floor(self.now * points_per_year) / points_per_year
        steps = int((until_year - start) * points_per_year) + 1
        out = []
        for i in range(steps):
            year = start + i / points_per_year
            out.append({"year": round(year, 4), "p": round(self.probability_by_year(year), 6)})
        return out

    def summary(self) -> dict:
        return {
            "scenario": self.scenario,
            "median_year": self.median_year,
            "sigma": self.sigma,
            "tolerance": self.tolerance,
            "evaluated_at": round(self.now, 4),
            "planning_years": round(self.planning_years, 3),
            "planning_year": round(self.planning_year, 3),
            "p10_year": round(self.now + self.quantile_years(0.10), 3),
            "p50_year": round(self.now + self.quantile_years(0.50), 3),
            "p90_year": round(self.now + self.quantile_years(0.90), 3),
        }


def mosca(model: ThreatModel, shelf_life_years: float, migration_years: float) -> dict:
    """Mosca's inequality for one system, in deterministic and probabilistic form."""
    x, y, z = float(shelf_life_years), float(migration_years), model.planning_years
    exposure = x + y - z
    if exposure > 0:
        status = "exposed"
    elif exposure > -2:
        status = "watch"
    else:
        status = "clear"
    # To keep X + Y <= Z, migration must be complete by (now + Z - X)
    # and therefore start by (now + Z - X - Y).
    complete_by = model.now + z - x
    start_by = complete_by - y
    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "z": round(z, 3),
        "exposure_years": round(exposure, 3),
        "status": status,
        "probability": model.probability_by(x + y),
        "complete_by": round(complete_by, 3),
        "start_by": round(start_by, 3),
        "overdue_years": round(max(0.0, model.now - start_by), 3),
    }
