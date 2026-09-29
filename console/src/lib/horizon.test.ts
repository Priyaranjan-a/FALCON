import { describe, expect, it } from "vitest";
import { mosca, normalCdf, normalInv, ThreatModel } from "./horizon";
import type { HorizonCatalogue } from "./types";

const catalogue: HorizonCatalogue = {
  scenarios: {
    aggressive: { label: "Aggressive", median_year: 2031, sigma: 0.45, summary: "" },
    moderate: { label: "Moderate", median_year: 2036, sigma: 0.4, summary: "" },
    conservative: { label: "Conservative", median_year: 2042, sigma: 0.35, summary: "" },
  },
  uncertainty: { narrow: 0.25, moderate: 0.4, wide: 0.6 },
  tolerances: [0.01, 0.05, 0.1, 0.25, 0.5],
};
const NOW = 2026.75;

describe("normal distribution", () => {
  it("matches reference values", () => {
    expect(normalCdf(0)).toBeCloseTo(0.5, 7);
    expect(normalCdf(1.959963985)).toBeCloseTo(0.975, 6);
    expect(normalInv(0.05)).toBeCloseTo(-1.6448536269514722, 8);
    expect(normalInv(0.975)).toBeCloseTo(1.959963984540054, 8);
  });
});

describe("threat model (mirrors the server)", () => {
  it("pins the moderate 5% planning year shared with server tests", () => {
    const model = new ThreatModel({ scenario: "moderate", tolerance: 0.05 }, catalogue, NOW);
    expect(model.planningYears).toBeCloseTo(9.25 * Math.exp(0.4 * -1.6448536269514722), 6);
    expect(model.planningYear).toBeCloseTo(2031.5407, 3);
    expect(model.probabilityByYear(2036)).toBeCloseTo(0.5, 6);
  });

  it("inverts quantile and probability for every scenario and tolerance", () => {
    for (const scenario of ["aggressive", "moderate", "conservative"] as const) {
      for (const tolerance of catalogue.tolerances) {
        const model = new ThreatModel({ scenario, tolerance }, catalogue, NOW);
        expect(model.probabilityBy(model.planningYears)).toBeCloseTo(tolerance, 5);
      }
    }
  });

  it("classifies Mosca exposure like the server", () => {
    const model = new ThreatModel({ scenario: "moderate", tolerance: 0.05 }, catalogue, NOW);
    expect(mosca(model, 10, 2).status).toBe("exposed");
    expect(mosca(model, 2, 1.5).status).toBe("watch");
    expect(mosca(model, 0, 0.5).status).toBe("clear");
  });

  it("uses custom medians and clamps past ones", () => {
    const custom = new ThreatModel({ scenario: "custom", medianYear: 2040, uncertainty: "wide", tolerance: 0.1 }, catalogue, NOW);
    expect(custom.sigma).toBe(0.6);
    const past = new ThreatModel({ scenario: "custom", medianYear: 2020, uncertainty: "narrow", tolerance: 0.1 }, catalogue, NOW);
    expect(past.medianYears).toBe(0.25);
  });
});
