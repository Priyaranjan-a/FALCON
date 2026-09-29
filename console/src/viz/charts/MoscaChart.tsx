import { scaleLinear } from "d3-scale";
import { CircleCheck, CircleDot, TriangleAlert } from "lucide-react";
import { useMemo, useState, type KeyboardEvent } from "react";
import { cn } from "@/design/cn";
import { formatPercent, formatYearsShort } from "@/lib/format";
import type { MoscaStatus } from "@/lib/types";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { linearTicks, niceDomain } from "../core/ticks";
import { barPathH, chrome, marks, series } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";
import { useTweenedArray } from "../core/useTween";

export interface MoscaRow {
  id: string;
  code: string;
  name: string;
  x: number;
  y: number;
  status: MoscaStatus;
  probability: number;
}

export const MOSCA_COLORS = { migration: series[0], shelfLife: series[1] } as const;

export const STATUS_META: Record<MoscaStatus, { label: string; icon: typeof TriangleAlert; color: string; tone: "critical" | "warning" | "good" }> = {
  exposed: { label: "Exposed", icon: TriangleAlert, color: "var(--status-critical)", tone: "critical" },
  watch: { label: "Watch", icon: CircleDot, color: "var(--status-warning)", tone: "warning" },
  clear: { label: "Clear", icon: CircleCheck, color: "var(--status-good)", tone: "good" },
};

interface MoscaChartProps {
  rows: MoscaRow[];
  /** Mosca's Z: planning horizon in years from today. */
  z: number;
  onSelect?: (id: string) => void;
  showStatus?: boolean;
  labelWidth?: number;
  ariaLabel: string;
}

const ROW = 36;
const BAR = 12;
const AXIS = 26;

/**
 * Mosca's inequality, one row per system: migration time (Y) from today, then
 * the shelf-life (X) of data encrypted just before migration completes. The
 * planning horizon (Z) is a rule; everything past it sits in the exposed zone.
 */
