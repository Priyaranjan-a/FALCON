import { ArrowRight, Lock, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Slider } from "@/design/components/Controls";
import { Card, CardHeader, Skeleton } from "@/design/components/Surface";
import { useCan } from "@/lib/access";
import { formatDecimalYear, formatMilestoneDate, formatPercent, formatYears } from "@/lib/format";
import { mosca } from "@/lib/horizon";
import { useHorizon, useMilestones, useOrganisation, useSystems, useUpdateThreatModel } from "@/lib/queries";
import type { Milestone, MilestoneCatalogue, MoscaStatus, ThreatModelSettings } from "@/lib/types";
import { MILESTONE_COLORS, MilestoneTimeline } from "@/viz/charts/MilestoneTimeline";
import { MOSCA_COLORS, MoscaChart, STATUS_META } from "@/viz/charts/MoscaChart";
import { ChartFrame } from "@/viz/core/ChartFrame";
import { Page, PageSkeleton } from "../shell/Page";
import { buildModel, sameSettings, scenarioLabel } from "./model";
import { ThreatModelEditor } from "./ThreatModelEditor";

export default function HorizonPage() {
  const horizon = useHorizon();
  const org = useOrganisation();
  const canManage = useCan("threat.manage");
  const save = useUpdateThreatModel();
  const [draft, setDraft] = useState<ThreatModelSettings | null>(null);
  const location = useLocation();

  const saved: ThreatModelSettings | null = org.data
    ? {
        crqc_scenario: org.data.threat_model.crqc_scenario,
        crqc_median_year: org.data.threat_model.crqc_median_year,
        crqc_uncertainty: org.data.threat_model.crqc_uncertainty,
        risk_tolerance: org.data.threat_model.risk_tolerance,
      }
    : null;

  useEffect(() => {
    if (saved && !draft) setDraft(saved);
  }, [saved, draft]);

  useEffect(() => {
    if (location.hash === "#regulation") document.getElementById("regulation")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [location.hash, horizon.data]);

  if (horizon.isPending || org.isPending || !draft || !saved) return <PageSkeleton />;
  if (!horizon.data) return null;
  const catalogue = horizon.data.catalogue;
  const dirty = !sameSettings(draft, saved);

  const commit = () =>
    save.mutate(draft, {
      onSuccess: (o) => toast.success("Threat model saved", { description: `Planning horizon is now ${formatDecimalYear(o.threat_model.planning_year)}. Every system has been re-scored.` }),
      onError: (e) => toast.error(e.message),
    });

  return (
    <Page
      title="Threat Horizon"
      subtitle="When a cryptographically relevant quantum computer (CRQC) could exist, how much of that risk you accept, and what it means for every system you depend on."
      actions={
        canManage ? (
          <>
            <Button variant="gray" icon={<RotateCcw />} disabled={!dirty || save.isPending} onClick={() => setDraft(saved)}>
              Revert
            </Button>
            <Button variant="filled" disabled={!dirty} loading={save.isPending} onClick={commit}>
              Save threat model
            </Button>
          </>
        ) : (
          <span className="flex items-center gap-1.5 text-subhead text-label-3">
            <Lock className="size-3.5" /> Read-only for your role
          </span>
        )
      }
    >
      <div className="space-y-4">
        <Card>
          <CardHeader
            title="Arrival model"
            subtitle={
              dirty
                ? "Previewing changes. Nothing is saved until you choose Save threat model."
                : `Saved: ${scenarioLabel(saved.crqc_scenario, catalogue)} scenario at ${formatPercent(saved.risk_tolerance, 0)} tolerance.`
            }
            actions={dirty && <span className="rounded-full bg-accent-tint px-2 py-0.5 text-footnote font-semibold text-accent-ink">Preview</span>}
          />
          <ThreatModelEditor catalogue={catalogue} value={draft} onChange={setDraft} disabled={!canManage} chartHeight={320} />
          <p className="mt-4 text-footnote text-label-3">
            Scenarios are planning assumptions, not forecasts. Calibrate them against the threat intelligence your organisation relies on, such as the Global Risk Institute’s annual Quantum Threat Timeline report.
          </p>
        </Card>

        <SystemsUnderModel draft={draft} saved={saved} />

        <MoscaCalculator draft={draft} />

        <RegulationCard horizonYear={buildModel(draft, catalogue).planningYear} />
      </div>
    </Page>
  );
}

function SystemsUnderModel({ draft, saved }: { draft: ThreatModelSettings; saved: ThreatModelSettings }) {
  const canRead = useCan("systems.read");
  const systems = useSystems({});
  const horizon = useHorizon();
  const navigate = useNavigate();
  const catalogue = horizon.data?.catalogue;

  const scored = useMemo(() => {
    if (!catalogue || !systems.data) return null;
    const draftModel = buildModel(draft, catalogue);
    const savedModel = buildModel(saved, catalogue);
    return systems.data.items
      .filter((s) => s.lifecycle !== "retired")
      .map((s) => ({ system: s, draft: mosca(draftModel, s.data_shelf_life_years, s.migration_years), saved: mosca(savedModel, s.data_shelf_life_years, s.migration_years) }))
      .sort((a, b) => b.draft.exposure_years - a.draft.exposure_years);
  }, [catalogue, systems.data, draft, saved]);

  if (!canRead) return null;
  if (!scored || !catalogue) return <Skeleton className="h-[240px] rounded-[18px]" />;
  if (scored.length === 0) return null;

  const count = (key: "draft" | "saved", status: MoscaStatus) => scored.filter((r) => r[key].status === status).length;
  const changed = !sameSettings(draft, saved);
  const z = buildModel(draft, catalogue).planningYears;

  return (
    <ChartFrame
      title="Your systems under this model"
      subtitle="Every registered system re-scored as you adjust the scenario and tolerance."
      legend={[
        { label: "Migration time (Y)", color: MOSCA_COLORS.migration },
        { label: "Data shelf-life (X)", color: MOSCA_COLORS.shelfLife },
        { label: "Beyond the horizon", color: "var(--chart-zone)", kind: "zone" },
      ]}
      actions={
        <div className="flex items-center gap-3 pr-1">
          {(["exposed", "watch", "clear"] as MoscaStatus[]).map((status) => {
            const meta = STATUS_META[status];
            const now = count("draft", status);
            const before = count("saved", status);
            return (
              <span key={status} className="flex items-center gap-1.5 text-footnote text-label-2">
                <meta.icon className="size-3.5" style={{ color: meta.color }} strokeWidth={2.25} />
                <span className="font-semibold tabular text-label">{now}</span> {meta.label.toLowerCase()}
                {changed && now !== before && <span className="tabular text-label-3">(was {before})</span>}
              </span>
            );
          })}
        </div>
      }
      table={{
        caption: "Systems re-scored under the previewed threat model",
        rows: scored,
        rowKey: (r) => r.system.id,
        columns: [
          { key: "code", header: "Code", cell: (r) => r.system.code },
          { key: "name", header: "System", cell: (r) => r.system.name },
          { key: "xy", header: "X + Y", numeric: true, cell: (r) => (r.draft.x + r.draft.y).toFixed(1) },
          { key: "z", header: "Z", numeric: true, cell: (r) => r.draft.z.toFixed(1) },
          { key: "status", header: "Status", cell: (r) => STATUS_META[r.draft.status].label },
          { key: "was", header: "Saved status", cell: (r) => STATUS_META[r.saved.status].label },
          { key: "p", header: "CRQC first", numeric: true, cell: (r) => formatPercent(r.draft.probability) },
        ],
      }}
    >
      <MoscaChart
        ariaLabel="Registered systems under the previewed threat model"
        rows={scored.slice(0, 12).map((r) => ({ id: r.system.id, code: r.system.code, name: r.system.name, x: r.draft.x, y: r.draft.y, status: r.draft.status, probability: r.draft.probability }))}
        z={z}
        onSelect={(id) => navigate(`/systems/${id}`)}
      />
      {scored.length > 12 && (
        <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/systems")}>
          All {scored.length} systems
        </Button>
      )}
    </ChartFrame>
  );
}

function MoscaCalculator({ draft }: { draft: ThreatModelSettings }) {
  const horizon = useHorizon();
  const [x, setX] = useState(10);
  const [y, setY] = useState(3);
  const catalogue = horizon.data?.catalogue;
  if (!catalogue) return null;
  const result = mosca(buildModel(draft, catalogue), x, y);
  const meta = STATUS_META[result.status];

  return (
    <Card>
      <CardHeader title="Mosca calculator" subtitle="Test any combination of data shelf-life and migration time against the model above." />
      <div className="grid gap-8 lg:grid-cols-[320px_1fr]">
        <div className="space-y-5">
          <CalcSlider label="Data shelf-life (X)" value={x} min={0} max={40} step={1} onChange={setX} />
          <CalcSlider label="Migration time (Y)" value={y} min={0.5} max={12} step={0.5} onChange={setY} />
        </div>
        <div className="min-w-0">
          <div className="mb-4 flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <div className="flex items-center gap-2">
              <meta.icon className="size-5" style={{ color: meta.color }} strokeWidth={2.25} />
              <span className="text-title-3 text-label">{meta.label}</span>
            </div>
            <span className="text-subhead text-label-2">
              X + Y = <strong className="font-semibold tabular text-label">{formatYears(x + y)}</strong> against Z = <strong className="font-semibold tabular text-label">{formatYears(result.z)}</strong>
            </span>
            <span className="text-subhead text-label-2">
              <strong className="font-semibold tabular text-label">{formatPercent(result.probability)}</strong> chance a CRQC arrives first
            </span>
          </div>
          <MoscaChart ariaLabel="Mosca calculator result" rows={[{ id: "calc", code: "CALC", name: "Your scenario", x, y, status: result.status, probability: result.probability }]} z={result.z} labelWidth={150} />
          <p className="text-footnote text-label-3">
            {result.overdue_years > 0
              ? `Migration should have started ${formatYears(result.overdue_years)} ago to finish inside the horizon.`
              : `Start migration by ${formatDecimalYear(result.start_by)} to finish inside the horizon.`}
          </p>
        </div>
      </div>
    </Card>
  );
}

function CalcSlider({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-subhead font-medium text-label-2">{label}</span>
        <span className="text-headline tabular text-label">{formatYears(value)}</span>
      </div>
      <Slider label={label} value={value} min={min} max={max} step={step} onChange={onChange} />
    </div>
  );
}

const LANE_ORDER = ["NIST", "NSA", "WH", "EU", "NCSC", "CCCS", "ASD"];

function RegulationCard({ horizonYear }: { horizonYear: number }) {
  const catalogue = useMilestones();
  const [region, setRegion] = useState<string>("all");
  const [selected, setSelected] = useState<string | null>(null);

  if (catalogue.isPending) return <Skeleton className="h-[360px] rounded-[18px]" />;
  if (!catalogue.data) return null;
  const data: MilestoneCatalogue = catalogue.data;
  const regions = ["all", ...new Set(LANE_ORDER.map((k) => data.authorities[k]?.region).filter(Boolean))];
  const lanes = LANE_ORDER.filter((k) => data.authorities[k] && (region === "all" || data.authorities[k].region === region)).map((k) => ({
    key: k,
    label: data.authorities[k].name === "Canadian Centre for Cyber Security" ? "CCCS" : data.authorities[k].name,
    sub: data.authorities[k].region,
  }));
  const milestones = data.milestones.filter((m) => lanes.some((l) => l.key === m.authority));
  const now = new Date();
  const nowYear = now.getUTCFullYear() + (now.getUTCMonth() + now.getUTCDate() / 31) / 12;
  const detail = milestones.find((m) => m.id === selected) ?? milestones.find((m) => new Date(m.date) >= now);

  return (
    <div id="regulation" className="scroll-mt-16">
      <ChartFrame
        title="Regulatory timeline"
        subtitle={`Published post-quantum milestones by authority, against today and your planning horizon. Catalogue ${data.version}.`}
        legend={[
          { label: "Deadline", color: MILESTONE_COLORS.deadline, kind: "rect" },
          { label: "Publication", color: MILESTONE_COLORS.publication, kind: "dot" },
          { label: "Beyond your horizon", color: "var(--chart-zone)", kind: "zone" },
        ]}
        actions={
          <div className="flex flex-wrap gap-1">
            {regions.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRegion(r)}
                aria-pressed={region === r}
                className={cn("h-7 rounded-full px-2.5 text-footnote font-medium transition-colors focus-visible:focus-ring", region === r ? "bg-label text-surface" : "bg-fill-2 text-label-2 hover:bg-fill")}
              >
                {r === "all" ? "All regions" : r}
              </button>
            ))}
          </div>
        }
        table={{
          caption: "Regulatory milestones",
          rows: milestones,
          rowKey: (m: Milestone) => m.id,
          columns: [
            { key: "date", header: "Date", cell: (m) => formatMilestoneDate(m.date, m.precision) },
            { key: "authority", header: "Authority", cell: (m) => m.authority_name },
            { key: "framework", header: "Framework", cell: (m) => m.framework },
            { key: "title", header: "Milestone", cell: (m) => m.title },
            { key: "kind", header: "Kind", cell: (m) => (m.kind === "deadline" ? "Deadline" : "Publication") },
          ],
        }}
      >
        <MilestoneTimeline
          ariaLabel="Regulatory milestones by authority"
          milestones={milestones}
          lanes={lanes}
          domain={[2024, 2036.5]}
          now={nowYear}
          horizon={horizonYear}
          selected={detail?.id ?? null}
          onSelect={setSelected}
        />
        {detail && (
          <div className="mt-5 rounded-[14px] bg-fill-2 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="text-headline text-label">{detail.title}</div>
              <div className="text-footnote font-medium tabular text-label-2">{formatMilestoneDate(detail.date, detail.precision)}</div>
            </div>
            <div className="mt-0.5 text-footnote text-label-3">
              {detail.authority_name} · {detail.framework}
            </div>
            <p className="mt-2 text-subhead text-label-2">{detail.detail}</p>
            <p className="mt-2 text-caption text-label-3">Source: {detail.source}</p>
          </div>
        )}
      </ChartFrame>
      <p className="mt-2 px-1 text-footnote text-label-3">{data.note}</p>
    </div>
  );
}
