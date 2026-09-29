import { ArrowLeft, ArrowRight, Check, CircleAlert, RotateCw, Square } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Banner, Card, CardHeader, Chip, EmptyState, GroupedList, GroupedRow } from "@/design/components/Surface";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { spring } from "@/design/motion";
import { useCan } from "@/lib/access";
import { ApiError } from "@/lib/api";
import { formatDateTime, formatInt, formatRelative } from "@/lib/format";
import { useArtefacts, useCancelScan, useScan, useStartScan } from "@/lib/queries";
import type { CoverageLeaf, InventorySummary, ScanDetail, ScanStage } from "@/lib/types";
import { BarList } from "@/viz/charts/BarList";
import { StackedBars } from "@/viz/charts/StackedBars";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { intensityColor, PENDING_FILL, Treemap, type TreemapLeaf } from "@/viz/charts/Treemap";
import { ChartFrame, LegendKey } from "@/viz/core/ChartFrame";
import { ScanDiffCard } from "../migration/ScanDiffCard";
import { Page, PageSkeleton } from "../shell/Page";
import { throughput, useScanStream, type Discovered } from "./useScanStream";
import { formatBytes, formatDuration, KIND_ORDER, KindGlyph, KINDS, QUANTUM, QUANTUM_ORDER, QuantumBadge, ScanStatusBadge, SOURCE_KINDS } from "./vocab";

const STAGES: { key: ScanStage; label: string; idle: string }[] = [
  { key: "acquire", label: "Acquire", idle: "Fetch or unpack the source" },
  { key: "enumerate", label: "Enumerate", idle: "Classify every file" },
  { key: "analyse", label: "Analyse", idle: "Run the detectors" },
  { key: "done", label: "Consolidate", idle: "Build the inventory" },
];

export default function ScanPage() {
  const { scanId = "" } = useParams();
  const navigate = useNavigate();
  const detail = useScan(scanId);
  const stream = useScanStream(scanId);

  // The stream's live copy leads while the scan runs; the query's copy carries the final summary.
  const scan: ScanDetail | undefined = useMemo(() => {
    if (!detail.data) return stream.scan ?? undefined;
    if (!stream.scan) return detail.data;
    const liveIsNewer = stream.scan.status === "running" || stream.scan.status === "queued" || detail.data.status === "running" || detail.data.status === "queued";
    return liveIsNewer ? { ...detail.data, ...stream.scan, summary: detail.data.summary } : detail.data;
  }, [detail.data, stream.scan]);

  if (detail.isError && !scan) {
    const missing = detail.error instanceof ApiError && detail.error.status === 404;
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <EmptyState
          icon={<CircleAlert />}
          title={missing ? "This scan no longer exists" : "The scan couldn’t be loaded"}
          message={missing ? "Its source may have been removed." : detail.error.message}
          action={<Button variant="tinted" onClick={() => navigate("/scans")}>All scans</Button>}
        />
      </div>
    );
  }
  if (!scan) return <PageSkeleton />;

  const coverage = Object.keys(stream.coverage).length ? stream.coverage : scan.coverage;
  return <ScanView scan={scan} coverage={coverage} feed={stream.feed} current={stream.current} samples={stream.samples} connection={stream.connection} />;
}

