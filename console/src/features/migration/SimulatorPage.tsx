import { useQuery } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { Select, Slider, Switch } from "@/design/components/Controls";
import { Card, CardHeader, Chip, EmptyState } from "@/design/components/Surface";
import { api } from "@/lib/api";
import { formatDecimalYear, formatPercent, formatYears } from "@/lib/format";
import { ThreatModel } from "@/lib/horizon";
import type { RiskRow, ScenarioKey } from "@/lib/types";
import { ProbabilityCurve } from "@/viz/charts/ProbabilityCurve";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { series } from "@/viz/core/tokens";
import { KindGlyph } from "../discovery/vocab";
import { useOrganisationModel } from "../horizon/useThreatModel";
import { Page, PageSkeleton } from "../shell/Page";

type ScenarioChoice = "current" | ScenarioKey;
const HYBRID_FIRST_YEARS = 0.5;

interface Settings {
  delay: number;
  capacity: number; // 1 = as estimated; 2 = twice as fast
  hybridFirst: boolean;
}

/** Expected exposure of every quantum-vulnerable artefact under a plan and a threat model. */
function simulate(rows: RiskRow[], model: ThreatModel, s: Settings) {
  let harvest = 0;
  let forge = 0;
  let weighted = 0;
  const contributions: { row: RiskRow; p: number }[] = [];
  for (const row of rows) {
    if (row.classification.mosca === "not-affected" || row.quantum !== "vulnerable") continue;
    const confidentiality = row.roles.includes("confidentiality");
    const effort = confidentiality && s.hybridFirst ? HYBRID_FIRST_YEARS : row.migration.years / s.capacity;
    const finish = s.delay + effort;
    // Confidentiality: data protected until the migration finishes stays sensitive for X more years.
    // Authenticity: forgery is possible if a CRQC arrives before the migration finishes.
    const p = model.probabilityBy(confidentiality ? finish + row.mosca.x : finish);
    if (confidentiality) harvest += p;
    else forge += p;
    weighted += p * row.impact.value;
    contributions.push({ row, p });
  }
  contributions.sort((a, b) => b.p * b.row.impact.value - a.p * a.row.impact.value);
  return { harvest, forge, weighted, contributions };
}

export default function SimulatorPage() {
  const { model: orgModel, catalogue } = useOrganisationModel();
  const register = useQuery({ queryKey: ["risk", "register", "all"], queryFn: () => api.get<{ items: RiskRow[]; total: number }>("/risk/register", { limit: 2000 }) });
  if (register.isPending || !orgModel || !catalogue) return <PageSkeleton />;
  const rows = register.data?.items ?? [];
  if (!rows.some((r) => r.quantum === "vulnerable")) {
    return (
      <Page title="What-if Simulator">
        <Card>
          <EmptyState icon={<SlidersHorizontal />} title="Nothing to simulate" message="The simulator needs quantum-vulnerable cryptography from a scan." />
        </Card>
      </Page>
    );
  }
  return <Simulator rows={rows} orgModel={orgModel} catalogue={catalogue} />;
}

