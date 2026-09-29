import { ArrowDownWideNarrow, Atom, History, OctagonX, Search, Server, ShieldAlert, X } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { FacetMenu } from "@/design/components/FacetMenu";
import { TextField } from "@/design/components/Field";
import { Menu, MenuContent, MenuLabel, MenuRadioGroup, MenuTrigger } from "@/design/components/Menu";
import { Segmented } from "@/design/components/Segmented";
import { Banner, Card, CardHeader, Chip, EmptyState, Skeleton } from "@/design/components/Surface";
import { Table, type Column } from "@/design/components/Table";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { useCan } from "@/lib/access";
import { formatInt, formatPercent, formatRelative } from "@/lib/format";
import { useArtefacts, useInventorySummary, useScan, useSystems, type ArtefactFilters } from "@/lib/queries";
import type { Artefact, ArtefactKind, InventorySummary, QuantumStatus } from "@/lib/types";
import { BarList } from "@/viz/charts/BarList";
import { Meter } from "@/viz/charts/Meter";
import { Ring } from "@/viz/charts/Ring";
import { StackedBars } from "@/viz/charts/StackedBars";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { ChartFrame, LegendKey } from "@/viz/core/ChartFrame";
import { Page, PageSkeleton } from "../shell/Page";
import { describeArtefact } from "./describe";
import { ASSESSED, CLASSICAL, CLASSICAL_ORDER, ClassicalBadge, KIND_ORDER, KindGlyph, KINDS, QUANTUM, QUANTUM_ORDER, QuantumBadge } from "./vocab";

const SORTS: { value: NonNullable<ArtefactFilters["sort"]>; label: string }[] = [
  { value: "risk", label: "Highest risk" },
  { value: "name", label: "Name" },
  { value: "recent", label: "Recently seen" },
  { value: "evidence", label: "Most evidence" },
];

