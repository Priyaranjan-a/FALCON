import { ArrowRight, CalendarClock, Clock, Radio, Check, CircleAlert, Hourglass, Plus, Radar, Server, TriangleAlert } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Card, CardHeader, EmptyState, Skeleton } from "@/design/components/Surface";
import { useCan } from "@/lib/access";
import { daysUntil, formatDecimalYear, formatInt, formatMilestoneDate, formatPercent, formatRelative, formatYears } from "@/lib/format";
import { useAccount, useOverview } from "@/lib/queries";
import type { Overview, Tally } from "@/lib/types";
import { Meter } from "@/viz/charts/Meter";
import { MOSCA_COLORS, MoscaChart } from "@/viz/charts/MoscaChart";
import { ProbabilityCurve } from "@/viz/charts/ProbabilityCurve";
import { Ring } from "@/viz/charts/Ring";
import { Stat } from "@/viz/charts/Stat";
import { ChartFrame } from "@/viz/core/ChartFrame";
import { ramp } from "@/viz/core/tokens";
import { ASSESSED, KIND_ORDER, KindGlyph, KINDS, QUANTUM, QUANTUM_ORDER, ScanStatusBadge, SourceGlyph } from "../discovery/vocab";
import { SCENARIO_COLORS, scenarioLabel } from "../horizon/model";
import { BAND_ORDER, BANDS, RiskBadge } from "../risk/vocab";
import { useOrganisationModel } from "../horizon/useThreatModel";
import { Page, PageSkeleton } from "../shell/Page";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

/** Ordinal tallies arrive highest rank first; the ramp runs low → high. */
function ordinalSegments(tallies: Tally[]) {
  const n = tallies.length;
  const steps = n >= 5 ? [0, 1, 2, 3, 4] : [0, 1, 3, 4];
  return tallies.map((t, i) => ({ key: t.key, label: t.label, value: t.count, color: ramp[steps[n - 1 - i]] }));
}

export default function OverviewPage() {
  const overview = useOverview();
  const account = useAccount().data;
  const firstName = account?.user.name.split(" ")[0];

  if (overview.isPending) return <PageSkeleton />;
  if (overview.isError) {
    return (
      <Page title="Overview">
        <Card>
          <EmptyState icon={<CircleAlert />} title="The overview couldn’t be loaded" message={overview.error.message} action={<Button variant="tinted" onClick={() => overview.refetch()}>Try again</Button>} />
        </Card>
      </Page>
    );
  }

  const data = overview.data;
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

  return (
    <Page eyebrow={`${greeting()}${firstName ? `, ${firstName}` : ""}`} title="Overview" subtitle={`${data.organisation.name} · ${today}`}>
      <div className={cn("space-y-4 transition-opacity duration-200", overview.isPlaceholderData && "opacity-60")}>
        <HeadlineRow data={data} />
        <ExposureCard data={data} />
        {data.risk && data.risk.total > 0 && <RiskRow data={data} />}
        {data.discovery && <DiscoveryRow data={data} />}
        <div className="grid gap-4 lg:grid-cols-3">
          <PortfolioCard data={data} />
          <ReadinessCard data={data} />
          <DeadlinesCard data={data} />
        </div>
      </div>
    </Page>
  );
}

