import { ThreatModel } from "@/lib/horizon";
import type { HorizonCatalogue, Scenario, ScenarioKey, ThreatModelSettings, Uncertainty } from "@/lib/types";
import { series } from "@/viz/core/tokens";

/** Colour follows the scenario, never its rank or selection state. */
export const SCENARIO_COLORS: Record<Scenario, string> = {
  moderate: series[0],
  aggressive: series[1],
  conservative: series[2],
  custom: series[6],
};

export const SCENARIO_ORDER: ScenarioKey[] = ["aggressive", "moderate", "conservative"];

export const TOLERANCE_LABELS: Record<string, string> = {
  "0.01": "Extreme caution",
  "0.05": "High assurance",
  "0.1": "Cautious",
  "0.25": "Balanced",
  "0.5": "Median estimate",
};

export const UNCERTAINTY_LABELS: Record<Uncertainty, string> = { narrow: "Narrow", moderate: "Moderate", wide: "Wide" };

export function buildModel(settings: ThreatModelSettings, catalogue: HorizonCatalogue): ThreatModel {
  return new ThreatModel(
    { scenario: settings.crqc_scenario, medianYear: settings.crqc_median_year, uncertainty: settings.crqc_uncertainty, tolerance: settings.risk_tolerance },
    catalogue,
  );
}

export function scenarioLabel(scenario: Scenario, catalogue?: HorizonCatalogue): string {
  if (scenario === "custom") return "Custom";
  return catalogue?.scenarios[scenario].label ?? scenario[0].toUpperCase() + scenario.slice(1);
}

export function sameSettings(a: ThreatModelSettings, b: ThreatModelSettings): boolean {
  return (
    a.crqc_scenario === b.crqc_scenario &&
    a.risk_tolerance === b.risk_tolerance &&
    (a.crqc_scenario !== "custom" || (a.crqc_median_year === b.crqc_median_year && a.crqc_uncertainty === b.crqc_uncertainty))
  );
}
