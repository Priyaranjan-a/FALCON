import { ArrowDownWideNarrow, ArrowRight, Clock, Orbit, Radio, ScrollText, Search, ShieldAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { cn } from "@/design/cn";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { Button } from "@/design/components/Button";
import { FacetMenu } from "@/design/components/FacetMenu";
import { TextField } from "@/design/components/Field";
import { Menu, MenuContent, MenuLabel, MenuRadioGroup, MenuTrigger } from "@/design/components/Menu";
import { Card, CardHeader, Chip, EmptyState, Skeleton } from "@/design/components/Surface";
import { Table, type Column } from "@/design/components/Table";
import { formatInt, formatPercent, formatYears } from "@/lib/format";
import { useRiskRegister, useRiskSummary, useSystems, type RiskFilters } from "@/lib/queries";
import type { RiskBand, RiskRow, RiskSummary } from "@/lib/types";
import { Meter } from "@/viz/charts/Meter";
import { MoscaPlane } from "@/viz/charts/MoscaPlane";
import { RiskMatrix } from "@/viz/charts/RiskMatrix";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { ChartFrame } from "@/viz/core/ChartFrame";
import { KIND_ORDER, KindGlyph, KINDS } from "../discovery/vocab";
import { Page, PageSkeleton } from "../shell/Page";
import { BAND_ORDER, BANDS, RiskBadge, ROLES } from "./vocab";

const SORTS: { value: NonNullable<RiskFilters["sort"]>; label: string }[] = [
  { value: "score", label: "Highest risk" },
  { value: "exposure", label: "Furthest beyond the horizon" },
  { value: "probability", label: "Most likely" },
  { value: "name", label: "Name" },
];

export default function RiskPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const system = params.get("system") ?? undefined;
  const summary = useRiskSummary(system);

  const filters: RiskFilters = useMemo(
    () => ({
      system,
      band: params.getAll("band"),
      kind: params.getAll("kind"),
      role: params.get("role") ?? undefined,
      hndl: params.get("hndl") === "1" ? true : undefined,
      lifetime: params.get("lifetime") ?? undefined,
      likelihood: params.get("likelihood") ?? undefined,
      impact: params.get("impact") ?? undefined,
      q: params.get("q")?.trim() || undefined,
      sort: (params.get("sort") as RiskFilters["sort"]) ?? "score",
    }),
    [params, system],
  );

  const set = (changes: Record<string, string | string[] | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value) next.set(key, value);
    }
    setParams(next, { replace: true });
    document.getElementById("register")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (summary.isPending) return <PageSkeleton />;
  const data = summary.data;

  return (
    <Page
      title="Quantum Risk"
      subtitle="Every artefact classified by type, lifetime and criticality with Mosca’s inequality, scored for quantum and classical risk, and checked for harvest-now-decrypt-later exposure."
      width="wide"
      actions={
        <>
          <Button variant="gray" icon={<ScrollText />} onClick={() => navigate("/compliance")}>
            Compliance
          </Button>
          <Button variant="filled" icon={<Clock />} onClick={() => navigate("/time-machine")}>
            Time Machine
          </Button>
        </>
      }
    >
      {!data || data.total === 0 ? (
        <Card>
          <EmptyState
            icon={<ShieldAlert />}
            title="Nothing to assess yet"
            message="Quantum risk is calculated from discovered cryptography. Add a source to a system and run a scan."
            action={<Button variant="filled" onClick={() => navigate("/systems")}>Choose a system</Button>}
          />
        </Card>
      ) : (
        <div className="space-y-4">
          <Posture data={data} onBand={(band) => set({ band: [band] })} onHndl={() => set({ hndl: "1" })} />
          <div className="grid gap-4 xl:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <ChartFrame
              title="Risk matrix"
              subtitle="Likelihood against business impact. Select a cell to list its artefacts."
              table={{
                caption: "Artefacts by likelihood and impact",
                rows: data.matrix.cells,
                rowKey: (c) => `${c.likelihood}-${c.impact}`,
                columns: [
                  { key: "l", header: "Likelihood", cell: (c) => data.matrix.likelihood.find((l) => l.key === c.likelihood)?.label },
                  { key: "i", header: "Impact", cell: (c) => data.matrix.impact.find((l) => l.key === c.impact)?.label },
                  { key: "n", header: "Artefacts", numeric: true, cell: (c) => formatInt(c.count) },
                  { key: "s", header: "Highest score", numeric: true, cell: (c) => c.score },
                ],
              }}
            >
              <RiskMatrix
                ariaLabel="Risk matrix of likelihood against impact"
                likelihood={data.matrix.likelihood}
                impact={data.matrix.impact}
                cells={data.matrix.cells}
                selected={filters.likelihood && filters.impact ? { likelihood: filters.likelihood, impact: filters.impact } : null}
                onSelect={(cell) => set({ likelihood: cell?.likelihood, impact: cell?.impact })}
              />
            </ChartFrame>
            <ChartFrame
              title="Mosca plane"
              subtitle={`Each artefact at its lifetime (X) and migration effort (Y). Above the line, X + Y exceeds the planning horizon Z of ${formatYears(data.model.planning_years)}.`}
              legend={BAND_ORDER.filter((b) => b !== "none").map((b) => ({ label: BANDS[b].label, color: BANDS[b].color, kind: "dot" as const }))}
              table={{
                caption: "Artefacts by lifetime and migration effort",
                rows: data.plane,
                rowKey: (p) => `${p.x}-${p.y}`,
                columns: [
                  { key: "x", header: "X (years)", numeric: true, cell: (p) => p.x },
                  { key: "y", header: "Y (years)", numeric: true, cell: (p) => p.y },
                  { key: "e", header: "X + Y − Z", numeric: true, cell: (p) => p.exposure.toFixed(1) },
                  { key: "n", header: "Artefacts", numeric: true, cell: (p) => p.count },
                  { key: "b", header: "Worst band", cell: (p) => BANDS[p.band].label },
                ],
              }}
            >
              <MoscaPlane
                ariaLabel="Mosca plane of artefacts by lifetime and migration effort"
                z={data.model.planning_years}
                points={data.plane.map((p) => ({
                  x: p.x,
                  y: p.y,
                  count: p.count,
                  color: BANDS[p.band].color,
                  exposure: p.exposure,
                  label: Object.entries(p.kinds).map(([k, n]) => `${n} ${n === 1 ? KINDS[k as keyof typeof KINDS].singular.toLowerCase() : KINDS[k as keyof typeof KINDS].label.toLowerCase()}`).join(", "),
                  detail: p.sample,
                }))}
              />
            </ChartFrame>
          </div>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
            <Classification data={data} selected={{ kind: filters.kind?.[0], lifetime: filters.lifetime }} onSelect={(kind, lifetime) => set({ kind: kind ? [kind] : [], lifetime })} />
            <SystemsRisk data={data} onSelect={(id) => navigate(`/systems/${id}`)} />
          </div>
          <Register filters={filters} set={set} params={params} />
        </div>
      )}
    </Page>
  );
}

