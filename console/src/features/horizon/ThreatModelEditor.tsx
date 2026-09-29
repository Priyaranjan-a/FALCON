import { Check } from "lucide-react";
import { useMemo } from "react";
import { cn } from "@/design/cn";
import { Slider } from "@/design/components/Controls";
import { Segmented } from "@/design/components/Segmented";
import { formatDecimalYear, formatPercent, formatYears } from "@/lib/format";
import type { HorizonCatalogue, Scenario, ThreatModelSettings, Uncertainty } from "@/lib/types";
import { ProbabilityCurve, type CurveSeries } from "@/viz/charts/ProbabilityCurve";
import { Legend } from "@/viz/core/ChartFrame";
import { buildModel, SCENARIO_COLORS, SCENARIO_ORDER, scenarioLabel, TOLERANCE_LABELS, UNCERTAINTY_LABELS } from "./model";

interface EditorProps {
  catalogue: HorizonCatalogue;
  value: ThreatModelSettings;
  onChange: (value: ThreatModelSettings) => void;
  disabled?: boolean;
  chartHeight?: number;
  compact?: boolean;
}

const DOMAIN_END = 2056;

/** Scenario and tolerance controls with a live arrival curve. */
export function ThreatModelEditor({ catalogue, value, onChange, disabled, chartHeight = 280, compact }: EditorProps) {
  const model = useMemo(() => buildModel(value, catalogue), [value, catalogue]);

  const curves: CurveSeries[] = useMemo(() => {
    const presets: CurveSeries[] = SCENARIO_ORDER.map((key) => {
      const m = buildModel({ crqc_scenario: key, crqc_median_year: null, crqc_uncertainty: null, risk_tolerance: value.risk_tolerance }, catalogue);
      return { id: key, label: catalogue.scenarios[key].label, color: SCENARIO_COLORS[key], points: m.curve(DOMAIN_END), emphasis: value.crqc_scenario === key };
    });
    if (value.crqc_scenario === "custom") {
      presets.push({ id: "custom", label: "Custom", color: SCENARIO_COLORS.custom, points: model.curve(DOMAIN_END), emphasis: true });
    }
    return presets;
  }, [catalogue, model, value.crqc_scenario, value.risk_tolerance]);

  const setScenario = (scenario: Scenario) =>
    onChange(
      scenario === "custom"
        ? { ...value, crqc_scenario: "custom", crqc_median_year: value.crqc_median_year ?? Math.round(model.medianYear), crqc_uncertainty: value.crqc_uncertainty ?? "moderate" }
        : { ...value, crqc_scenario: scenario, crqc_median_year: null, crqc_uncertainty: null },
    );

  const description =
    value.crqc_scenario === "custom"
      ? `Median arrival in ${value.crqc_median_year} with ${UNCERTAINTY_LABELS[value.crqc_uncertainty ?? "moderate"].toLowerCase()} uncertainty.`
      : catalogue.scenarios[value.crqc_scenario].summary;

  return (
    <div className={cn("grid gap-6", !compact && "lg:grid-cols-[300px_1fr]")}>
      <div className="space-y-5">
        <div className="space-y-2">
          <div className="text-subhead font-medium text-label-2" id="scenario-label">
            Arrival scenario
          </div>
          <div role="radiogroup" aria-labelledby="scenario-label" className="overflow-hidden rounded-[12px] bg-fill-2">
            {[...SCENARIO_ORDER, "custom" as const].map((key) => {
              const selected = value.crqc_scenario === key;
              const sub = key === "custom" ? "Your own median and uncertainty" : `Median arrival ${catalogue.scenarios[key].median_year}`;
              return (
                <button
                  key={key}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  disabled={disabled && !selected}
                  onClick={() => !disabled && setScenario(key)}
                  className={cn(
                    "relative flex w-full items-center gap-3 px-3 py-2 text-left outline-none transition-colors duration-150 focus-visible:bg-accent-tint",
                    "[&+&]:before:absolute [&+&]:before:inset-x-3 [&+&]:before:top-0 [&+&]:before:h-px [&+&]:before:bg-separator",
                    !disabled && !selected && "hover:bg-fill-2",
                    disabled && !selected && "opacity-50",
                  )}
                >
                  <span aria-hidden className="size-2.5 shrink-0 rounded-full" style={{ background: SCENARIO_COLORS[key] }} />
                  <span className="min-w-0 flex-1">
                    <span className={cn("block text-callout", selected ? "font-semibold text-label" : "text-label")}>{scenarioLabel(key, catalogue)}</span>
                    <span className="block text-footnote tabular text-label-3">{sub}</span>
                  </span>
                  {selected && <Check className="size-4 shrink-0 text-accent" strokeWidth={2.75} />}
                </button>
              );
            })}
          </div>
          <p className="text-footnote text-label-3">{description}</p>
        </div>

        {value.crqc_scenario === "custom" && (
          <div className="space-y-4 rounded-[12px] bg-fill-2 p-3.5">
            <div>
              <div className="mb-1 flex items-baseline justify-between">
                <span className="text-subhead font-medium text-label-2">Median arrival</span>
                <span className="text-headline tabular text-label">{value.crqc_median_year}</span>
              </div>
              <Slider label="Median arrival year" min={2028} max={2060} step={1} value={value.crqc_median_year ?? 2036} onChange={(y) => onChange({ ...value, crqc_median_year: y })} disabled={disabled} />
            </div>
            <div>
              <div className="mb-1.5 text-subhead font-medium text-label-2">Uncertainty</div>
              <Segmented
                size="sm"
                block
                label="Uncertainty"
                value={value.crqc_uncertainty ?? "moderate"}
                onChange={(u: Uncertainty) => onChange({ ...value, crqc_uncertainty: u })}
                options={(["narrow", "moderate", "wide"] as Uncertainty[]).map((u) => ({ value: u, label: UNCERTAINTY_LABELS[u], disabled }))}
              />
            </div>
          </div>
        )}

        <div className="space-y-2">
          <div className="text-subhead font-medium text-label-2">Risk tolerance</div>
          <Segmented
            label="Risk tolerance"
            block
            size="sm"
            value={String(value.risk_tolerance)}
            onChange={(t) => onChange({ ...value, risk_tolerance: Number(t) })}
            options={catalogue.tolerances.map((t) => ({ value: String(t), label: formatPercent(t, 0), disabled }))}
          />
          <p className="text-footnote text-label-3">
            <span className="font-medium text-label-2">{TOLERANCE_LABELS[String(value.risk_tolerance)]}.</span> Plan as though a CRQC arrives when there is a {formatPercent(value.risk_tolerance, 0)} chance it already exists.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 rounded-[14px] bg-fill-2 p-3.5">
          <Readout label="Planning horizon (Z)" value={formatDecimalYear(model.planningYear)} detail={`${formatYears(model.planningYears)} from today`} strong />
          <Readout label="Median arrival" value={formatDecimalYear(model.now + model.quantileYears(0.5))} detail={`80% range ${Math.floor(model.now + model.quantileYears(0.1))}–${Math.ceil(model.now + model.quantileYears(0.9))}`} />
        </div>
      </div>

      <div className="min-w-0">
        <Legend
          className="mb-2"
          items={curves.map((c) => ({ label: c.emphasis ? <span className="font-medium text-label">{c.label}</span> : c.label, color: c.color, kind: "line" as const }))}
        />
        <ProbabilityCurve
          ariaLabel={`Probability a cryptographically relevant quantum computer exists, by year, under the ${scenarioLabel(value.crqc_scenario, catalogue)} scenario`}
          series={curves}
          domain={[model.now, DOMAIN_END]}
          tolerance={value.risk_tolerance}
          marker={{ year: model.planningYear, p: value.risk_tolerance, title: "Planning horizon", value: formatDecimalYear(model.planningYear) }}
          height={chartHeight}
        />
      </div>
    </div>
  );
}

function Readout({ label, value, detail, strong }: { label: string; value: string; detail: string; strong?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-caption font-medium text-label-3">{label}</div>
      <div className={cn("mt-0.5 truncate text-label", strong ? "text-title-3" : "text-headline")}>{value}</div>
      <div className="truncate text-caption text-label-3">{detail}</div>
    </div>
  );
}
