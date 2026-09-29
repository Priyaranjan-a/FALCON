import { cn } from "@/design/cn";
import { Badge } from "@/design/components/Surface";
import { Tooltip } from "@/design/components/Menu";
import { formatPercent, formatYearsShort } from "@/lib/format";
import type { Criticality, Mosca, MoscaStatus, Vocabulary } from "@/lib/types";
import { MOSCA_COLORS, STATUS_META } from "@/viz/charts/MoscaChart";

const CRITICALITY_RANK: Record<Criticality, number> = { low: 1, moderate: 2, high: 3, critical: 4 };

/** Ordinal rank as signal bars, in ink: no status colour is spent on it. */
export function CriticalityBars({ value, vocabulary, withLabel = true }: { value: Criticality; vocabulary?: Vocabulary; withLabel?: boolean }) {
  const rank = CRITICALITY_RANK[value];
  const label = vocabulary?.criticality[value].label ?? value;
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap" aria-label={`Criticality: ${label}`}>
      <span aria-hidden className="flex h-3 items-end gap-[2px]">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={cn("w-[3px] rounded-[1px]", i <= rank ? "bg-label-2" : "bg-fill-hover")} style={{ height: 3 + i * 2.25 }} />
        ))}
      </span>
      {withLabel && <span className="text-subhead text-label">{label}</span>}
    </span>
  );
}

export function MoscaBadge({ status }: { status: MoscaStatus }) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} icon={<Icon style={{ color: meta.color }} strokeWidth={2.25} />}>
      {meta.label}
    </Badge>
  );
}

/** Compact Mosca glyph for table rows: Y then X against the horizon tick. */
export function MiniMosca({ mosca, max }: { mosca: Mosca; max: number }) {
  const w = 96;
  const scale = (v: number) => (Math.min(v, max) / max) * w;
  const y = scale(mosca.y);
  const x = scale(mosca.y + mosca.x) - y;
  const z = scale(mosca.z);
  return (
    <Tooltip
      content={
        <span className="tabular">
          Y {formatYearsShort(mosca.y)} + X {formatYearsShort(mosca.x)} vs Z {formatYearsShort(mosca.z)} · {formatPercent(mosca.probability)} chance a CRQC arrives first
        </span>
      }
    >
      <span className="inline-flex" aria-label={`Migration ${mosca.y} years plus shelf-life ${mosca.x} years against a ${mosca.z.toFixed(1)} year horizon`}>
        <svg width={w + 2} height={14} className="overflow-visible">
          <rect x={z} y={0} width={Math.max(0, w - z)} height={14} rx={2} style={{ fill: "var(--chart-zone)" }} />
          {y > 0 && <rect x={0} y={4} width={Math.max(0, y - 1)} height={6} style={{ fill: MOSCA_COLORS.migration }} />}
          {x > 0 && <rect x={y + 1} y={4} width={Math.max(0, x - 1)} height={6} rx={2} style={{ fill: MOSCA_COLORS.shelfLife }} />}
          <line x1={z} x2={z} y1={0} y2={14} style={{ stroke: "var(--label)" }} strokeWidth={1.25} />
        </svg>
      </span>
    </Tooltip>
  );
}