/* ---------------------------------------------------------------- posture */

function Posture({ data, onBand, onHndl }: { data: RiskSummary; onBand: (band: RiskBand) => void; onHndl: () => void }) {
  const navigate = useNavigate();
  const urgent = data.bands.critical + data.bands.high;
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <Card className="lg:col-span-2">
        <div className="text-subhead font-medium text-label-2">Risk posture</div>
        <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
          <AnimatedNumber value={urgent} format={(n) => formatInt(Math.round(n))} className="text-hero text-label" />
          <span className="text-title-3 text-label-2">of {formatInt(data.total)} artefacts need action this cycle</span>
        </div>
        <p className="mb-4 mt-1 text-subhead text-label-2">
          {formatInt(data.bands.critical)} critical and {formatInt(data.bands.high)} high. Scores combine business impact with the likelihood of attack: classical today, quantum by Mosca’s inequality, and policy deadlines.
        </p>
        <Meter
          unit="artefacts"
          ariaLabel={`Risk bands: ${BAND_ORDER.map((b) => `${BANDS[b].label} ${data.bands[b]}`).join(", ")}`}
          segments={BAND_ORDER.map((b) => ({ key: b, label: BANDS[b].label, value: data.bands[b], color: BANDS[b].color }))}
        />
        <div className="mt-3 flex flex-wrap gap-1.5">
          {BAND_ORDER.filter((b) => b !== "none" && data.bands[b] > 0).map((b) => (
            <button key={b} type="button" onClick={() => onBand(b)} className="hover-light rounded-full bg-fill-2 px-2.5 py-1 text-footnote font-medium text-label-2 transition-colors hover:text-label">
              Show {BANDS[b].label.toLowerCase()} <ArrowRight className="inline size-3" />
            </button>
          ))}
        </div>
      </Card>
      <button type="button" onClick={onHndl} className="glass hover-light hover-lift flex flex-col rounded-[18px] p-5 text-left">
        <div className="flex items-center gap-2 text-subhead font-medium text-label-2">
          <Radio className="size-4 text-label-3" /> Harvest now, decrypt later
        </div>
        <div className="mt-auto pt-4">
          <AnimatedNumber value={data.hndl.exposed} format={(n) => formatInt(Math.round(n))} className="block text-title-1 text-label" />
          <p className="mt-1 text-footnote text-label-3">
            {data.hndl.exposed
              ? `Key exchanges on ${data.hndl.systems} system${data.hndl.systems === 1 ? "" : "s"} protect data that outlives the horizon. Traffic recorded today can be decrypted later${data.hndl.internet ? `; ${data.hndl.internet} are internet-facing` : ""}.`
              : "No recorded traffic outlives the planning horizon."}
          </p>
        </div>
      </button>
      <button type="button" onClick={() => navigate("/horizon")} className="glass hover-light hover-lift flex flex-col rounded-[18px] p-5 text-left">
        <div className="flex items-center gap-2 text-subhead font-medium text-label-2">
          <Orbit className="size-4 text-label-3" /> Planning horizon (Z)
        </div>
        <div className="mt-auto pt-4">
          <div className="text-title-1 text-label">{data.model.planning_label}</div>
          <p className="mt-1 text-footnote text-label-3">
            {formatYears(data.model.planning_years)} away: the point with a {formatPercent(data.model.tolerance, 0)} chance a cryptographically relevant quantum computer exists ({data.model.scenario} scenario).
          </p>
        </div>
      </button>
    </div>
  );
}