function ScanView({
  scan,
  coverage,
  feed,
  current,
  samples,
  connection,
}: {
  scan: ScanDetail;
  coverage: Record<string, CoverageLeaf>;
  feed: Discovered[];
  current: string | null;
  samples: ReturnType<typeof useScanStream>["samples"];
  connection: ReturnType<typeof useScanStream>["connection"];
}) {
  const navigate = useNavigate();
  const canScan = useCan("scans.run");
  const cancel = useCancelScan();
  const again = useStartScan();
  const active = scan.status === "queued" || scan.status === "running";
  const kind = scan.source?.kind ?? "directory";
  const sourceMeta = SOURCE_KINDS[kind];
  const now = useNow(active ? 1000 : null);
  const elapsed = scan.started_at ? ((scan.finished_at ? new Date(scan.finished_at).getTime() : now) - new Date(scan.started_at).getTime()) / 1000 : 0;

  const rescan = async () => {
    if (!scan.source) return;
    try {
      const next = await again.mutateAsync(scan.source.id);
      navigate(`/scans/${next.id}`);
    } catch (error) {
      toast.error((error as Error).message);
    }
  };

  return (
    <Page
      eyebrow={
        <span className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => navigate("/scans")} className="inline-flex items-center gap-1 rounded text-accent-ink hover:underline">
            <ArrowLeft className="size-3.5" /> Scans
          </button>
          {scan.system && (
            <>
              <span className="text-label-4">/</span>
              <button type="button" onClick={() => navigate(`/systems/${scan.system!.id}`)} className="rounded hover:text-label">
                <Chip>{scan.system.code}</Chip> <span className="ml-1">{scan.system.name}</span>
              </button>
            </>
          )}
        </span>
      }
      title={scan.source?.name ?? "Removed source"}
      subtitle={
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <ScanStatusBadge status={scan.status} />
          <span>
            {sourceMeta.label} · requested by {scan.requested_by ?? "FALCON"} {formatRelative(scan.queued_at)}
          </span>
        </span>
      }
      actions={
        canScan &&
        (active ? (
          <Button
            variant="destructive-tinted"
            icon={<Square className="fill-current" />}
            loading={cancel.isPending}
            onClick={() => cancel.mutate(scan.id, { onError: (e) => toast.error(e.message) })}
          >
            Cancel scan
          </Button>
        ) : (
          <>
            {scan.source && (
              <Button variant="gray" icon={<RotateCw />} loading={again.isPending} onClick={rescan}>
                Scan again
              </Button>
            )}
            {scan.status === "succeeded" && (
              <Button variant="filled" trailingIcon={<ArrowRight />} onClick={() => navigate(`/inventory?scan=${scan.id}`)}>
                View {formatInt(scan.artefacts)} artefacts
              </Button>
            )}
          </>
        ))
      }
    >
      <div className="space-y-4">
        {scan.status === "failed" && (
          <Banner tone="critical" title="The scan did not complete">
            {scan.error}
          </Banner>
        )}
        {scan.status === "cancelled" && <Banner tone="info" title="Scan cancelled">{scan.error ?? "Findings up to the point of cancellation were discarded."}</Banner>}
        {connection === "error" && active && <Banner tone="warning" title="Live updates paused">FALCON will reconnect automatically.</Banner>}

        <ProgressCard scan={scan} current={current} elapsed={elapsed} rate={throughput(samples)} />

        <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
          {kind === "endpoint" ? <EndpointsPanel scan={scan} coverage={coverage} active={active} /> : <CoverageCard coverage={coverage} active={active} />}
          {feed.length > 0 || active ? <LiveFeed feed={feed} active={active} /> : <FoundList scanId={scan.id} total={scan.artefacts} />}
        </div>

        {scan.status === "succeeded" && <ScanDiffCard scanId={scan.id} />}
        {scan.status === "succeeded" && scan.summary && <ResultsRow scan={scan} summary={scan.summary} />}
      </div>
    </Page>
  );
}

function useNow(interval: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!interval) return;
    const id = window.setInterval(() => setNow(Date.now()), interval);
    return () => window.clearInterval(id);
  }, [interval]);
  return interval ? now : Date.now();
}

/* ------------------------------------------------------------ progress */