function HeadlineRow({ data }: { data: Overview }) {
  const navigate = useNavigate();
  const { model, catalogue } = useOrganisationModel();
  const h = data.horizon;
  const s = data.systems;
  const next = data.milestones[0];
  const critical = s.by_criticality.find((t) => t.key === "critical")?.count ?? 0;
  const curve = useMemo(() => (model ? model.curve(2050) : []), [model]);

  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <Card className="flex flex-col lg:col-span-2 lg:row-span-2">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-subhead font-medium text-label-2">Quantum planning horizon</div>
            <div className="mt-2 text-hero text-label">{formatDecimalYear(h.planning_year)}</div>
            <div className="mt-1 text-subhead text-label-2">
              {formatYears(h.planning_years)} from today · {scenarioLabel(h.scenario, catalogue ?? undefined)} scenario at {formatPercent(h.tolerance, 0)} tolerance
            </div>
          </div>
          <Button variant="gray" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/horizon")}>
            Horizon
          </Button>
        </div>
        <div className="mt-4 min-h-[180px] flex-1">
          {model ? (
            <ProbabilityCurve
              ariaLabel="Probability a cryptographically relevant quantum computer exists, by year"
              series={[{ id: h.scenario, label: scenarioLabel(h.scenario, catalogue ?? undefined), color: SCENARIO_COLORS[h.scenario], points: curve, emphasis: true }]}
              domain={[model.now, 2050]}
              tolerance={h.tolerance}
              marker={{ year: model.planningYear, p: h.tolerance, title: "Planning horizon", value: formatDecimalYear(model.planningYear) }}
              height={210}
            />
          ) : (
            <Skeleton className="h-[210px]" />
          )}
        </div>
      </Card>
      <Stat label="Systems registered" icon={<Server />} value={s.active} format={(n) => formatInt(Math.round(n))} detail={s.active ? `${critical} mission-critical` : "Register your first system"} />
      <Stat
        label="Exposed now"
        icon={<TriangleAlert />}
        value={s.mosca.exposed}
        format={(n) => formatInt(Math.round(n))}
        detail={s.active ? `of ${s.active} · X + Y exceeds Z` : "Nothing to assess yet"}
        accessory={s.active > 0 ? <ExposureRing exposed={s.mosca.exposed} watch={s.mosca.watch} total={s.active} /> : undefined}
      />
      <Stat
        label="Overdue migrations"
        icon={<Hourglass />}
        value={s.mosca.overdue}
        format={(n) => formatInt(Math.round(n))}
        detail={s.mosca.overdue ? "Should already have started" : "None past their start date"}
      />
      <Stat
        label="Next regulatory deadline"
        icon={<CalendarClock />}
        value={next ? Math.max(0, daysUntil(next.date)) : 0}
        format={(n) => (next ? `${formatInt(Math.round(n))} days` : "—")}
        detail={next ? `${next.authority_name} · ${next.title}` : "No upcoming deadlines"}
      />
    </div>
  );
}

function ExposureRing({ exposed, watch, total }: { exposed: number; watch: number; total: number }) {
  return (
    <Ring value={exposed / total} size={52} thickness={6} color="var(--status-critical)" ariaLabel={`${exposed} of ${total} systems exposed, ${watch} on watch`}>
      <span className="text-caption font-semibold tabular text-label-2">{Math.round((exposed / total) * 100)}%</span>
    </Ring>
  );
}

