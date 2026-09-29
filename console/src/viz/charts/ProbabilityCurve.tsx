import { scaleLinear } from "d3-scale";
import { area, curveMonotoneX, line } from "d3-shape";
import { useId, useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";
import { formatDecimalYear, formatPercent } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { yearTicks } from "../core/ticks";
import { chrome, marks } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";
import { useTweenedArray } from "../core/useTween";

export interface CurveSeries {
  id: string;
  label: string;
  color: string;
  points: { year: number; p: number }[];
  /** The series the story is about: area wash and full-strength line. */
  emphasis?: boolean;
}

export interface CurveMarker {
  year: number;
  p: number;
  title: string;
  value: string;
}

interface ProbabilityCurveProps {
  series: CurveSeries[];
  marker?: CurveMarker;
  /** Horizontal guide at the tolerated probability. */
  tolerance?: number;
  domain: [number, number];
  height?: number;
  ariaLabel: string;
  /** Caption under the year in the tooltip. */
  readout?: string;
}

const M = { top: 34, right: 18, bottom: 28, left: 44 };

/**
 * Cumulative probability that a CRQC exists, over calendar time. A crosshair
 * snaps to the nearest quarter and reads every series at once; the planning
 * horizon is annotated where the curve crosses the organisation's tolerance.
 */
export function ProbabilityCurve({ series, marker, tolerance, domain, height = 300, ariaLabel, readout = "Probability a CRQC exists" }: ProbabilityCurveProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const clip = useId();
  const [hover, setHover] = useState<number | null>(null);

  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const x = useMemo(() => scaleLinear().domain(domain).range([0, innerW]), [domain, innerW]);
  const y = useMemo(() => scaleLinear().domain([0, 1]).range([innerH, 0]), [innerH]);

  // All series share the same sampling grid (quarter years from today).
  const grid = useMemo(() => (series[0]?.points ?? []).map((p) => p.year).filter((yr) => yr >= domain[0] && yr <= domain[1]), [series, domain]);
  const xTicks = yearTicks(Math.ceil(domain[0]), domain[1], innerW);
  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  const hoverYear = hover === null ? null : grid[hover];

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const year = x.invert(e.clientX - box.left);
    let best = 0;
    for (let i = 1; i < grid.length; i++) if (Math.abs(grid[i] - year) < Math.abs(grid[best] - year)) best = i;
    setHover(best);
  };

  const onKey = (e: KeyboardEvent<SVGRectElement>) => {
    const perYear = 4;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const delta = (e.key === "ArrowRight" ? 1 : -1) * perYear;
      setHover((h) => Math.min(grid.length - 1, Math.max(0, (h ?? 0) + delta)));
    } else if (e.key === "Escape") setHover(null);
  };

  const probabilityAt = (s: CurveSeries, year: number) => s.points.find((p) => Math.abs(p.year - year) < 1e-6)?.p ?? 0;

  return (
    <div ref={ref} className="relative w-full select-none" style={{ height }}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block overflow-visible">
          <defs>
            <clipPath id={clip}>
              <rect x={0} y={-4} width={innerW} height={innerH + 8} />
            </clipPath>
          </defs>
          <g transform={`translate(${M.left},${M.top})`}>
            {yTicks.map((t) => (
              <g key={t} transform={`translate(0,${y(t)})`}>
                <line x1={0} x2={innerW} style={{ stroke: t === 0 ? chrome.axis : chrome.grid }} strokeWidth={1} shapeRendering="crispEdges" />
                <text x={-10} dy="0.32em" textAnchor="end" className="tabular" style={{ fill: chrome.ink, fontSize: 11 }}>
                  {Math.round(t * 100)}%
                </text>
              </g>
            ))}
            {xTicks.map((t) => (
              <text key={t} x={x(t)} y={innerH + 19} textAnchor="middle" className="tabular" style={{ fill: chrome.ink, fontSize: 11 }}>
                {t}
              </text>
            ))}

            <g clipPath={`url(#${clip})`}>
              {[...series].sort((a, b) => Number(!!a.emphasis) - Number(!!b.emphasis)).map((s) => (
                <CurvePath key={s.id} series={s} grid={grid} x={x} y={y} />
              ))}
            </g>

            {tolerance !== undefined && marker && (
              <line x1={0} x2={x(marker.year)} y1={y(tolerance)} y2={y(tolerance)} style={{ stroke: chrome.label2 }} strokeOpacity={0.55} strokeWidth={1} />
            )}
            {marker && <Marker marker={marker} x={x} y={y} innerW={innerW} innerH={innerH} />}

            {hoverYear !== null && (
              <g pointerEvents="none">
                <line x1={x(hoverYear)} x2={x(hoverYear)} y1={0} y2={innerH} style={{ stroke: chrome.label2 }} strokeOpacity={0.5} strokeWidth={1} />
                {series.map((s) => (
                  <circle
                    key={s.id}
                    cx={x(hoverYear)}
                    cy={y(probabilityAt(s, hoverYear))}
                    r={marks.dotRadius}
                    style={{ fill: s.color, stroke: chrome.surface }}
                    strokeWidth={marks.ring}
                  />
                ))}
              </g>
            )}

            <rect
              width={innerW}
              height={innerH}
              fill="transparent"
              tabIndex={0}
              role="slider"
              aria-label="Inspect probability by year"
              aria-valuemin={domain[0]}
              aria-valuemax={domain[1]}
              aria-valuenow={hoverYear ?? undefined}
              aria-valuetext={hoverYear !== null ? `${formatDecimalYear(hoverYear)}: ${series.map((s) => `${s.label} ${formatPercent(probabilityAt(s, hoverYear))}`).join(", ")}` : undefined}
              onPointerMove={onMove}
              onPointerLeave={() => setHover(null)}
              onKeyDown={onKey}
              onBlur={() => setHover(null)}
              style={{ outline: "none" }}
            />
          </g>
        </svg>
      )}
      <ChartTooltip visible={hoverYear !== null} x={hoverYear !== null ? M.left + x(hoverYear) : 0} y={M.top + innerH / 2} containerWidth={width}>
        {hoverYear !== null && (
          <>
            <TooltipTitle sub={readout}>{formatDecimalYear(hoverYear)}</TooltipTitle>
            {[...series]
              .sort((a, b) => Number(!!b.emphasis) - Number(!!a.emphasis))
              .map((s) => (
                <TooltipRow key={s.id} color={s.color} label={s.label} value={formatPercent(probabilityAt(s, hoverYear))} />
              ))}
          </>
        )}
      </ChartTooltip>
    </div>
  );
}