function ProgressCard({ scan, current, elapsed, rate }: { scan: ScanDetail; current: string | null; elapsed: number; rate: number }) {
  const active = scan.status === "queued" || scan.status === "running";
  const fraction = scan.files_total ? scan.files_done / scan.files_total : scan.status === "succeeded" ? 1 : 0;
  const determinate = scan.status !== "queued" && (scan.stage === "analyse" || scan.stage === "done" || !active);
  const endpoint = scan.source?.kind === "endpoint";
  const unit = endpoint ? "endpoints" : "files";

  return (
    <Card className="grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
      <div className="flex justify-center md:px-4">
        <ProgressDial fraction={fraction} determinate={determinate} status={scan.status}>
          {determinate ? (
            <>
              <AnimatedNumber value={Math.round(fraction * 100)} format={(n) => `${Math.round(n)}%`} className="block text-title-1 tabular text-label" />
              <span className="text-footnote text-label-3">
                {formatInt(scan.files_done)} of {formatInt(scan.files_total)} {unit}
              </span>
            </>
          ) : (
            <>
              <span className="block text-headline text-label">{scan.status === "queued" ? "Queued" : STAGES.find((s) => s.key === scan.stage)?.label ?? "Starting"}</span>
              <span className="text-footnote text-label-3">{scan.status === "queued" ? "Waiting for a worker" : "Preparing"}</span>
            </>
          )}
        </ProgressDial>
      </div>
      <div className="min-w-0 space-y-5">
        <StageStepper scan={scan} />
        <div className="h-5 min-w-0 truncate font-mono text-footnote text-label-3" aria-live="off" title={current ?? undefined}>
          {active ? (current ?? scan.stage_detail ?? "") : ""}
        </div>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
          <Figure label={endpoint ? "Endpoints probed" : "Files analysed"} value={scan.files_done} />
          <Figure label="Evidence" value={scan.evidence} hint="Individual detections" />
          <Figure label={scan.status === "succeeded" ? "Artefacts" : "New artefacts"} value={scan.status === "succeeded" ? scan.artefacts : scan.new_artefacts} hint={scan.status === "succeeded" ? `${formatInt(scan.new_artefacts)} new to the system` : undefined} />
          <FigureText label="Throughput" value={active ? (rate > 0 ? `${rate >= 100 ? formatInt(rate) : rate.toFixed(1)} ${unit}/s` : "—") : scan.duration_seconds && scan.files_total ? `${formatInt(scan.files_total / Math.max(scan.duration_seconds, 0.1))} ${unit}/s` : "—"} />
          <FigureText label={active ? "Elapsed" : "Duration"} value={elapsed > 0 ? formatDuration(elapsed) : "—"} hint={scan.bytes_done ? formatBytes(scan.bytes_done) : undefined} />
        </dl>
      </div>
    </Card>
  );
}

function Figure({ label, value, hint }: { label: string; value: number; hint?: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-footnote font-medium text-label-3">{label}</dt>
      <dd>
        <AnimatedNumber value={value} format={(n) => formatInt(Math.round(n))} className="block text-title-2 tabular text-label" />
        {hint && <span className="block truncate text-caption text-label-3">{hint}</span>}
      </dd>
    </div>
  );
}

function FigureText({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-footnote font-medium text-label-3">{label}</dt>
      <dd>
        <span className="block truncate text-title-2 tabular text-label">{value}</span>
        {hint && <span className="block truncate text-caption text-label-3">{hint}</span>}
      </dd>
    </div>
  );
}

/** A progress dial: determinate fill during analysis, a gliding arc while the size is unknown. */
function ProgressDial({ fraction, determinate, status, children }: { fraction: number; determinate: boolean; status: ScanDetail["status"]; children: ReactNode }) {
  const reduce = useReducedMotion();
  const size = 172;
  const thickness = 10;
  const r = (size - thickness) / 2;
  const color = status === "failed" ? "var(--status-critical)" : status === "succeeded" ? "var(--status-good)" : status === "cancelled" ? "var(--label-3)" : "var(--accent)";
  const label = determinate ? `${Math.round(fraction * 100)} percent complete` : "Preparing";
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }} role="progressbar" aria-label={label} aria-valuenow={determinate ? Math.round(fraction * 100) : undefined} aria-valuemin={0} aria-valuemax={100}>
      {/* Colour flows through currentColor so the ring eases to green (or red) when the scan ends. */}
      <svg width={size} height={size} className="absolute inset-0 -rotate-90 transition-colors duration-500" style={{ color }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={thickness} stroke="currentColor" strokeOpacity={0.16} />
        {determinate ? (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            strokeWidth={thickness}
            strokeLinecap="round"
            stroke="currentColor"
            initial={false}
            animate={{ pathLength: Math.max(0.0001, Math.min(1, fraction)) }}
            transition={spring.data}
          />
        ) : (
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            strokeWidth={thickness}
            strokeLinecap="round"
            stroke="currentColor"
            style={{ originX: "50%", originY: "50%" }}
            initial={{ pathLength: 0.22, rotate: 0 }}
            animate={reduce ? { pathLength: 0.22 } : { pathLength: [0.18, 0.32, 0.18], rotate: 360 }}
            transition={{ rotate: { duration: 1.4, ease: "linear", repeat: Infinity }, pathLength: { duration: 2.8, ease: "easeInOut", repeat: Infinity } }}
          />
        )}
      </svg>
      <div className="relative px-4 text-center">{children}</div>
    </div>
  );
}