export function MoscaChart({ rows, z, onSelect, showStatus = true, labelWidth = 210, ariaLabel }: MoscaChartProps) {
  const [plotRef, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<string | null>(null);

  const tickCount = width < 360 ? 3 : 6;
  const max = niceDomain(Math.max(z * 1.25, ...rows.map((r) => r.x + r.y), 1), tickCount);
  const scale = useMemo(() => scaleLinear().domain([0, max]).range([0, Math.max(0, width - 8)]), [max, width]);
  const ticks = linearTicks(max, tickCount);
  const zX = useTweenedArray([scale(z)], { from: "target" })[0];
  const hovered = rows.find((r) => r.id === hover);
  const hoveredIndex = hovered ? rows.indexOf(hovered) : -1;
  const plotHeight = rows.length * ROW;

  return (
    <div className="relative" role="figure" aria-label={ariaLabel}>
      {/* Axis */}
      <div className="flex" style={{ height: AXIS }}>
        <div style={{ width: labelWidth }} className="shrink-0 self-end pb-2 text-caption font-medium uppercase tracking-wide text-label-3">
          System
        </div>
        <div ref={plotRef} className="relative min-w-0 flex-1">
          {width > 0 &&
            ticks.map((t) => (
              <span key={t} className="absolute bottom-2 -translate-x-1/2 text-caption tabular text-label-3" style={{ left: scale(t) }}>
                {t === 0 ? "Today" : `${t}y`}
              </span>
            ))}
        </div>
        {showStatus && <div className="w-[92px] shrink-0" />}
      </div>

      <div className="relative">
        {/* Underlay: grid, exposed zone and the horizon rule */}
        {width > 0 && (
          <svg aria-hidden width={width} height={plotHeight} className="pointer-events-none absolute top-0 block" style={{ left: labelWidth }}>
            <rect x={zX} y={0} width={Math.max(0, width - zX)} height={plotHeight} style={{ fill: chrome.zone }} />
            {ticks.map((t) => (
              <line key={t} x1={scale(t)} x2={scale(t)} y1={0} y2={plotHeight} style={{ stroke: t === 0 ? chrome.axis : chrome.grid }} strokeWidth={1} shapeRendering="crispEdges" />
            ))}
            <line x1={zX} x2={zX} y1={0} y2={plotHeight} style={{ stroke: chrome.label }} strokeWidth={1.25} />
          </svg>
        )}
        <ul className="relative">
          {rows.map((row, index) => (
          <MoscaBarRow
            key={row.id}
            row={row}
            index={index}
            scale={scale}
            width={width}
            labelWidth={labelWidth}
            showStatus={showStatus}
            active={hover === row.id}
            onHover={setHover}
            onSelect={onSelect}
          />
          ))}
        </ul>
      </div>

      {/* Footer band: the horizon label sits under its rule, clear of the tick labels. */}
      <div className="relative h-7">
        {width > 0 && (
          <div
            className="absolute top-1.5 -translate-x-1/2 whitespace-nowrap rounded-full bg-label px-2 py-px text-caption font-semibold tabular text-surface"
            style={{ left: labelWidth + zX }}
          >
            Horizon Z · {formatYearsShort(z)}
          </div>
        )}
      </div>

      <ChartTooltip
        visible={!!hovered}
        containerWidth={labelWidth + width + (showStatus ? 92 : 0)}
        x={hovered ? labelWidth + scale(hovered.x + hovered.y) : 0}
        y={AXIS + hoveredIndex * ROW + ROW / 2}
      >
        {hovered && (
          <>
            <TooltipTitle sub={hovered.code}>{hovered.name}</TooltipTitle>
            <TooltipRow kind="rect" color={MOSCA_COLORS.migration} label="Migration time (Y)" value={formatYearsShort(hovered.y)} />
            <TooltipRow kind="rect" color={MOSCA_COLORS.shelfLife} label="Data shelf-life (X)" value={formatYearsShort(hovered.x)} />
            <div className="my-1.5 h-px bg-separator" />
            <TooltipRow
              kind="none"
              label={hovered.x + hovered.y - z > 0 ? "beyond the horizon" : "inside the horizon"}
              value={`${hovered.x + hovered.y - z > 0 ? "+" : "−"}${formatYearsShort(Math.abs(hovered.x + hovered.y - z))}`}
            />
            <TooltipRow kind="none" label="chance a CRQC arrives first" value={formatPercent(hovered.probability)} />
          </>
        )}
      </ChartTooltip>
    </div>
  );
}

interface RowProps {
  row: MoscaRow;
  index: number;
  scale: (v: number) => number;
  width: number;
  labelWidth: number;
  showStatus: boolean;
  active: boolean;
  onHover: (id: string | null) => void;
  onSelect?: (id: string) => void;
}

function MoscaBarRow({ row, index, scale, width, labelWidth, showStatus, active, onHover, onSelect }: RowProps) {
  const [yW, xW] = useTweenedArray([scale(row.y), scale(row.x)], { duration: 640, delay: Math.min(index, 12) * 35 });
  const meta = STATUS_META[row.status];
  const Icon = meta.icon;
  const top = (ROW - BAR) / 2;
  const gap = xW > 0 && yW > 0 ? marks.gap : 0;
  const interactive = !!onSelect;

  const onKey = (e: KeyboardEvent) => {
    if (interactive && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onSelect!(row.id);
    }
  };

  return (
    <li
      tabIndex={interactive ? 0 : -1}
      role={interactive ? "button" : undefined}
      aria-label={`${row.name}: migration ${row.y} years, shelf-life ${row.x} years, ${meta.label}`}
      onPointerEnter={() => onHover(row.id)}
      onPointerLeave={() => onHover(null)}
      onFocus={() => onHover(row.id)}
      onBlur={() => onHover(null)}
      onClick={interactive ? () => onSelect!(row.id) : undefined}
      onKeyDown={onKey}
      className={cn("relative flex items-center rounded-[8px] outline-none transition-colors duration-100", active && "bg-fill-2")}
      style={{ height: ROW }}
    >
      <div style={{ width: labelWidth }} className="flex min-w-0 shrink-0 items-center gap-2 pl-1 pr-3">
        <span className="shrink-0 rounded-[4px] bg-fill-2 px-1 font-mono text-[10.5px] font-medium text-label-2">{row.code}</span>
        <span className="truncate text-subhead text-label">{row.name}</span>
      </div>
      <div className="relative min-w-0 flex-1" style={{ height: ROW }}>
        {width > 0 && (
          <svg width={width} height={ROW} className="block overflow-visible">
            {yW > 0.5 && <path d={xW > 0.5 ? rectPath(0, top, yW - gap / 2, BAR) : barPathH(0, top, yW, BAR)} style={{ fill: MOSCA_COLORS.migration }} />}
            {xW > 0.5 && <path d={barPathH(yW + gap / 2, top, Math.max(0, xW - gap / 2), BAR)} style={{ fill: MOSCA_COLORS.shelfLife }} />}
          </svg>
        )}
      </div>
      {showStatus && (
        <div className="flex w-[92px] shrink-0 items-center gap-1.5 pl-3 text-footnote font-medium text-label-2">
          <Icon className="size-3.5 shrink-0" style={{ color: meta.color }} strokeWidth={2.25} />
          {meta.label}
        </div>
      )}
    </li>
  );
}

function rectPath(x: number, y: number, w: number, h: number): string {
  return w > 0 ? `M${x},${y}h${w}v${h}h${-w}z` : "";
}
