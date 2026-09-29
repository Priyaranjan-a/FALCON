import { Cpu, FlaskConical, Play } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/design/components/Button";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { Card, CardHeader, EmptyState, GroupedList, GroupedRow } from "@/design/components/Surface";
import { useCan } from "@/lib/access";
import { formatDateTime } from "@/lib/format";
import { useBenchmarks, useRunBenchmarks } from "@/lib/queries";
import type { BenchmarkReport, BenchmarkResult } from "@/lib/types";
import { DotPlot } from "@/viz/charts/DotPlot";
import { ChartFrame, LegendKey } from "@/viz/core/ChartFrame";
import { series } from "@/viz/core/tokens";
import { Page, PageSkeleton } from "../shell/Page";
import { formatBytesShort, formatMicros } from "./vocab";

const KEM_OPS = [
  { key: "keygen", label: "Key generation", color: series[0] },
  { key: "encapsulate", label: "Encapsulate", color: series[1] },
  { key: "decapsulate", label: "Decapsulate", color: series[2] },
];
const SIG_OPS = [
  { key: "keygen", label: "Key generation", color: series[0] },
  { key: "sign", label: "Sign", color: series[1] },
  { key: "verify", label: "Verify", color: series[2] },
];
const TAGS: Record<string, string> = { pqc: "Post-quantum", hybrid: "Hybrid", vulnerable: "Classical" };

export default function LabPage() {
  const report = useBenchmarks();
  const run = useRunBenchmarks();
  const canRun = useCan("scans.run");
  if (report.isPending) return <PageSkeleton />;
  const data = report.data;

  const start = () =>
    run.mutate(undefined, {
      onSuccess: (r) => toast.success(`Measured ${r.results.length} algorithms in ${r.duration_seconds.toFixed(1)} s`),
      onError: (e) => toast.error(e.message),
    });

  return (
    <Page
      title="Benchmark Lab"
      subtitle="Post-quantum, hybrid and classical cryptography measured on this host through the platform’s own OpenSSL: what a migration costs in time and on the wire, here rather than on a vendor’s slide."
      width="wide"
      actions={
        canRun && (
          <Button variant="filled" icon={run.isPending ? undefined : <Play className="fill-current" />} loading={run.isPending} onClick={start}>
            {data ? "Measure again" : "Run benchmarks"}
          </Button>
        )
      }
    >
      {run.isPending && (
        <Card className="mb-4 flex items-center gap-3">
          <ActivityIndicator size={18} />
          <div>
            <div className="text-callout font-medium text-label">Measuring…</div>
            <div className="text-footnote text-label-3">Key generation, encapsulation, signing and verification for 13 algorithms. This takes about ten seconds.</div>
          </div>
        </Card>
      )}
      {!data ? (
        <Card>
          <EmptyState
            icon={<FlaskConical />}
            title="No measurements yet"
            message="Run the lab to measure ML-KEM, ML-DSA, hybrid key exchange and the classical algorithms they replace on this machine."
            action={canRun && <Button variant="filled" icon={<Play className="fill-current" />} loading={run.isPending} onClick={start}>Run benchmarks</Button>}
          />
        </Card>
      ) : (
        <Results report={data} />
      )}
    </Page>
  );
}