function CurvePath({ series, grid, x, y }: { series: CurveSeries; grid: number[]; x: (v: number) => number; y: (v: number) => number }) {
  const target = useMemo(() => {
    const lookup = new Map(series.points.map((p) => [p.year.toFixed(4), p.p]));
    return grid.map((yr) => lookup.get(yr.toFixed(4)) ?? 0);
  }, [series.points, grid]);
  const values = useTweenedArray(target, { duration: 560 });
  const pts = grid.map((yr, i) => [x(yr), y(values[i] ?? 0)] as [number, number]);
  const linePath = line().curve(curveMonotoneX)(pts) ?? "";
  const areaPath = area().curve(curveMonotoneX).y0(y(0)).y1((d) => d[1])(pts) ?? "";
  const emphasis = !!series.emphasis;
  return (
    <g style={{ opacity: emphasis ? 1 : 0.5, transition: "opacity 200ms" }}>
      {emphasis && <path d={areaPath} style={{ fill: series.color }} fillOpacity={marks.areaOpacity} />}
      <path d={linePath} fill="none" style={{ stroke: series.color }} strokeWidth={emphasis ? marks.line : 1.5} strokeLinejoin="round" strokeLinecap="round" />
    </g>
  );
}

function Marker({ marker, x, y, innerW, innerH }: { marker: CurveMarker; x: (v: number) => number; y: (v: number) => number; innerW: number; innerH: number }) {
  const [year, p] = useTweenedArray([marker.year, marker.p], { duration: 560, from: "target" });
  const cx = x(year);
  const cy = y(p);
  const labelX = Math.min(Math.max(cx, 60), innerW - 60);
  return (
    <g pointerEvents="none">
      <line x1={cx} x2={cx} y1={cy} y2={innerH} style={{ stroke: chrome.label2 }} strokeOpacity={0.55} strokeWidth={1} />
      <line x1={cx} x2={cx} y1={4} y2={cy - 8} style={{ stroke: chrome.label2 }} strokeOpacity={0.25} strokeWidth={1} />
      <circle cx={cx} cy={cy} r={5} style={{ fill: chrome.label, stroke: chrome.surface }} strokeWidth={marks.ring} />
      <text x={labelX} y={-20} textAnchor="middle" style={{ fill: chrome.ink, fontSize: 11 }}>
        {marker.title}
      </text>
      <text x={labelX} y={-6} textAnchor="middle" style={{ fill: chrome.label, fontSize: 12, fontWeight: 600 }}>
        {marker.value}
      </text>
    </g>
  );
}