function ExposureCard({ data }: { data: Overview }) {
  const navigate = useNavigate();
  const canWrite = useCan("systems.write");
  const plane = data.systems.plane;
  const rows = plane.slice(0, 8).map((p) => ({ id: p.id, code: p.code, name: p.name, x: p.x, y: p.y, status: p.status, probability: p.probability }));
  const z = data.horizon.planning_years;

  if (plane.length === 0) {
    return (
      <Card>
        <CardHeader title="Mosca exposure" subtitle="Where each system’s data outlives your planning horizon." />
        <EmptyState
          compact
          icon={<Server />}
          title="No systems to assess yet"
          message="Register a system and FALCON places it against your planning horizon immediately."
          action={canWrite && <Button variant="filled" icon={<Plus />} onClick={() => navigate("/systems?register=1")}>Register a system</Button>}
        />
      </Card>
    );
  }

  return (
    <ChartFrame
      title="Mosca exposure"
      subtitle={`${plane.length > 8 ? "The eight most exposed systems" : "Every registered system"}: migration time (Y) plus data shelf-life (X) against the planning horizon (Z).`}
      legend={[
        { label: "Migration time (Y)", color: MOSCA_COLORS.migration },
        { label: "Data shelf-life (X)", color: MOSCA_COLORS.shelfLife },
        { label: "Beyond the horizon", color: "var(--chart-zone)", kind: "zone" },
      ]}
      actions={
        plane.length > 8 && (
          <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/systems")}>
            All {plane.length}
          </Button>
        )
      }
      table={{
        caption: "Mosca exposure by system",
        rows: plane,
        rowKey: (p) => p.id,
        columns: [
          { key: "code", header: "Code", cell: (p) => p.code },
          { key: "name", header: "System", cell: (p) => p.name },
          { key: "y", header: "Y (years)", numeric: true, cell: (p) => p.y },
          { key: "x", header: "X (years)", numeric: true, cell: (p) => p.x },
          { key: "z", header: "Z (years)", numeric: true, cell: (p) => p.z.toFixed(1) },
          { key: "exposure", header: "X + Y − Z", numeric: true, cell: (p) => p.exposure_years.toFixed(1) },
          { key: "p", header: "CRQC first", numeric: true, cell: (p) => formatPercent(p.probability) },
          { key: "status", header: "Status", cell: (p) => p.status },
        ],
      }}
    >
      <MoscaChart ariaLabel="Mosca exposure of registered systems" rows={rows} z={z} onSelect={(id) => navigate(`/systems/${id}`)} />
    </ChartFrame>
  );
}

function PortfolioCard({ data }: { data: Overview }) {
  const s = data.systems;
  return (
    <Card>
      <CardHeader title="Portfolio profile" subtitle={`${s.active} active system${s.active === 1 ? "" : "s"}`} />
      <div className="space-y-6">
        <MeterBlock title="Business criticality" tallies={s.by_criticality} />
        <MeterBlock title="Data classification" tallies={s.by_classification} />
        <MeterBlock title="Exposure" tallies={s.by_exposure} />
      </div>
    </Card>
  );
}

function MeterBlock({ title, tallies }: { title: string; tallies: Tally[] }) {
  return (
    <div>
      <div className="mb-2 text-footnote font-semibold text-label-2">{title}</div>
      <Meter ariaLabel={`${title}: ${tallies.map((t) => `${t.label} ${t.count}`).join(", ")}`} segments={ordinalSegments(tallies)} />
    </div>
  );
}

