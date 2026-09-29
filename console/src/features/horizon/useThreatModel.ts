import { useMemo } from "react";
import { ThreatModel } from "@/lib/horizon";
import { useHorizon } from "@/lib/queries";
import type { HorizonCatalogue, ThreatModelSummary, Uncertainty } from "@/lib/types";

export function modelFromSummary(summary: ThreatModelSummary, catalogue: HorizonCatalogue): ThreatModel {
  const uncertainty = (Object.entries(catalogue.uncertainty).find(([, sigma]) => Math.abs(sigma - summary.sigma) < 1e-9)?.[0] ?? "moderate") as Uncertainty;
  return new ThreatModel({ scenario: summary.scenario, medianYear: summary.median_year, uncertainty, tolerance: summary.tolerance }, catalogue);
}

/** The organisation's saved threat model, evaluated client-side for live previews. */
export function useOrganisationModel(): { model: ThreatModel | null; catalogue: HorizonCatalogue | null } {
  const horizon = useHorizon();
  return useMemo(() => {
    if (!horizon.data) return { model: null, catalogue: null };
    return { model: modelFromSummary(horizon.data.model, horizon.data.catalogue), catalogue: horizon.data.catalogue };
  }, [horizon.data]);
}
