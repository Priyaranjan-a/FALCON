import { scaleLog } from "d3-scale";
import { useMemo, useState } from "react";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { chrome } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export interface DotSeries {
  key: string;
  label: string;
  color: string;
}

export interface DotRow {
  key: string;
  label: string;
  tag?: string;
  values: Record<string, number>;
}

interface DotPlotProps {
  rows: DotRow[];
  series: DotSeries[];
  format: (v: number) => string;
  ariaLabel: string;
  unit?: string;
}

const LABEL_W = 150;
const ROW_H = 38;
const AXIS_H = 24;

/**
 * Several measurements per row on one logarithmic axis: each row a thin rule
 * from its fastest to its slowest value, each measurement a dot. Suits timings
 * that span orders of magnitude.
 */
export function DotPlot({ rows, series, format, ariaLabel, unit = "" }: DotPlotProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const values = rows.flatMap((r) => series.map((s) => r.values[s.key]).filter((v): v is number => v > 0));
  const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...values, 10))));
  const hi = Math.pow(10, Math.ceil(Math.log10(Math.max(...values, 100))));
  const innerW = Math.max(0, width - LABEL_W - 20);
  const x = useMemo(() => scaleLog().domain([lo, hi]).range([0, innerW]), [lo, hi, innerW]);
  const decades: number[] = [];
  for (let d = lo; d <= hi * 1.0001; d *= 10) decades.push(d);
  const height = AXIS_H + rows.length * ROW_H + 4;
  const hovered = hover !== null ? rows[hover] : null;

  return (
    <div ref={ref} className="relative w-full" style={{ height }} onPointerLeave={() => setHover(null)}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block">
          <g transform={`translate(${LABEL_W},0)`}>
            {decades.map((d) => (
              <g key={d}>
                <line x1={x(d)} x2={x(d)} y1={AXIS_H - 4} y2={height} strokeWidth={1} style={{ stroke: chrome.grid }} />
                <text x={x(d)} y={12} textAnchor="middle" className="text-caption tabular" style={{ fill: chrome.ink }}>
                  {format(d)}
                </text>
              </g>
            ))}
          </g>
          {rows.map((row, i) => {
            const y = AXIS_H + i * ROW_H + ROW_H / 2;
            const vs = series.map((s) => row.values[s.key]).filter((v): v is number => v > 0);
            const active = hover === i;
            return (
              <g key={row.key} onPointerEnter={() => setHover(i)} className="cursor-default">
                <rect x={0} y={y - ROW_H / 2} width={width} height={ROW_H} rx={8} style={{ fill: active ? "var(--fill-2)" : "transparent" }} />
                <text x={8} y={row.tag ? y - 6 : y} dy="0.32em" className="text-subhead" style={{ fill: "var(--label)" }}>
                  {row.label}
                </text>
                {row.tag && (
                  <text x={8} y={y + 9} dy="0.32em" className="text-caption" style={{ fill: "var(--label-3)" }}>
                    {row.tag}
                  </text>
                )}
                <g transform={`translate(${LABEL_W},0)`}>
                  {vs.length > 1 && <line x1={x(Math.min(...vs))} x2={x(Math.max(...vs))} y1={y} y2={y} strokeWidth={2} strokeLinecap="round" style={{ stroke: chrome.axis }} />}
                  {series.map((s) =>
                    row.values[s.key] > 0 ? (
                      <circle key={s.key} cx={x(row.values[s.key])} cy={y} r={active ? 6 : 5} strokeWidth={2} className="transition-[r] duration-200" style={{ fill: s.color, stroke: "var(--surface)" }} />
                    ) : null,
                  )}
                </g>
              </g>
            );
          })}
        </svg>
      )}
      <ChartTooltip visible={!!hovered} x={hovered ? LABEL_W + x(Math.max(...series.map((s) => hovered.values[s.key] || lo))) : 0} y={hover !== null ? AXIS_H + hover * ROW_H + ROW_H / 2 : 0} containerWidth={width}>
        {hovered && (
          <>
            <TooltipTitle sub={hovered.tag}>{hovered.label}</TooltipTitle>
            {series.map((s) => (
              <TooltipRow key={s.key} kind="rect" color={s.color} label={`${s.label}${unit}`} value={hovered.values[s.key] ? format(hovered.values[s.key]) : "—"} />
            ))}
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
