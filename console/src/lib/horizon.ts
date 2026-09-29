/**
 * Client-side mirror of the server's threat horizon model
 * (server/falcon/domains/horizon/model.py), so scenario and Mosca previews
 * respond at frame rate while the user drags a control. Both implementations
 * are pinned to the same reference values by their test suites; the server
 * remains authoritative for anything saved.
 */
import type { HorizonCatalogue, Mosca, MoscaStatus, Scenario, Uncertainty } from "./types";

const MIN_MEDIAN_YEARS = 0.25;

/** Standard normal CDF (Hart 1968, as given by West 2005; double precision, |ε| ≈ 1e-14). */
export function normalCdf(x: number): number {
  const a = Math.abs(x);
  let tail: number;
  if (a > 37) {
    tail = 0;
  } else {
    const e = Math.exp((-a * a) / 2);
    if (a < 7.07106781186547) {
      let n = 3.52624965998911e-2 * a + 0.700383064443688;
      n = n * a + 6.37396220353165;
      n = n * a + 33.912866078383;
      n = n * a + 112.079291497871;
      n = n * a + 221.213596169931;
      n = n * a + 220.206867912376;
      let d = 8.83883476483184e-2 * a + 1.75566716318264;
      d = d * a + 16.064177579207;
      d = d * a + 86.7807322029461;
      d = d * a + 296.564248779674;
      d = d * a + 637.333633378831;
      d = d * a + 793.826512519948;
      d = d * a + 440.413735824752;
      tail = (e * n) / d;
    } else {
      let b = a + 0.65;
      b = a + 4 / b;
      b = a + 3 / b;
      b = a + 2 / b;
      b = a + 1 / b;
      tail = e / b / 2.506628274631;
    }
  }
  return x > 0 ? 1 - tail : tail;
}

/** Inverse standard normal CDF (Acklam's algorithm with one Halley refinement). */
export function normalInv(p: number): number {
  if (p <= 0 || p >= 1) throw new RangeError("p must be in (0, 1)");
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.38357751867269e2, -3.066479806614716e1, 2.506628277459239];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  const low = 0.02425;
  let x: number;
  if (p < low) {
    const q = Math.sqrt(-2 * Math.log(p));
    x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  } else if (p <= 1 - low) {
    const q = p - 0.5;
    const r = q * q;
    x = ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  } else {
    const q = Math.sqrt(-2 * Math.log(1 - p));
    x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  const e = normalCdf(x) - p;
  const u = e * Math.sqrt(2 * Math.PI) * Math.exp((x * x) / 2);
  return x - u / (1 + (x * u) / 2);
}

export function decimalYear(date = new Date()): number {
  const year = date.getUTCFullYear();
  const start = Date.UTC(year, 0, 1);
  const end = Date.UTC(year + 1, 0, 1);
  return year + (date.getTime() - start) / (end - start);
}

export interface ThreatModelInput {
  scenario: Scenario;
  medianYear?: number | null;
  uncertainty?: Uncertainty | null;
  tolerance: number;
}

export class ThreatModel {
  readonly scenario: Scenario;
  readonly medianYear: number;
  readonly sigma: number;
  readonly tolerance: number;
  readonly now: number;

  constructor(input: ThreatModelInput, catalogue: HorizonCatalogue, now = decimalYear()) {
    this.now = now;
    this.tolerance = input.tolerance;
    if (input.scenario !== "custom") {
      const preset = catalogue.scenarios[input.scenario];
      this.scenario = input.scenario;
      this.medianYear = preset.median_year;
      this.sigma = preset.sigma;
    } else {
      this.scenario = "custom";
      this.medianYear = input.medianYear ?? catalogue.scenarios.moderate.median_year;
      this.sigma = catalogue.uncertainty[input.uncertainty ?? "moderate"];
    }
  }

  get medianYears(): number {
    return Math.max(MIN_MEDIAN_YEARS, this.medianYear - this.now);
  }

  probabilityBy(yearsFromNow: number): number {
    if (yearsFromNow <= 0) return 0;
    return normalCdf((Math.log(yearsFromNow) - Math.log(this.medianYears)) / this.sigma);
  }

  probabilityByYear(year: number): number {
    return this.probabilityBy(year - this.now);
  }

  quantileYears(q: number): number {
    return Math.exp(Math.log(this.medianYears) + this.sigma * normalInv(q));
  }

  get planningYears(): number {
    return this.quantileYears(this.tolerance);
  }

  get planningYear(): number {
    return this.now + this.planningYears;
  }

  curve(untilYear = 2060, pointsPerYear = 4): { year: number; p: number }[] {
    const start = Math.floor(this.now * pointsPerYear) / pointsPerYear;
    const steps = Math.floor((untilYear - start) * pointsPerYear) + 1;
    return Array.from({ length: steps }, (_, i) => {
      const year = start + i / pointsPerYear;
      return { year, p: this.probabilityByYear(year) };
    });
  }
}

export function mosca(model: ThreatModel, x: number, y: number): Mosca {
  const z = model.planningYears;
  const exposure = x + y - z;
  const status: MoscaStatus = exposure > 0 ? "exposed" : exposure > -2 ? "watch" : "clear";
  const completeBy = model.now + z - x;
  const startBy = completeBy - y;
  return {
    x,
    y,
    z,
    exposure_years: exposure,
    status,
    probability: model.probabilityBy(x + y),
    complete_by: completeBy,
    start_by: startBy,
    overdue_years: Math.max(0, model.now - startBy),
  };
}
