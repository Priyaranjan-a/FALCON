import { ArrowDownRight, ArrowUpRight, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { Badge, Card, CardHeader } from "@/design/components/Surface";
import { formatInt, formatRelative } from "@/lib/format";
import { useScanDiff } from "@/lib/queries";
import type { ScanDiffRow } from "@/lib/types";
import { KindGlyph, QuantumBadge } from "../discovery/vocab";

const VERDICT = {
  improved: { tone: "good" as const, label: "Improved" },
  regressed: { tone: "critical" as const, label: "Regressed" },
  mixed: { tone: "warning" as const, label: "Mixed" },
  unchanged: { tone: "neutral" as const, label: "No change" },
  baseline: { tone: "neutral" as const, label: "Baseline" },
};

/** Before and after: what changed since the previous scan of this source. */
export function ScanDiffCard({ scanId }: { scanId: string }) {
  const diff = useScanDiff(scanId);
  const d = diff.data;
  if (!d || !d.base) return null;
  const v = VERDICT[d.verdict];
  return (
    <Card>
      <CardHeader
        title="Since the previous scan"
        subtitle={`Compared with the scan ${formatRelative(d.base.finished_at ?? d.base.queued_at)}: ${formatInt(d.unchanged)} artefacts unchanged.`}
        actions={<Badge tone={v.tone}>{v.label}</Badge>}
      />
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Vulnerable retired" value={d.verified.retired} tone="good" />
        <Stat label="Post-quantum introduced" value={d.verified.introduced} tone="good" />
        <Stat label="New weaknesses" value={d.verified.regressions} tone={d.verified.regressions ? "critical" : "neutral"} />
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <List title="Gone" icon={<ArrowDownRight className="size-4 text-label-3" />} rows={d.removed} empty="Nothing removed." />
        <List title="New" icon={<ArrowUpRight className="size-4 text-label-3" />} rows={d.added} empty="Nothing new." />
        <List
          title="Spreading"
          icon={<Sparkles className="size-4 text-label-3" />}
          rows={d.spread.filter((r) => r.quantum === "pqc" || r.quantum === "hybrid")}
          empty="No post-quantum cryptography moved into new places."
          detail={(r) => `now also in ${r.new_locations?.slice(0, 2).join(", ")}`}
        />
      </div>
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "good" | "critical" | "neutral" }) {
  const bg = tone === "good" && value ? "bg-[var(--status-good-tint)]" : tone === "critical" && value ? "bg-[var(--status-critical-tint)]" : "bg-fill-2";
  return (
    <div className={`rounded-[12px] px-3.5 py-2.5 ${bg}`}>
      <div className="text-caption text-label-3">{label}</div>
      <div className="text-title-2 tabular text-label">{formatInt(value)}</div>
    </div>
  );
}

function List({ title, icon, rows, empty, detail }: { title: string; icon: ReactNode; rows: ScanDiffRow[]; empty: string; detail?: (r: ScanDiffRow) => string }) {
  const navigate = useNavigate();
  return (
    <div className="min-w-0">
      <div className="mb-1.5 flex items-center gap-1.5 text-footnote font-semibold text-label-2">
        {icon} {title} <span className="font-normal text-label-3">{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p className="text-footnote text-label-3">{empty}</p>
      ) : (
        <ul className="max-h-[260px] space-y-0.5 overflow-y-auto">
          {rows.map((r) => (
            <li key={r.id}>
              <button type="button" onClick={() => navigate(`/inventory/${r.id}`)} className="hover-light flex w-full items-center gap-2 rounded-[8px] px-1.5 py-1 text-left transition-colors hover:bg-fill-2">
                <KindGlyph kind={r.kind} size={22} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-subhead text-label">{r.name}</span>
                  {detail && <span className="block truncate text-caption text-label-3">{detail(r)}</span>}
                </span>
                {r.quantum && r.kind !== "library" && r.kind !== "hardware" && <QuantumBadge value={r.quantum} short />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
