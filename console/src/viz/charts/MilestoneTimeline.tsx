import { scaleLinear } from "d3-scale";
import { useMemo, useState } from "react";
import { cn } from "@/design/cn";
import { formatDecimalYear, formatMilestoneDate } from "@/lib/format";
import type { Milestone } from "@/lib/types";
import { ChartTooltip, TooltipTitle } from "../core/ChartTooltip";
import { yearTicks } from "../core/ticks";
import { chrome, marks, series } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export const MILESTONE_COLORS = { deadline: series[0], publication: series[2] } as const;

interface TimelineProps {
  milestones: Milestone[];
  lanes: { key: string; label: string; sub?: string }[];
  domain: [number, number];
  now: number;
  horizon?: number;
  selected?: string | null;
  onSelect?: (id: string) => void;
  ariaLabel: string;
}

const LANE = 34;
const LABEL_W = 132;
const AXIS = 24;

export function MilestoneTimeline({ milestones, lanes, domain, now, horizon, selected, onSelect, ariaLabel }: TimelineProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<string | null>(null);
  const plotW = Math.max(0, width - LABEL_W - 12);
  const x = useMemo(() => scaleLinear().domain(domain).range([8, plotW - 8]).clamp(true), [domain, plotW]);
  const ticks = yearTicks(Math.ceil(domain[0]), domain[1], plotW, 48);
  const height = lanes.length * LANE;
  const hovered = milestones.find((m) => m.id === hover);
  const laneIndex = (authority: string) => lanes.findIndex((l) => l.key === authority);

  return (
    <div ref={ref} className="relative w-full" role="figure" aria-label={ariaLabel}>
      {width > 0 && (
        <div className="flex">
          <ul className="shrink-0" style={{ width: LABEL_W, marginTop: AXIS }}>
            {lanes.map((lane) => (
              <li key={lane.key} className="flex flex-col justify-center pr-3" style={{ height: LANE }}>
                <span className="truncate text-subhead font-medium text-label">{lane.label}</span>
                {lane.sub && <span className="truncate text-caption text-label-3">{lane.sub}</span>}
              </li>
            ))}
          </ul>
          <svg width={plotW} height={height + AXIS} className="block overflow-visible">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={AXIS - 4} y2={AXIS + height} style={{ stroke: chrome.grid }} strokeWidth={1} shapeRendering="crispEdges" />
                <text x={x(t)} y={12} textAnchor="middle" className="tabular" style={{ fill: chrome.ink, fontSize: 11 }}>
                  {t}
                </text>
              </g>
            ))}
            {lanes.map((lane, i) => (
              <line key={lane.key} x1={0} x2={plotW} y1={AXIS + (i + 1) * LANE} y2={AXIS + (i + 1) * LANE} style={{ stroke: chrome.grid }} strokeWidth={1} shapeRendering="crispEdges" />
            ))}
            {horizon !== undefined && horizon >= domain[0] && horizon <= domain[1] && (
              <g>
                <rect x={x(horizon)} y={AXIS} width={Math.max(0, plotW - x(horizon))} height={height} style={{ fill: chrome.zone }} />
                <line x1={x(horizon)} x2={x(horizon)} y1={AXIS - 2} y2={AXIS + height} style={{ stroke: chrome.label }} strokeWidth={1.25} />
              </g>
            )}
            <line x1={x(now)} x2={x(now)} y1={AXIS - 2} y2={AXIS + height} style={{ stroke: "var(--accent)" }} strokeWidth={1.25} />

            {milestones.map((m) => {
              const lane = laneIndex(m.authority);
              if (lane < 0) return null;
              const cx = x(m.decimal_year);
              const cy = AXIS + lane * LANE + LANE / 2;
              const past = m.decimal_year < now;
              const isSelected = selected === m.id;
              const active = hover === m.id || isSelected;
              const color = m.kind === "deadline" ? MILESTONE_COLORS.deadline : MILESTONE_COLORS.publication;
              const size = active ? 6.5 : 5;
              return (
                <g
                  key={m.id}
                  tabIndex={0}
                  role="button"
                  aria-label={`${m.authority_name}: ${m.title}, ${formatMilestoneDate(m.date, m.precision)}`}
                  aria-pressed={isSelected}
                  onPointerEnter={() => setHover(m.id)}
                  onPointerLeave={() => setHover(null)}
                  onFocus={() => setHover(m.id)}
                  onBlur={() => setHover(null)}
                  onClick={() => onSelect?.(m.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect?.(m.id);
                    }
                  }}
                  className="outline-none"
                  style={{ opacity: past && !active ? 0.45 : 1, transition: "opacity 150ms" }}
                >
                  <circle cx={cx} cy={cy} r={marks.hitMin / 2} fill="transparent" />
                  {m.kind === "deadline" ? (
                    <rect
                      x={cx - size}
                      y={cy - size}
                      width={size * 2}
                      height={size * 2}
                      rx={2}
                      transform={`rotate(45 ${cx} ${cy})`}
                      style={{ fill: color, stroke: chrome.surface, transition: "all 150ms" }}
                      strokeWidth={marks.ring}
                    />
                  ) : (
                    <circle cx={cx} cy={cy} r={size} style={{ fill: color, stroke: chrome.surface, transition: "r 150ms" }} strokeWidth={marks.ring} />
                  )}
                  {isSelected && <circle cx={cx} cy={cy} r={11} fill="none" style={{ stroke: color }} strokeWidth={1.5} />}
                </g>
              );
            })}
          </svg>
        </div>
      )}
      <div className="mt-2 flex items-center gap-4 pl-[132px] text-caption text-label-3">
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-[1.5px] bg-accent" /> Today · {formatDecimalYear(now)}
        </span>
        {horizon !== undefined && (
          <span className="flex items-center gap-1.5">
            <span className="h-3 w-[1.5px] bg-label" /> Planning horizon · {formatDecimalYear(horizon)}
          </span>
        )}
      </div>
      <ChartTooltip
        visible={!!hovered}
        containerWidth={width}
        x={hovered ? LABEL_W + x(hovered.decimal_year) : 0}
        y={hovered ? AXIS + laneIndex(hovered.authority) * LANE + LANE / 2 : 0}
      >
        {hovered && (
          <div className="max-w-[260px]">
            <TooltipTitle sub={`${hovered.authority_name} · ${hovered.framework}`}>{hovered.title}</TooltipTitle>
            <div className={cn("text-footnote font-semibold tabular text-label")}>{formatMilestoneDate(hovered.date, hovered.precision)}</div>
            <p className="mt-1 text-footnote text-label-2">{hovered.detail}</p>
          </div>
        )}
      </ChartTooltip>
    </div>
  );
}