/* --------------------------------------------------------- classification */

function Classification({ data, selected, onSelect }: { data: RiskSummary; selected: { kind?: string; lifetime?: string }; onSelect: (kind?: string, lifetime?: string) => void }) {
  const lifetimes = data.classification.lifetimes;
  const rows = [...data.classification.rows].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
  const band = (score: number): RiskBand => (score >= 60 ? "critical" : score >= 35 ? "high" : score >= 15 ? "medium" : score >= 1 ? "low" : "none");
  return (
    <Card>
      <CardHeader
        title="Classification"
        subtitle="Type against lifetime. Each cell shows how many artefacts it holds, tinted by the worst risk among them."
      />
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-[3px] text-left">
          <thead>
            <tr>
              <th className="text-caption font-medium text-label-3">Type</th>
              {lifetimes.map((l) => (
                <th key={l.key} className="px-1 text-center text-caption font-medium text-label-3">
                  {l.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.kind}>
                <td className="whitespace-nowrap pr-2">
                  <span className="flex items-center gap-2 text-subhead text-label">
                    <KindGlyph kind={row.kind} size={24} /> {KINDS[row.kind].label}
                  </span>
                </td>
                {lifetimes.map((l) => {
                  const cell = row.cells[l.key];
                  const active = selected.kind === row.kind && selected.lifetime === l.key;
                  return (
                    <td key={l.key} className="p-0">
                      <button
                        type="button"
                        disabled={!cell}
                        onClick={() => (active ? onSelect(undefined, undefined) : onSelect(row.kind, l.key))}
                        className={cn(
                          "hover-light grid h-10 w-full min-w-[56px] place-items-center rounded-[8px] text-subhead font-semibold tabular transition-transform duration-200 disabled:cursor-default",
                          cell ? "text-label hover:scale-[1.04]" : "text-label-4",
                          active && "shadow-[0_0_0_2px_var(--label)]",
                        )}
                        style={{ background: cell ? `color-mix(in srgb, ${BANDS[band(cell.score)].color} 30%, transparent)` : "var(--fill-2)" }}
                      >
                        {cell ? formatInt(cell.count) : "·"}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {(Object.keys(ROLES) as (keyof typeof ROLES)[]).map((role) => (
          <div key={role} className="rounded-[12px] bg-fill-2 px-3 py-2" title={ROLES[role].summary}>
            <div className="text-caption text-label-3">{ROLES[role].label}</div>
            <div className="text-headline tabular text-label">{formatInt(data.classification.roles[role] ?? 0)}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ---------------------------------------------------------------- systems */

function SystemsRisk({ data, onSelect }: { data: RiskSummary; onSelect: (id: string) => void }) {
  const rows = data.systems.filter((s) => s.artefacts > 0);
  const unscanned = data.systems.length - rows.length;
  return (
    <Card padded={false}>
      <div className="px-5 pt-5">
        <CardHeader title="Systems" subtitle="Worst risk per system, and migration time (Y) estimated from what was discovered." />
      </div>
      <ul className="pb-2">
        {rows.map((s) => {
          const total = BAND_ORDER.reduce((n, b) => n + (s.bands[b] ?? 0), 0) || 1;
          return (
            <li key={s.id} className="px-2">
              <button type="button" onClick={() => onSelect(s.id)} className="hover-light flex w-full items-center gap-3 rounded-[12px] px-3 py-2.5 text-left transition-colors hover:bg-fill-2">
                <Chip className="shrink-0">{s.code}</Chip>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-callout font-medium text-label">{s.name}</span>
                    <RiskBadge band={s.band} />
                  </span>
                  <span className="mt-1.5 flex h-1.5 gap-[2px] overflow-hidden rounded-full" aria-hidden>
                    {BAND_ORDER.filter((b) => (s.bands[b] ?? 0) > 0).map((b) => (
                      <span key={b} style={{ flexGrow: s.bands[b], flexBasis: 0, background: BANDS[b].color }} />
                    ))}
                  </span>
                  <span className="mt-1 flex flex-wrap gap-x-3 text-caption text-label-3">
                    <span>{formatInt(total)} artefacts</span>
                    {s.hndl_exposed > 0 && <span className="text-label-2">{s.hndl_exposed} harvestable</span>}
                    {s.estimated_y !== null && (
                      <span>
                        Y {formatYears(s.estimated_y)} from discovery · {formatYears(s.register_y)} registered
                      </span>
                    )}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {unscanned > 0 && <p className="px-5 pb-4 text-footnote text-label-3">{unscanned} registered system{unscanned === 1 ? " has" : "s have"} not been scanned yet.</p>}
    </Card>
  );
}

/* --------------------------------------------------------------- register */

function Register({ filters, set, params }: { filters: RiskFilters; set: (c: Record<string, string | string[] | undefined>) => void; params: URLSearchParams }) {
  const navigate = useNavigate();
  const systems = useSystems({ sort: "name" });
  const register = useRiskRegister(filters);
  const rows = useMemo(() => register.data?.pages.flatMap((p) => p.items) ?? [], [register.data]);
  const total = register.data?.pages[0]?.total ?? 0;
  const sentinel = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = register;

  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage) return;
    const observer = new IntersectionObserver(([entry]) => entry.isIntersecting && !isFetchingNextPage && fetchNextPage(), { rootMargin: "400px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const chips: { label: string; clear: Record<string, undefined> }[] = [];
  if (filters.likelihood && filters.impact) chips.push({ label: `Matrix: ${filters.likelihood} · ${filters.impact}`, clear: { likelihood: undefined, impact: undefined } });
  if (filters.lifetime) chips.push({ label: `Lifetime: ${filters.lifetime}`, clear: { lifetime: undefined } });
  if (filters.hndl) chips.push({ label: "Harvestable now", clear: { hndl: undefined } });

  const columns: Column<RiskRow>[] = [
    {
      key: "artefact",
      header: "Artefact",
      cell: (r) => (
        <div className="flex min-w-0 items-center gap-3">
          <KindGlyph kind={r.kind} size={30} />
          <div className="min-w-0">
            <div className="truncate font-medium text-label">{r.name}</div>
            <div className="max-w-[380px] truncate text-footnote text-label-3">{r.driver ?? r.roles.map((x) => ROLES[x].label).join(" · ")}</div>
          </div>
        </div>
      ),
    },
    { key: "system", header: "System", hideBelow: "md", cell: (r) => <Chip>{r.system.code}</Chip> },
    {
      key: "mosca",
      header: "X + Y vs Z",
      hideBelow: "lg",
      cell: (r) => <MoscaGlyph x={r.mosca.x} y={r.mosca.y} z={r.mosca.z} />,
    },
    {
      key: "p",
      header: "CRQC first",
      numeric: true,
      hideBelow: "lg",
      cell: (r) => (r.classification.mosca === "not-affected" ? <span className="text-label-4">—</span> : formatPercent(r.mosca.probability)),
    },
    {
      key: "hndl",
      header: "HNDL",
      hideBelow: "sm",
      cell: (r) => (r.hndl.exposed ? <span className="text-footnote font-medium text-label">Harvestable</span> : <span className="text-footnote text-label-4">—</span>),
    },
    { key: "score", header: "Risk", cell: (r) => <RiskBadge band={r.band} score={r.score} /> },
  ];

  return (
    <div id="register" className="scroll-mt-16 space-y-3 pt-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-2 text-title-3 text-label">Risk register</h2>
        <TextField
          aria-label="Search artefacts"
          placeholder="Search by name"
          leading={<Search />}
          value={params.get("q") ?? ""}
          onChange={(e) => set({ q: e.target.value })}
          containerClassName="w-[220px] max-sm:w-full"
        />
        <FacetMenu label="Band" selected={filters.band ?? []} onChange={(v) => set({ band: v })} options={BAND_ORDER.map((b) => ({ value: b, label: BANDS[b].label }))} />
        <FacetMenu label="Type" selected={filters.kind ?? []} onChange={(v) => set({ kind: v })} options={KIND_ORDER.map((k) => ({ value: k, label: KINDS[k].label }))} />
        <FacetMenu
          label={filters.role ? ROLES[filters.role as keyof typeof ROLES].label : "Role"}
          selected={filters.role ? [filters.role] : []}
          onChange={(v) => set({ role: v.filter((x) => x !== filters.role)[0] })}
          options={(Object.keys(ROLES) as (keyof typeof ROLES)[]).map((r) => ({ value: r, label: ROLES[r].label }))}
        />
        {systems.data && systems.data.items.length > 1 && (
          <FacetMenu
            label={filters.system ? (systems.data.items.find((s) => s.id === filters.system)?.code ?? "System") : "System"}
            selected={filters.system ? [filters.system] : []}
            onChange={(v) => set({ system: v.filter((id) => id !== filters.system)[0] })}
            options={systems.data.items.map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` }))}
          />
        )}
        {chips.map((c) => (
          <button key={c.label} type="button" onClick={() => set(c.clear)} className="hover-light inline-flex h-8 items-center gap-1.5 rounded-full bg-accent-tint px-3 text-subhead font-medium text-accent-ink">
            {c.label} <X className="size-3.5" />
          </button>
        ))}
        <div className="ml-auto">
          <Menu>
            <MenuTrigger asChild>
              <Button variant="gray" icon={<ArrowDownWideNarrow />}>
                {SORTS.find((s) => s.value === filters.sort)?.label}
              </Button>
            </MenuTrigger>
            <MenuContent>
              <MenuLabel>Sort by</MenuLabel>
              <MenuRadioGroup value={filters.sort ?? "score"} onChange={(v) => set({ sort: v === "score" ? undefined : v })} options={SORTS} />
            </MenuContent>
          </Menu>
        </div>
      </div>
      <Card padded={false} className={cn("overflow-hidden transition-opacity duration-200", register.isPlaceholderData && "opacity-60")}>
        {register.isPending ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <Table
            caption="Risk register"
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
            rowLabel={(r) => `Open ${r.name}`}
            onRowClick={(r) => navigate(`/inventory/${r.id}`)}
            empty={<EmptyState compact icon={<Search />} title="No matching artefacts" message="Clear a filter or pick another cell." />}
          />
        )}
        <div ref={sentinel} />
      </Card>
      <div className="flex items-center gap-2 px-1 text-footnote text-label-3">
        {isFetchingNextPage && <ActivityIndicator size={12} />}
        {total > 0 && `${formatInt(rows.length)} of ${formatInt(total)} artefacts`}
      </div>
    </div>
  );
}

/** Y then X against the horizon tick, like the systems register's glyph. */
export function MoscaGlyph({ x, y, z, width = 96 }: { x: number; y: number; z: number; width?: number }) {
  const max = Math.max(z * 1.6, x + y, 1);
  const s = (v: number) => (Math.min(v, max) / max) * width;
  return (
    <span className="inline-flex" title={`Y ${formatYears(y)} + X ${formatYears(x)} against Z ${formatYears(z)}`}>
      <svg width={width + 2} height={14} aria-hidden className="overflow-visible">
        <rect x={s(z)} y={0} width={Math.max(0, width - s(z))} height={14} rx={2} style={{ fill: "var(--chart-zone)" }} />
        {y > 0 && <rect x={0} y={4} width={Math.max(1, s(y) - 1)} height={6} style={{ fill: "var(--series-1)" }} />}
        {x > 0 && <rect x={s(y) + 1} y={4} width={Math.max(1, s(x) - 1)} height={6} rx={2} style={{ fill: "var(--series-2)" }} />}
        <line x1={s(z)} x2={s(z)} y1={0} y2={14} strokeWidth={1.25} style={{ stroke: "var(--label)" }} />
      </svg>
    </span>
  );
}