function Simulator({ rows, orgModel, catalogue }: { rows: RiskRow[]; orgModel: ThreatModel; catalogue: NonNullable<ReturnType<typeof useOrganisationModel>["catalogue"]> }) {
  const navigate = useNavigate();
  const [scenario, setScenario] = useState<ScenarioChoice>("current");
  const [settings, setSettings] = useState<Settings>({ delay: 0, capacity: 1, hybridFirst: false });
  const model = useMemo(
    () => (scenario === "current" ? orgModel : new ThreatModel({ scenario, tolerance: orgModel.tolerance }, catalogue, orgModel.now)),
    [scenario, orgModel, catalogue],
  );
  const baseline = useMemo(() => simulate(rows, orgModel, { delay: 0, capacity: 1, hybridFirst: false }), [rows, orgModel]);
  const result = useMemo(() => simulate(rows, model, settings), [rows, model, settings]);
  const harvestable = rows.filter((r) => r.quantum === "vulnerable" && r.roles.includes("confidentiality")).length || 1;

  const curve = useMemo(() => {
    const points = (hybridFirst: boolean) =>
      Array.from({ length: 41 }, (_, i) => {
        const delay = i / 4;
        return { year: model.now + delay, p: simulate(rows, model, { ...settings, delay, hybridFirst }).harvest / harvestable };
      });
    return { plan: points(false), hybrid: points(true) };
  }, [rows, model, settings, harvestable]);

  const delta = (now: number, base: number) => {
    const d = now - base;
    if (Math.abs(d) < 0.05) return "Same as starting now with the estimated plan";
    return `${d > 0 ? "+" : "−"}${Math.abs(d).toFixed(1)} against starting now with the estimated plan`;
  };

  return (
    <Page
      title="What-if Simulator"
      subtitle="Change when the migration starts, how fast the team works, whether hybrid key exchange goes first and which threat scenario you plan for. The expected exposure of every quantum-vulnerable artefact updates as you move."
      width="wide"
    >
      <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="space-y-6 self-start">
          <div>
            <Select
              label="Threat scenario"
              value={scenario}
              onChange={setScenario}
              options={[
                { value: "current", label: "Our threat model" },
                { value: "aggressive", label: "Aggressive (CRQC early 2030s)" },
                { value: "moderate", label: "Moderate (mid-2030s)" },
                { value: "conservative", label: "Conservative (2040s)" },
              ]}
            />
            <p className="mt-2 text-footnote text-label-3">
              Median arrival {formatDecimalYear(model.medianYear)}; planning horizon {formatDecimalYear(model.planningYear)}.
            </p>
          </div>
          <Control label="Migration starts" value={settings.delay === 0 ? "Now" : `In ${formatYears(settings.delay)}`}>
            <Slider label="Migration start delay" min={0} max={10} step={0.25} value={settings.delay} onChange={(delay) => setSettings((s) => ({ ...s, delay }))} />
          </Control>
          <Control label="Team capacity" value={`${Math.round(settings.capacity * 100)}% of the estimate`}>
            <Slider label="Team capacity" min={0.5} max={2} step={0.1} value={settings.capacity} onChange={(capacity) => setSettings((s) => ({ ...s, capacity }))} />
          </Control>
          <label className="flex items-start justify-between gap-4">
            <span>
              <span className="block text-callout font-medium text-label">Hybrid key exchange first</span>
              <span className="block text-footnote text-label-3">Deploy X25519MLKEM768 everywhere within six months, before anything else.</span>
            </span>
            <Switch label="Hybrid key exchange first" checked={settings.hybridFirst} onChange={(hybridFirst) => setSettings((s) => ({ ...s, hybridFirst }))} />
          </label>
        </Card>

        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <Outcome label="Harvested traffic decrypted" value={result.harvest} detail={delta(result.harvest, baseline.harvest)} hint="Expected number of key exchanges whose recorded data is read while still sensitive." />
            <Outcome label="Signatures forgeable" value={result.forge} detail={delta(result.forge, baseline.forge)} hint="Expected number of signature artefacts still in use when a CRQC exists." />
            <Outcome label="Risk-weighted exposure" value={result.weighted} detail={delta(result.weighted, baseline.weighted)} hint="The same, weighted by each system's business impact." />
          </div>
          <Card>
            <CardHeader title="The cost of waiting" subtitle="Share of harvestable key exchanges whose data is decrypted while still sensitive, by the year the migration starts." />
            <ProbabilityCurve
              ariaLabel="Share of harvestable data exposed by migration start year"
              domain={[model.now, model.now + 10]}
              height={300}
              readout="Share of harvestable data exposed"
              series={[
                { id: "plan", label: "Migrate as planned", color: series[1], points: curve.plan, emphasis: !settings.hybridFirst },
                { id: "hybrid", label: "Hybrid key exchange first", color: series[2], points: curve.hybrid, emphasis: settings.hybridFirst },
              ]}
              marker={{ year: model.now + settings.delay, p: result.harvest / harvestable, title: "Your plan", value: formatPercent(result.harvest / harvestable) }}
            />
            <div className="mt-2 flex gap-4 text-footnote text-label-2">
              <span className="flex items-center gap-1.5"><span className="h-[2px] w-3 rounded-full" style={{ background: series[1] }} /> Migrate as planned</span>
              <span className="flex items-center gap-1.5"><span className="h-[2px] w-3 rounded-full" style={{ background: series[2] }} /> Hybrid key exchange first</span>
            </div>
          </Card>
          <Card padded={false}>
            <div className="px-5 pt-5">
              <CardHeader title="Where the exposure comes from" subtitle="The artefacts contributing most under these settings." />
            </div>
            <ul className="px-2 pb-2">
              {result.contributions.slice(0, 8).map(({ row, p }) => (
                <li key={row.id}>
                  <button type="button" onClick={() => navigate(`/inventory/${row.id}`)} className="hover-light flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left transition-colors hover:bg-fill-2">
                    <KindGlyph kind={row.kind} size={28} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-callout font-medium text-label">{row.name}</span>
                      <span className="flex items-center gap-1.5 text-caption text-label-3">
                        <Chip>{row.system.code}</Chip> {row.roles.includes("confidentiality") ? `data sensitive for ${formatYears(row.mosca.x)}` : "signature"} · {row.migration.label.toLowerCase()}
                      </span>
                    </span>
                    <span className="w-24 shrink-0">
                      <span className="block h-1.5 overflow-hidden rounded-full bg-fill">
                        <span className="block h-full rounded-full bg-[var(--status-critical)] transition-[width] duration-300" style={{ width: `${p * 100}%` }} />
                      </span>
                      <span className="mt-0.5 block text-right text-caption tabular text-label-2">{formatPercent(p)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </Page>
  );
}

function Control({ label, value, children }: { label: string; value: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-footnote font-semibold text-label-2">{label}</span>
        <span className="text-subhead font-medium tabular text-label">{value}</span>
      </div>
      {children}
    </div>
  );
}

function Outcome({ label, value, detail, hint }: { label: string; value: number; detail: string; hint: string }) {
  return (
    <Card title={hint}>
      <div className="text-subhead font-medium text-label-2">{label}</div>
      <AnimatedNumber value={value} format={(n) => n.toFixed(1)} className="mt-2 block text-title-1 tabular text-label" />
      <p className="mt-1 text-footnote text-label-3">{detail}</p>
    </Card>
  );
}