function Results({ report }: { report: BenchmarkReport }) {
  const kems = report.results.filter((r) => r.kind === "kem");
  const sigs = report.results.filter((r) => r.kind === "signature");
  const find = (name: string) => report.results.find((r) => r.algorithm === name);
  const insights = takeaways(find);
  const toRow = (r: BenchmarkResult) => ({ key: r.algorithm, label: r.algorithm, tag: TAGS[r.quantum], values: r.operations });

  return (
    <div className="space-y-4">
      {insights.length > 0 && (
        <div className="grid gap-4 md:grid-cols-3">
          {insights.map((t) => (
            <Card key={t.title}>
              <div className="text-subhead font-medium text-label-2">{t.title}</div>
              <div className="mt-2 text-title-2 tabular text-label">{t.value}</div>
              <p className="mt-1 text-footnote text-label-3">{t.detail}</p>
            </Card>
          ))}
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartFrame
          title="Key establishment"
          subtitle="Time per operation, logarithmic scale. Lower is faster."
          legend={KEM_OPS.map((o) => ({ label: o.label, color: o.color, kind: "dot" as const }))}
          table={{ caption: "Key establishment timings", rows: kems, rowKey: (r) => r.algorithm, columns: [
            { key: "a", header: "Algorithm", cell: (r) => r.algorithm },
            ...KEM_OPS.map((o) => ({ key: o.key, header: o.label, numeric: true, cell: (r: BenchmarkResult) => formatMicros(r.operations[o.key]) })),
          ] }}
        >
          <DotPlot ariaLabel="Key establishment timings" rows={kems.map(toRow)} series={KEM_OPS} format={formatMicros} />
        </ChartFrame>
        <ChartFrame
          title="Signatures"
          subtitle="Time per operation, logarithmic scale. RSA key generation sits far to the right."
          legend={SIG_OPS.map((o) => ({ label: o.label, color: o.color, kind: "dot" as const }))}
          table={{ caption: "Signature timings", rows: sigs, rowKey: (r) => r.algorithm, columns: [
            { key: "a", header: "Algorithm", cell: (r) => r.algorithm },
            ...SIG_OPS.map((o) => ({ key: o.key, header: o.label, numeric: true, cell: (r: BenchmarkResult) => formatMicros(r.operations[o.key]) })),
          ] }}
        >
          <DotPlot ariaLabel="Signature timings" rows={sigs.map(toRow)} series={SIG_OPS} format={formatMicros} />
        </ChartFrame>
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader title="On the wire" subtitle="Bytes a peer receives: public key plus ciphertext or signature." />
          <WireBars results={report.results} />
        </Card>
        <GroupedList header="Measured on" footer={report.method}>
          <GroupedRow icon={<Cpu />} label="Processor" value={<span className="block max-w-[190px] truncate" title={report.host.processor}>{report.host.processor}</span>} />
          <GroupedRow label="Cores" value={report.host.cpus} />
          <GroupedRow label="Operating system" value={report.host.system} />
          <GroupedRow label="OpenSSL" value={report.host.openssl.replace(/^OpenSSL /, "").split(" ")[0]} />
          <GroupedRow label="Measured" value={formatDateTime(report.measured_at)} />
          <GroupedRow label="Duration" value={`${report.duration_seconds.toFixed(1)} s`} />
        </GroupedList>
      </div>
    </div>
  );
}

function WireBars({ results }: { results: BenchmarkResult[] }) {
  const rows = [...results].map((r) => ({ r, total: r.sizes.public_key + (r.sizes.ciphertext ?? r.sizes.signature ?? 0) })).sort((a, b) => b.total - a.total);
  const max = Math.max(...rows.map((x) => x.total));
  return (
    <>
      <div className="mb-3 flex gap-4 text-footnote text-label-2">
        <span className="flex items-center gap-1.5"><LegendKey color={series[0]} kind="rect" /> Public key</span>
        <span className="flex items-center gap-1.5"><LegendKey color={series[3]} kind="rect" /> Ciphertext or signature</span>
      </div>
      <ul className="space-y-1.5">
        {rows.map(({ r, total }) => {
          const second = r.sizes.ciphertext ?? r.sizes.signature ?? 0;
          return (
            <li key={r.algorithm} className="grid grid-cols-[140px_1fr_64px] items-center gap-3">
              <span className="truncate text-subhead text-label">{r.algorithm}</span>
              <span className="flex h-2.5 gap-[2px]" style={{ width: `max(4px, ${(total / max) * 100}%)` }} title={`${r.sizes.public_key} + ${second} bytes`}>
                <span className="h-full rounded-l-[2px]" style={{ flexGrow: r.sizes.public_key, flexBasis: 0, background: series[0] }} />
                <span className="h-full rounded-r-[4px]" style={{ flexGrow: second, flexBasis: 0, background: series[3] }} />
              </span>
              <span className="text-right text-subhead font-medium tabular text-label">{formatBytesShort(total)}</span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function takeaways(find: (name: string) => BenchmarkResult | undefined) {
  const out: { title: string; value: string; detail: string }[] = [];
  const hybrid = find("X25519MLKEM768");
  const x = find("X25519");
  if (hybrid && x) {
    const extra = hybrid.operations.encapsulate + hybrid.operations.decapsulate - x.operations.encapsulate - x.operations.decapsulate;
    out.push({
      title: "Hybrid TLS key exchange",
      value: `+${formatMicros(Math.max(0, extra))}`,
      detail: `Extra computation per handshake over X25519, and +${formatBytesShort(hybrid.sizes.public_key + (hybrid.sizes.ciphertext ?? 0) - 64)} on the wire.`,
    });
  }
  const kem = find("ML-KEM-768");
  const ecdh = find("ECDH P-256");
  if (kem && ecdh) {
    const ratio = ecdh.operations.encapsulate / kem.operations.encapsulate;
    out.push({
      title: "ML-KEM-768 against ECDH P-256",
      value: ratio >= 1 ? `${ratio.toFixed(1)}× faster` : `${(1 / ratio).toFixed(1)}× slower`,
      detail: `Encapsulation ${formatMicros(kem.operations.encapsulate)} against an ECDH exchange of ${formatMicros(ecdh.operations.encapsulate)}.`,
    });
  }
  const dsa = find("ML-DSA-65");
  const ecdsa = find("ECDSA P-256");
  if (dsa && ecdsa) {
    out.push({
      title: "ML-DSA-65 verification",
      value: formatMicros(dsa.operations.verify),
      detail: `Against ${formatMicros(ecdsa.operations.verify)} for ECDSA P-256; signatures grow from ${ecdsa.sizes.signature} to ${dsa.sizes.signature} bytes.`,
    });
  }
  return out;
}