function ReadinessCard({ data }: { data: Overview }) {
  const navigate = useNavigate();
  const done = data.checklist.filter((c) => c.done).length;
  const total = data.checklist.length;
  const targets: Record<string, string> = { threat_model: "/horizon", systems: "/systems", owners: "/systems", team: "/members", discovery: "/systems" };
  return (
    <Card>
      <CardHeader title="Getting ready" subtitle="The foundations of a migration programme." />
      <div className="mb-5 flex items-center gap-4">
        <Ring value={done / total} size={76} thickness={8} color="var(--status-good)" ariaLabel={`${done} of ${total} steps complete`}>
          <span className="text-headline tabular text-label">
            {done}/{total}
          </span>
        </Ring>
        <p className="text-subhead text-label-2">{done === total ? "Foundations complete. Rescan sources as your systems change." : `${total - done} step${total - done === 1 ? "" : "s"} left.`}</p>
      </div>
      <ul className="space-y-0.5">
        {data.checklist.map((item) => (
          <li key={item.key}>
            <button type="button" onClick={() => navigate(targets[item.key] ?? "/")} className="flex w-full items-start gap-3 rounded-[10px] p-2 text-left transition-colors hover:bg-fill-2 focus-visible:focus-ring">
              <span className={cn("mt-0.5 grid size-[18px] shrink-0 place-items-center rounded-full", item.done ? "bg-good" : "shadow-[inset_0_0_0_1.5px_var(--separator-strong)]")}>
                {item.done && <Check className="size-3 text-white" strokeWidth={3.25} />}
              </span>
              <span className="min-w-0">
                <span className={cn("block text-callout", item.done ? "text-label-2" : "font-medium text-label")}>{item.title}</span>
                <span className="block text-footnote text-label-3">{item.detail}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function DeadlinesCard({ data }: { data: Overview }) {
  const navigate = useNavigate();
  return (
    <Card>
      <CardHeader
        title="Upcoming deadlines"
        subtitle="Published post-quantum milestones."
        actions={
          <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/horizon#regulation")}>
            Timeline
          </Button>
        }
      />
      <ol className="relative space-y-4 before:absolute before:bottom-2 before:left-[5px] before:top-2 before:w-px before:bg-separator">
        {data.milestones.slice(0, 5).map((m) => {
          const days = daysUntil(m.date);
          return (
            <li key={m.id} className="relative flex gap-3 pl-0">
              <span className={cn("relative mt-1.5 size-[11px] shrink-0 rounded-full ring-2 ring-[var(--surface)]", m.kind === "deadline" ? "bg-[var(--series-1)]" : "bg-[var(--series-3)]")} />
              <div className="min-w-0">
                <div className="text-callout font-medium text-label">{m.title}</div>
                <div className="text-footnote text-label-3">
                  {m.authority_name} · {m.framework} · {formatMilestoneDate(m.date, m.precision)}
                  {days >= 0 && days < 730 && <span className="text-label-2"> · in {formatInt(days)} days</span>}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function DiscoveryRow({ data }: { data: Overview }) {
  const navigate = useNavigate();
  const canManage = useCan("sources.manage");
  const { inventory, recent_scans: scans } = data.discovery!;

  if (inventory.total === 0 && scans.length === 0) {
    return (
      <Card>
        <CardHeader title="Cryptographic inventory" subtitle="What your systems actually run on." />
        <EmptyState
          compact
          icon={<Radar />}
          title="Discover your cryptography"
          message="Point FALCON at a system’s code, archives, container images or live TLS endpoints. It finds the algorithms, keys, certificates, protocols, libraries, hardware and cloud keys in use."
          action={canManage && <Button variant="filled" icon={<Server />} onClick={() => navigate("/systems")}>Choose a system to scan</Button>}
        />
      </Card>
    );
  }

  const segments = QUANTUM_ORDER.map((q) => ({
    key: q,
    label: QUANTUM[q].label,
    color: QUANTUM[q].color,
    value: ASSESSED.reduce((n, k) => n + (inventory.matrix[k]?.[q] ?? 0), 0),
  })).filter((s) => s.key !== "unknown" || s.value > 0);
  const vulnerable = segments.find((s) => s.key === "vulnerable")?.value ?? 0;
  const assessed = segments.reduce((n, s) => n + s.value, 0);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader
          title="Cryptographic inventory"
          subtitle={`${formatInt(inventory.total)} artefacts across ${inventory.systems} system${inventory.systems === 1 ? "" : "s"}${assessed ? ` · ${formatPercent(vulnerable / assessed)} of assessed artefacts are quantum-vulnerable` : ""}.`}
          actions={
            <Button variant="gray" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/inventory")}>
              Inventory
            </Button>
          }
        />
        <div className="mb-5 grid grid-cols-4 gap-1 sm:grid-cols-7">
          {KIND_ORDER.map((kind) => (
            <button
              key={kind}
              type="button"
              onClick={() => navigate(`/inventory?kind=${kind}`)}
              className="flex flex-col items-center gap-1 rounded-[12px] px-1 py-2 text-center transition-colors hover:bg-fill-2 focus-visible:focus-ring"
            >
              <KindGlyph kind={kind} size={28} />
              <span className={cn("text-headline tabular", inventory.by_kind[kind] ? "text-label" : "text-label-4")}>{formatInt(inventory.by_kind[kind] ?? 0)}</span>
              <span className="w-full truncate text-caption text-label-3">{KINDS[kind].label}</span>
            </button>
          ))}
        </div>
        <div className="mb-2 text-footnote font-semibold text-label-2">Quantum status of assessed artefacts</div>
        <Meter segments={segments} unit="artefacts" ariaLabel={`Quantum status: ${segments.map((s) => `${s.label} ${s.value}`).join(", ")}`} />
      </Card>
      <Card padded={false} className="flex flex-col">
        <div className="px-5 pt-5">
          <CardHeader
            title="Recent scans"
            actions={
              <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/scans")}>
                All
              </Button>
            }
          />
        </div>
        <ul className="-mt-2 flex-1 px-2 pb-2">
          {scans.slice(0, 5).map((scan) => (
            <li key={scan.id}>
              <button type="button" onClick={() => navigate(`/scans/${scan.id}`)} className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left transition-colors hover:bg-fill-2 focus-visible:focus-ring">
                <SourceGlyph kind={scan.source_kind} size={30} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-callout font-medium text-label">{scan.source_name}</span>
                  <span className="block truncate text-caption text-label-3">
                    {scan.system_code} · {formatRelative(scan.finished_at ?? scan.queued_at)}
                  </span>
                </span>
                {scan.status === "succeeded" ? (
                  <span className="shrink-0 text-footnote tabular text-label-2">{formatInt(scan.artefacts)}</span>
                ) : (
                  <ScanStatusBadge status={scan.status} />
                )}
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function RiskRow({ data }: { data: Overview }) {
  const navigate = useNavigate();
  const risk = data.risk!;
  const urgent = risk.bands.critical + risk.bands.high;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader
          title="Quantum risk"
          subtitle={`${formatInt(urgent)} of ${formatInt(risk.total)} artefacts need action this cycle, scored by impact and likelihood under Mosca’s inequality.`}
          actions={
            <>
              <Button variant="gray" size="sm" icon={<Clock />} onClick={() => navigate("/time-machine")}>
                Time Machine
              </Button>
              <Button variant="gray" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate("/risk")}>
                Risk
              </Button>
            </>
          }
        />
        <Meter
          unit="artefacts"
          ariaLabel={`Risk bands: ${BAND_ORDER.map((b) => `${BANDS[b].label} ${risk.bands[b]}`).join(", ")}`}
          segments={BAND_ORDER.map((b) => ({ key: b, label: BANDS[b].label, value: risk.bands[b], color: BANDS[b].color }))}
        />
        {risk.hndl.exposed > 0 && (
          <button type="button" onClick={() => navigate("/risk?hndl=1")} className="hover-light mt-4 flex w-full items-start gap-3 rounded-[12px] bg-[var(--status-critical-tint)] px-3.5 py-3 text-left">
            <Radio className="mt-0.5 size-[18px] shrink-0 text-critical" />
            <span className="text-subhead text-label">
              <strong className="font-semibold">Harvest now, decrypt later: {formatInt(risk.hndl.exposed)} key exchanges on {risk.hndl.systems} system{risk.hndl.systems === 1 ? "" : "s"}.</strong>{" "}
              <span className="text-label-2">Traffic recorded today stays sensitive past the planning horizon.</span>
            </span>
          </button>
        )}
      </Card>
      <Card padded={false} className="flex flex-col">
        <div className="px-5 pt-5">
          <CardHeader title="Most at risk" />
        </div>
        <ul className="-mt-2 flex-1 px-2 pb-2">
          {risk.systems.filter((s) => s.artefacts > 0).map((s) => (
            <li key={s.id}>
              <button type="button" onClick={() => navigate(`/systems/${s.id}`)} className="hover-light flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left transition-colors hover:bg-fill-2">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-callout font-medium text-label">{s.name}</span>
                  <span className="block truncate text-caption text-label-3">
                    {s.code} · {formatInt(s.artefacts)} artefacts{s.hndl_exposed ? ` · ${s.hndl_exposed} harvestable` : ""}
                  </span>
                </span>
                <RiskBadge band={s.band} score={s.score} />
              </button>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