function StageStepper({ scan }: { scan: ScanDetail }) {
  const endpoint = scan.source?.kind === "endpoint";
  const stages = endpoint ? STAGES.filter((s) => s.key !== "enumerate") : STAGES;
  const index = scan.status === "succeeded" ? stages.length : scan.status === "queued" ? -1 : Math.max(0, stages.findIndex((s) => s.key === scan.stage));
  const failed = scan.status === "failed" || scan.status === "cancelled";

  return (
    <ol className="grid gap-2" style={{ gridTemplateColumns: `repeat(${stages.length}, minmax(0, 1fr))` }} aria-label="Scan stages">
      {stages.map((stage, i) => {
        const complete = i < index;
        const current = i === index && !failed && scan.status !== "succeeded";
        const stopped = i === index && failed;
        return (
          <li key={stage.key} className="min-w-0" aria-current={current ? "step" : undefined}>
            <div className="mb-2 flex items-center gap-1.5">
              <span
                className={cn(
                  "relative grid size-[22px] shrink-0 place-items-center rounded-full text-[11px] font-semibold transition-colors duration-300",
                  complete && "bg-accent text-on-accent",
                  current && "bg-accent-tint text-accent",
                  stopped && "bg-[var(--status-critical-tint)] text-critical",
                  !complete && !current && !stopped && "text-label-3 shadow-[inset_0_0_0_1.5px_var(--separator-strong)]",
                )}
              >
                {complete ? <Check className="size-3" strokeWidth={3.25} /> : i + 1}
                {current && <span className="absolute inset-0 rounded-full shadow-[inset_0_0_0_1.5px_var(--accent)]" style={{ animation: "falcon-breathe 1.8s ease-in-out infinite" }} />}
              </span>
              <span className={cn("h-[2px] min-w-0 flex-1 rounded-full transition-colors duration-500", i < index - 1 || (complete && scan.status === "succeeded") ? "bg-accent" : "bg-fill")} />
            </div>
            <div className={cn("truncate text-subhead font-medium", complete || current ? "text-label" : "text-label-3")}>{stage.label}</div>
            <div className="truncate text-caption text-label-3">{current && scan.stage_detail ? scan.stage_detail : stage.idle}</div>
          </li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------ coverage */

const DENSITY_STEPS = [0, 1, 3, 6, 12];

function intensity(leaf: CoverageLeaf): number {
  if (!leaf.scanned) return 0;
  const density = leaf.findings / leaf.scanned;
  if (density === 0) return 0;
  let step = 1;
  DENSITY_STEPS.forEach((threshold, i) => {
    if (density >= threshold && threshold > 0) step = i + 1;
  });
  return step;
}

function CoverageCard({ coverage, active }: { coverage: Record<string, CoverageLeaf>; active: boolean }) {
  const entries = Object.entries(coverage);
  const leaves: TreemapLeaf[] = entries.map(([key, leaf]) => ({
    key,
    size: leaf.files,
    progress: leaf.files ? leaf.scanned / leaf.files : 0,
    intensity: intensity(leaf),
    label: leaf.findings ? `${formatInt(leaf.findings)} found` : leaf.scanned ? undefined : `${formatInt(leaf.files)} files`,
    tooltip: {
      title: key === "." ? "Top-level files" : key,
      sub: formatBytes(leaf.bytes),
      rows: [
        { label: "files analysed", value: `${formatInt(leaf.scanned)} / ${formatInt(leaf.files)}` },
        { label: "detections", value: formatInt(leaf.findings) },
      ],
    },
  }));
  const hot = [...entries].sort((a, b) => b[1].findings - a[1].findings);

  return (
    <ChartFrame
      title="Coverage"
      subtitle="Directories sized by file count. Each fills as it is analysed; the deeper the blue, the more cryptography per file."
      table={{
        caption: "Scan coverage by directory",
        rows: hot,
        rowKey: ([key]) => key,
        columns: [
          { key: "path", header: "Directory", cell: ([key]) => <span className="font-mono text-footnote">{key}</span> },
          { key: "files", header: "Files", numeric: true, cell: ([, l]) => `${formatInt(l.scanned)} / ${formatInt(l.files)}` },
          { key: "bytes", header: "Size", numeric: true, cell: ([, l]) => formatBytes(l.bytes) },
          { key: "findings", header: "Detections", numeric: true, cell: ([, l]) => formatInt(l.findings) },
        ],
      }}
      footer={<CoverageKey active={active} />}
    >
      {leaves.length ? (
        <Treemap leaves={leaves} height={320} ariaLabel="Treemap of scan coverage by directory" />
      ) : (
        <div className="grid h-[320px] place-items-center rounded-[12px] bg-fill-2 text-subhead text-label-3">{active ? "Mapping the source…" : "No files were found to analyse."}</div>
      )}
    </ChartFrame>
  );
}

function CoverageKey({ active }: { active: boolean }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-footnote text-label-2">
      {active && (
        <span className="flex items-center gap-1.5">
          <LegendKey color={PENDING_FILL} kind="zone" /> Not analysed yet
        </span>
      )}
      <span className="flex items-center gap-1.5">
        <LegendKey color={intensityColor(0)} kind="rect" /> No cryptography
      </span>
      <span className="flex items-center gap-2">
        <span>Detections per file</span>
        <span className="flex items-center gap-[2px]" aria-hidden>
          {[1, 2, 3, 4, 5].map((step) => (
            <span key={step} className="h-2.5 w-5 first:rounded-l-[3px] last:rounded-r-[3px]" style={{ background: intensityColor(step) }} />
          ))}
        </span>
        <span className="tabular text-label-3">under 1 → 12+</span>
      </span>
    </div>
  );
}

/* ---------------------------------------------------------------- feed */

function LiveFeed({ feed, active }: { feed: Discovered[]; active: boolean }) {
  const navigate = useNavigate();
  return (
    <Card padded={false} className="flex max-h-[520px] min-h-[320px] flex-col">
      <div className="px-5 pb-2 pt-5">
        <CardHeader
          className="mb-0"
          title="Found"
          subtitle={active ? "Artefacts as FALCON finds them; new ones are marked." : "Artefacts this scan found."}
          actions={active && <span className="size-2 rounded-full bg-accent" style={{ animation: "falcon-breathe 1.6s ease-in-out infinite" }} aria-label="Live" />}
        />
      </div>
      {feed.length === 0 ? (
        <div className="grid flex-1 place-items-center px-5 pb-5 text-center text-subhead text-label-3">Listening for findings…</div>
      ) : (
        <ul className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          <AnimatePresence initial={false}>
            {feed.map((item) => (
              <motion.li key={item.id} layout initial={{ opacity: 0, y: -10, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring.smooth}>
                <button type="button" onClick={() => navigate(`/inventory/${item.id}`)} className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left transition-colors hover:bg-fill-2 focus-visible:focus-ring">
                  <KindGlyph kind={item.kind} size={28} />
                  <span className="min-w-0 flex-1">
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span className="truncate text-callout font-medium text-label">{item.name}</span>
                      {item.new && <span className="shrink-0 rounded-[4px] bg-accent-tint px-1 text-[10px] font-semibold uppercase tracking-wide text-accent-ink">New</span>}
                    </span>
                    <span className="block truncate font-mono text-caption text-label-3">
                      {item.path}
                      {item.line ? `:${item.line}` : ""}
                    </span>
                  </span>
                  {item.quantum && item.kind !== "library" && item.kind !== "hardware" && <QuantumDot status={item.quantum} />}
                </button>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </Card>
  );
}

function QuantumDot({ status: value }: { status: NonNullable<Discovered["quantum"]> }) {
  const meta = QUANTUM[value];
  const Icon = meta.icon;
  return (
    <span className="flex shrink-0 items-center gap-1 text-caption font-medium text-label-2" title={meta.label}>
      <Icon className="size-3.5" style={{ color: meta.tone === "good" ? "var(--status-good)" : meta.color }} strokeWidth={2.25} />
      {meta.short}
    </span>
  );
}

function FoundList({ scanId, total }: { scanId: string; total: number }) {
  const navigate = useNavigate();
  const artefacts = useArtefacts({ scan: scanId, sort: "risk", status: "all" });
  const items = artefacts.data?.pages[0]?.items.slice(0, 14) ?? [];
  return (
    <Card padded={false} className="flex max-h-[520px] min-h-[320px] flex-col">
      <div className="px-5 pb-2 pt-5">
        <CardHeader
          className="mb-0"
          title="Found in this scan"
          subtitle="Highest risk first."
          actions={
            total > items.length && (
              <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate(`/inventory?scan=${scanId}`)}>
                All {formatInt(total)}
              </Button>
            )
          }
        />
      </div>
      <ul className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {items.map((a) => (
          <li key={a.id}>
            <button type="button" onClick={() => navigate(`/inventory/${a.id}`)} className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left transition-colors hover:bg-fill-2 focus-visible:focus-ring">
              <KindGlyph kind={a.kind} size={28} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-callout font-medium text-label">{a.name}</span>
                <span className="block truncate text-caption text-label-3">
                  {KINDS[a.kind].singular} · {formatInt(a.occurrences)} {a.occurrences === 1 ? "occurrence" : "occurrences"}
                </span>
              </span>
              {a.quantum && <QuantumDot status={a.quantum} />}
            </button>
          </li>
        ))}
        {artefacts.isSuccess && items.length === 0 && <li className="px-3 py-10 text-center text-subhead text-label-3">This scan found no cryptography.</li>}
      </ul>
    </Card>
  );
}

/* ------------------------------------------------------------- results */

function ResultsRow({ scan, summary }: { scan: ScanDetail; summary: InventorySummary }) {
  const navigate = useNavigate();
  const composition = Object.entries(scan.stats.composition ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([key, value]) => ({ key, label: languageLabel(key), value }));
  const rows = KIND_ORDER.map((k) => ({ key: k, label: KINDS[k].label, icon: <KindIconOnly kind={k} />, values: summary.matrix[k] ?? {} }));
  const series = QUANTUM_ORDER.map((q) => ({ key: q, label: QUANTUM[q].label, color: QUANTUM[q].color }));
  const skipped = Object.entries(scan.stats.skipped ?? {}).filter(([, n]) => n > 0);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr_320px]">
      <ChartFrame
        className="self-start lg:col-span-2"
        title="What this scan found"
        subtitle={`${formatInt(summary.total)} artefacts by class and quantum status.`}
        legend={series.filter((s) => Object.values(summary.matrix).some((m) => (m?.[s.key as keyof typeof m] ?? 0) > 0)).map((s) => ({ label: s.label, color: s.color }))}
        table={{
          caption: "Artefacts found by class and quantum status",
          rows,
          rowKey: (r) => r.key,
          columns: [
            { key: "class", header: "Class", cell: (r) => r.label },
            ...QUANTUM_ORDER.map((q) => ({ key: q, header: QUANTUM[q].short, numeric: true, cell: (r: (typeof rows)[number]) => formatInt(r.values[q] ?? 0) })),
          ],
        }}
      >
        <StackedBars
          rows={rows}
          series={series}
          ariaLabel="Artefacts found by class and quantum status"
          onSelect={(kind, quantum) => navigate(`/inventory?scan=${scan.id}&kind=${kind}${quantum ? `&quantum=${quantum}` : ""}`)}
        />
      </ChartFrame>
      <div className="space-y-4">
        {composition.length > 0 && (
          <Card>
            <CardHeader title="Composition" subtitle={`${formatInt(scan.files_total)} files by type.`} />
            <BarList items={composition} ariaLabel="Files analysed by language or type" />
          </Card>
        )}
        <GroupedList header="Engine">
          <GroupedRow label="Engine" value={scan.stats.engine ? `FALCON ${scan.stats.engine}` : "—"} />
          <GroupedRow label="Knowledge base" value={scan.stats.knowledge?.algorithms ?? "—"} />
          {scan.stats.openssl && <GroupedRow label="OpenSSL" value={scan.stats.openssl.replace(/^OpenSSL /, "").split(" ")[0]} />}
          <GroupedRow label="Finished" value={scan.finished_at ? formatDateTime(scan.finished_at) : "—"} />
          {skipped.length > 0 && <GroupedRow label="Skipped" value={skipped.map(([k, n]) => `${formatInt(n)} ${k.replace(/_/g, " ")}`).join(", ")} />}
          {!!scan.stats.file_errors?.length && <GroupedRow label="Unreadable files" value={formatInt(scan.stats.file_errors.length)} />}
        </GroupedList>
      </div>
    </div>
  );
}

function KindIconOnly({ kind }: { kind: keyof typeof KINDS }) {
  const Icon = KINDS[kind].icon;
  return <Icon strokeWidth={1.9} />;
}

const LANGUAGE_LABELS: Record<string, string> = {
  material: "Keys & certificates",
  config: "Configuration",
  manifest: "Dependency manifests",
  binary: "Binaries",
  "java-archive": "Java archives",
  "java-class": "Java classes",
  text: "Text",
  c: "C / C++",
  csharp: "C#",
  javascript: "JavaScript",
  typescript: "TypeScript",
  php: "PHP",
};

function languageLabel(key: string): string {
  return LANGUAGE_LABELS[key] ?? key.charAt(0).toUpperCase() + key.slice(1);
}

/* ----------------------------------------------------------- endpoints */

/** Endpoint scans: each target's probe, live while running and the handshake verdict once done. */
function EndpointsPanel({ scan, coverage, active }: { scan: ScanDetail; coverage: Record<string, CoverageLeaf>; active: boolean }) {
  const reports = new Map((scan.stats.endpoints ?? []).map((r) => [r.endpoint, r]));
  const endpoints = reports.size ? [...reports.keys()] : Object.keys(coverage);
  const probing = active ? endpoints.find((e) => !coverage[e]?.scanned) : undefined;
  return (
    <Card padded={false} className="self-start overflow-hidden">
      <div className="px-5 pt-5">
        <CardHeader
          title="Post-quantum handshake"
          subtitle="FALCON offers the hybrid X25519MLKEM768 group with a genuine ML-KEM-768 key share, then records what each endpoint chooses."
        />
      </div>
      {endpoints.length === 0 && <div className="px-5 pb-6 text-subhead text-label-3">{active ? "Resolving endpoints…" : "No endpoints were probed."}</div>}
      <ul>
        {endpoints.map((endpoint) => {
          const r = reports.get(endpoint);
          const leaf = coverage[endpoint];
          const hybrid = !!r?.pq_probe?.selected && /MLKEM|Kyber/i.test(r.pq_probe.selected);
          return (
            <li key={endpoint} className="grid gap-3 px-5 py-3.5 hairline-t sm:grid-cols-[1.2fr_1fr_1fr_1.1fr] sm:items-center">
              <div className="min-w-0">
                <div className="truncate font-mono text-callout text-label">{endpoint}</div>
                {r?.error && <div className="text-footnote text-danger-ink">{r.error}</div>}
              </div>
              {r && !r.error ? (
                <>
                  <div>
                    <div className="text-caption text-label-3">Key exchange</div>
                    <QuantumBadge value={hybrid ? "hybrid" : "vulnerable"} short className="mt-0.5" />
                    <div className="mt-0.5 truncate font-mono text-caption text-label-2">{r.pq_probe?.selected ?? "—"}</div>
                  </div>
                  <div>
                    <div className="text-caption text-label-3">Negotiated</div>
                    <div className="text-callout text-label">{r.version ?? "—"}</div>
                    <div className="truncate font-mono text-caption text-label-2">{r.cipher ?? ""}</div>
                  </div>
                  <div>
                    <div className="text-caption text-label-3">Also accepts</div>
                    <div className="text-callout text-label">{r.also_accepted?.length ? r.also_accepted.join(", ") : "Nothing older"}</div>
                  </div>
                </>
              ) : !r ? (
                <div className="flex items-center gap-2 text-footnote text-label-3 sm:col-span-3">
                  {leaf?.scanned ? (
                    <>
                      <Check className="size-3.5 text-good" strokeWidth={2.75} /> Probed · {formatInt(leaf.findings)} detections
                    </>
                  ) : endpoint === probing ? (
                    <>
                      <ActivityIndicator size={13} label="Probing" /> Probing…
                    </>
                  ) : (
                    "Waiting"
                  )}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