export default function InventoryPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const system = params.get("system") ?? undefined;
  const summary = useInventorySummary(system);
  const systems = useSystems({ sort: "name" });

  const filters: ArtefactFilters = useMemo(
    () => ({
      system,
      kind: params.getAll("kind"),
      quantum: params.getAll("quantum"),
      classical: params.getAll("classical"),
      status: (params.get("status") as ArtefactFilters["status"]) ?? "active",
      family: params.get("family") ?? undefined,
      q: params.get("q")?.trim() || undefined,
      scan: params.get("scan") ?? undefined,
      sort: (params.get("sort") as ArtefactFilters["sort"]) ?? "risk",
    }),
    [params, system],
  );

  const set = (key: string, value: string | string[] | undefined) => {
    const next = new URLSearchParams(params);
    next.delete(key);
    if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
    else if (value) next.set(key, value);
    setParams(next, { replace: true });
  };
  const toggleKind = (kind: ArtefactKind) => set("kind", filters.kind?.includes(kind) ? [] : [kind]);

  if (summary.isPending) return <PageSkeleton />;
  const data = summary.data;
  const nothingYet = data && data.total === 0 && !system;

  return (
    <Page
      title="Inventory"
      subtitle="Every cryptographic artefact FALCON has discovered, de-duplicated per system and assessed for quantum and classical risk."
      width="wide"
      actions={
        <Button variant="gray" icon={<History />} onClick={() => navigate("/scans")}>
          Scan history
        </Button>
      }
    >
      {nothingYet ? (
        <Card>
          <EmptyState
            icon={<Search />}
            title="No cryptography discovered yet"
            message="Add a source to a system (a folder, repository, archive, container image or TLS endpoint) and FALCON will build the inventory from what it finds."
            action={<Button variant="filled" icon={<Server />} onClick={() => navigate("/systems")}>Choose a system</Button>}
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {data && <Posture data={data} />}
          {data && <KindTiles data={data} selected={filters.kind ?? []} onToggle={toggleKind} />}
          {data && data.total > 0 && (
            <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
              <ClassChart data={data} selected={filters.kind?.length === 1 ? filters.kind[0] : null} onSelect={(kind, quantum) => {
                const next = new URLSearchParams(params);
                next.delete("kind");
                next.delete("quantum");
                next.append("kind", kind);
                if (quantum) next.append("quantum", quantum);
                setParams(next, { replace: true });
              }} />
              <Card>
                <CardHeader title="Algorithm families" subtitle="Most widespread across the inventory." />
                <BarList
                  ariaLabel="Algorithm families by number of artefacts"
                  items={data.top_families.map((f) => ({ key: f.family, label: f.family, value: f.count }))}
                  onSelect={(family) => set("family", filters.family === family ? undefined : family)}
                />
              </Card>
            </div>
          )}

          <ScanScope scanId={filters.scan} onClear={() => set("scan", undefined)} />

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <SearchBox value={params.get("q") ?? ""} onChange={(v) => set("q", v)} />
            <Segmented
              label="Artefact status"
              value={filters.status ?? "active"}
              onChange={(v) => set("status", v === "active" ? undefined : v)}
              options={[
                { value: "active", label: "In use" },
                { value: "resolved", label: "Resolved" },
                { value: "all", label: "All" },
              ]}
            />
            <FacetMenu label="Class" selected={filters.kind ?? []} onChange={(v) => set("kind", v)} options={KIND_ORDER.map((k) => ({ value: k, label: KINDS[k].label }))} />
            <FacetMenu label="Quantum" selected={filters.quantum ?? []} onChange={(v) => set("quantum", v)} options={QUANTUM_ORDER.map((q) => ({ value: q, label: QUANTUM[q].label }))} />
            <FacetMenu label="Classical" selected={filters.classical ?? []} onChange={(v) => set("classical", v)} options={CLASSICAL_ORDER.filter((c) => c !== "unknown").map((c) => ({ value: c, label: CLASSICAL[c].label }))} />
            {systems.data && systems.data.items.length > 1 && (
              <FacetMenu
                label={system ? (systems.data.items.find((s) => s.id === system)?.code ?? "System") : "System"}
                selected={system ? [system] : []}
                onChange={(v) => set("system", v.filter((id) => id !== system)[0])}
                options={systems.data.items.map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` }))}
              />
            )}
            {filters.family && (
              <button type="button" onClick={() => set("family", undefined)} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-accent-tint px-3 text-subhead font-medium text-accent-ink focus-visible:focus-ring">
                {filters.family} <X className="size-3.5" />
              </button>
            )}
            <div className="ml-auto">
              <Menu>
                <MenuTrigger asChild>
                  <Button variant="gray" icon={<ArrowDownWideNarrow />}>
                    {SORTS.find((s) => s.value === filters.sort)?.label}
                  </Button>
                </MenuTrigger>
                <MenuContent>
                  <MenuLabel>Sort by</MenuLabel>
                  <MenuRadioGroup value={filters.sort ?? "risk"} onChange={(v) => set("sort", v === "risk" ? undefined : v)} options={SORTS} />
                </MenuContent>
              </Menu>
            </div>
          </div>

          <ArtefactTable filters={filters} showSystem={!system} />
        </div>
      )}
    </Page>
  );
}

function SearchBox({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <TextField
      aria-label="Search artefacts"
      placeholder="Search by name"
      leading={<Search />}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      containerClassName="w-[240px] max-sm:w-full"
      trailing={
        value && (
          <button type="button" aria-label="Clear search" onClick={() => onChange("")} className="grid size-6 place-items-center rounded-full text-label-3 hover:text-label-2">
            <X className="size-3.5" />
          </button>
        )
      }
    />
  );
}

/* --------------------------------------------------------------- posture */

function Posture({ data }: { data: InventorySummary }) {
  const assessed = QUANTUM_ORDER.map((q) => ({
    key: q,
    label: QUANTUM[q].label,
    color: QUANTUM[q].color,
    value: ASSESSED.reduce((n, k) => n + (data.matrix[k]?.[q] ?? 0), 0),
  }));
  const assessedTotal = assessed.reduce((n, s) => n + s.value, 0);
  const vulnerable = assessed.find((s) => s.key === "vulnerable")!.value;
  const pqc = (data.by_quantum.pqc ?? 0) + (data.by_quantum.hybrid ?? 0);
  const publicKey = pqc + vulnerable;
  const brokenNow = (data.by_classical.broken ?? 0) + (data.by_classical.weak ?? 0);

  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <Card className="lg:col-span-2">
        <div className="text-subhead font-medium text-label-2">Quantum posture</div>
        <div className="mt-2 flex flex-wrap items-baseline gap-x-2">
          <AnimatedNumber value={vulnerable} format={(n) => formatInt(Math.round(n))} className="text-hero text-label" />
          <span className="text-title-3 text-label-2">of {formatInt(assessedTotal)} assessed artefacts are quantum-vulnerable</span>
        </div>
        <p className="mb-4 mt-1 text-subhead text-label-2">
          {data.systems} system{data.systems === 1 ? "" : "s"} · {formatInt(data.total)} artefacts in use
          {data.libraries.total > 0 && `, including ${formatInt(data.libraries.total)} libraries`}
          {data.by_kind.hardware > 0 && ` and ${formatInt(data.by_kind.hardware)} hardware modules`}.
        </p>
        <Meter segments={assessed} unit="artefacts" ariaLabel={`Quantum status of assessed artefacts: ${assessed.map((s) => `${s.label} ${s.value}`).join(", ")}`} />
      </Card>
      <Card className="flex flex-col">
        <div className="flex items-center gap-2 text-subhead font-medium text-label-2">
          <Atom className="size-4 text-label-3" /> Post-quantum in use
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 pt-4">
          <AnimatedNumber value={pqc} format={(n) => formatInt(Math.round(n))} className="block text-title-1 text-label" />
          {publicKey > 0 && (
            <Ring value={pqc / publicKey} size={64} thickness={7} color="var(--status-good)" ariaLabel={`${pqc} of ${publicKey} public-key artefacts are post-quantum or hybrid`}>
              <span className="text-caption font-semibold tabular text-label">{formatPercent(pqc / publicKey, 0)}</span>
            </Ring>
          )}
        </div>
        <p className="mt-2 text-footnote text-label-3">
          {publicKey
            ? `${formatInt(data.by_quantum.pqc ?? 0)} post-quantum and ${formatInt(data.by_quantum.hybrid ?? 0)} hybrid, against ${formatInt(vulnerable)} classical public-key artefacts.`
            : "No public-key cryptography found yet."}
        </p>
      </Card>
      <Card className="flex flex-col">
        <div className="flex items-center gap-2 text-subhead font-medium text-label-2">
          <OctagonX className="size-4 text-label-3" /> Weak or broken today
        </div>
        <div className="mt-auto flex items-end justify-between gap-3 pt-4">
          <AnimatedNumber value={brokenNow} format={(n) => formatInt(Math.round(n))} className="block text-title-1 text-label" />
          {data.certificates.expired > 0 && (
            <span className="mb-1 shrink-0 rounded-full bg-[var(--status-critical-tint)] px-2 py-0.5 text-caption font-medium text-label">
              {formatInt(data.certificates.expired)} expired cert{data.certificates.expired === 1 ? "" : "s"}
            </span>
          )}
        </div>
        <p className="mt-1 text-footnote text-label-3">{brokenNow ? "Attackable without a quantum computer." : "Nothing below today’s minimums."}</p>
        <ul className="mt-3 space-y-1">
          {(["broken", "weak", "legacy"] as const).map((c) => (
            <li key={c} className="flex items-center gap-2 text-footnote">
              <LegendKey color={CLASSICAL[c].color} kind="rect" />
              <span className="text-label-2">{CLASSICAL[c].label}</span>
              <span className="ml-auto font-medium tabular text-label">{formatInt(data.by_classical[c] ?? 0)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function KindTiles({ data, selected, onToggle }: { data: InventorySummary; selected: string[]; onToggle: (kind: ArtefactKind) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
      {KIND_ORDER.map((kind) => {
        const count = data.by_kind[kind] ?? 0;
        const row = data.matrix[kind] ?? {};
        const active = selected.includes(kind);
        return (
          <button
            key={kind}
            type="button"
            aria-pressed={active}
            onClick={() => onToggle(kind)}
            className={cn(
              "glass hover-light hover-lift flex min-h-[124px] flex-col rounded-[16px] p-4 text-left focus-visible:focus-ring",
              active && "outline outline-2 -outline-offset-2 outline-[var(--accent)]",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <KindGlyph kind={kind} size={30} className={cn(active && "bg-accent-tint text-accent")} />
              <AnimatedNumber value={count} format={(n) => formatInt(Math.round(n))} className={cn("text-title-2 tabular", count ? "text-label" : "text-label-4")} />
            </div>
            <div className="mt-auto pt-3">
              <div className="truncate text-subhead font-medium text-label">{KINDS[kind].label}</div>
              <TileFootnote kind={kind} data={data} row={row} count={count} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

function TileFootnote({ kind, data, row, count }: { kind: ArtefactKind; data: InventorySummary; row: Partial<Record<QuantumStatus, number>>; count: number }) {
  if (!count) return <div className="truncate text-caption text-label-4">None found</div>;
  if (kind === "library") {
    const parts = [data.libraries.pqc_capable && `${data.libraries.pqc_capable} PQC-capable`, data.libraries.end_of_life && `${data.libraries.end_of_life} end-of-life`, data.libraries.abandoned && `${data.libraries.abandoned} abandoned`].filter(Boolean);
    return <div className="line-clamp-2 text-caption text-label-3">{parts.join(" · ") || "No PQC support found"}</div>;
  }
  if (kind === "hardware") return <div className="line-clamp-2 text-caption text-label-3">HSMs, TPMs and PKCS#11 modules</div>;
  const segments = QUANTUM_ORDER.filter((q) => (row[q] ?? 0) > 0);
  return (
    <div className="mt-1.5 flex h-1.5 gap-[2px] overflow-hidden rounded-full" role="img" aria-label={segments.map((q) => `${QUANTUM[q].label} ${row[q]}`).join(", ")}>
      {segments.map((q) => (
        <span key={q} className="h-full min-w-[3px]" style={{ flexGrow: row[q], flexBasis: 0, background: QUANTUM[q].color }} />
      ))}
    </div>
  );
}

function ClassChart({ data, selected, onSelect }: { data: InventorySummary; selected: string | null; onSelect: (kind: string, quantum?: string) => void }) {
  const rows = ASSESSED.map((k) => ({ key: k, label: KINDS[k].label, values: data.matrix[k] ?? {} }));
  const present = QUANTUM_ORDER.filter((q) => rows.some((r) => (r.values[q] ?? 0) > 0));
  const series = present.map((q) => ({ key: q, label: QUANTUM[q].label, color: QUANTUM[q].color }));
  return (
    <ChartFrame
      title="Quantum status by class"
      subtitle="Select a bar to filter the inventory below."
      legend={series.map((s) => ({ label: s.label, color: s.color }))}
      table={{
        caption: "Artefacts by class and quantum status",
        rows,
        rowKey: (r) => r.key,
        columns: [
          { key: "class", header: "Class", cell: (r) => r.label },
          ...QUANTUM_ORDER.map((q) => ({ key: q, header: QUANTUM[q].short, numeric: true, cell: (r: (typeof rows)[number]) => formatInt(r.values[q] ?? 0) })),
        ],
      }}
    >
      <StackedBars rows={rows} series={series} ariaLabel="Artefacts by class, stacked by quantum status" onSelect={onSelect} selected={selected} />
    </ChartFrame>
  );
}

function ScanScope({ scanId, onClear }: { scanId?: string; onClear: () => void }) {
  const scan = useScan(scanId ?? "");
  if (!scanId) return null;
  return (
    <Banner
      tone="info"
      title={scan.data ? `Artefacts seen by the scan of “${scan.data.source?.name ?? "a removed source"}”` : "Artefacts seen by one scan"}
      action={
        <Button variant="plain" size="sm" onClick={onClear}>
          Show everything
        </Button>
      }
    >
      {scan.data?.finished_at ? `Completed ${formatRelative(scan.data.finished_at)} in ${scan.data.system?.name ?? "a system"}.` : "Including artefacts since resolved."}
    </Banner>
  );
}

/* ----------------------------------------------------------------- table */

function ArtefactTable({ filters, showSystem }: { filters: ArtefactFilters; showSystem: boolean }) {
  const navigate = useNavigate();
  const canScan = useCan("sources.manage");
  const effective = filters.scan && filters.status === "active" ? { ...filters, status: "all" as const } : filters;
  const artefacts = useArtefacts(effective);
  const rows = useMemo(() => artefacts.data?.pages.flatMap((p) => p.items) ?? [], [artefacts.data]);
  const total = artefacts.data?.pages[0]?.total ?? 0;
  const sentinel = useRef<HTMLDivElement>(null);
  const { hasNextPage, isFetchingNextPage, fetchNextPage } = artefacts;

  useEffect(() => {
    const node = sentinel.current;
    if (!node || !hasNextPage) return;
    const observer = new IntersectionObserver(([entry]) => entry.isIntersecting && !isFetchingNextPage && fetchNextPage(), { rootMargin: "400px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const columns: Column<Artefact>[] = [
    {
      key: "name",
      header: "Artefact",
      cell: (a) => (
        <div className="flex min-w-0 items-center gap-3">
          <KindGlyph kind={a.kind} size={30} />
          <div className="min-w-0">
            <div className={cn("truncate font-medium", a.status === "resolved" ? "text-label-3 line-through decoration-label-4" : "text-label")}>{a.name}</div>
            <div className="truncate text-footnote text-label-3">{describeArtefact(a) || KINDS[a.kind].singular}</div>
          </div>
        </div>
      ),
    },
    ...(showSystem ? [{ key: "system", header: "System", hideBelow: "md" as const, cell: (a: Artefact) => (a.system ? <Chip>{a.system.code}</Chip> : null) }] : []),
    {
      key: "quantum",
      header: "Quantum",
      cell: (a) =>
        a.kind === "library" || a.kind === "hardware" ? (
          <span className="text-footnote text-label-3">{a.kind === "library" ? ((a.properties.pqc as { capable?: boolean } | undefined)?.capable ? "PQC-capable" : "—") : "—"}</span>
        ) : (
          <QuantumBadge value={a.quantum} short />
        ),
    },
    { key: "classical", header: "Classical", hideBelow: "lg", cell: (a) => (a.classical ? <ClassicalBadge value={a.classical} /> : <span className="text-footnote text-label-4">—</span>) },
    { key: "evidence", header: "Evidence", numeric: true, hideBelow: "sm", cell: (a) => formatInt(a.occurrences) },
    { key: "seen", header: "Last seen", hideBelow: "lg", cell: (a) => <span className="text-footnote text-label-3">{formatRelative(a.last_seen_at)}</span> },
  ];

  return (
    <>
      <Card padded={false} className={cn("overflow-hidden transition-opacity duration-200", artefacts.isPlaceholderData && "opacity-60")}>
        {artefacts.isPending ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <Table
            caption="Cryptographic artefacts"
            columns={columns}
            rows={rows}
            rowKey={(a) => a.id}
            rowLabel={(a) => `Open ${a.name}`}
            onRowClick={(a) => navigate(`/inventory/${a.id}`)}
            empty={
              <EmptyState
                compact
                icon={<ShieldAlert />}
                title="No matching artefacts"
                message={canScan ? "Try a different search or filter, or scan more sources." : "Try a different search or filter."}
              />
            }
          />
        )}
        <div ref={sentinel} />
      </Card>
      <div className="mt-3 flex items-center gap-2 px-1 text-footnote text-label-3">
        {isFetchingNextPage && <ActivityIndicator size={12} />}
        {artefacts.data && total > 0 && `${formatInt(rows.length)} of ${formatInt(total)} artefacts`}
      </div>
    </>
  );
}
