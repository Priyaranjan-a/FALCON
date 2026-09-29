import { scaleLinear } from "d3-scale";
import { area, curveMonotoneX, stack } from "d3-shape";
import { useMemo, useState, type PointerEvent } from "react";
import { formatDecimalYear, formatInt } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { linearTicks, niceDomain, yearTicks } from "../core/ticks";
import { chrome } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export interface StateSeries {
  key: string;
  label: string;
  color: string;
}

export interface StateSample {
  year: number;
  counts: Record<string, number>;
}

export interface StateMarker {
  year: number;
  label: string;
  tone: "neutral" | "critical";
}

interface StateAreaProps {
  samples: StateSample[];
  series: StateSeries[]; // bottom → top
  year: number;
  markers?: StateMarker[];
  height?: number;
  ariaLabel: string;
  onScrub?: (year: number) => void;
}

const M = { top: 26, right: 16, bottom: 26, left: 40 };

/**
 * How many artefacts are in each state, year by year. Areas stack from the
 * worst state up; a vertical rule marks the year being replayed, and dragging
 * across the chart moves it.
 */
export function StateArea({ samples, series, year, markers = [], height = 260, ariaLabel, onScrub }: StateAreaProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = height - M.top - M.bottom;
  const start = samples[0]?.year ?? 0;
  const end = samples[samples.length - 1]?.year ?? 1;
  const total = Math.max(1, ...samples.map((s) => series.reduce((n, k) => n + (s.counts[k.key] ?? 0), 0)));
  const yMax = niceDomain(total, 4);
  const x = useMemo(() => scaleLinear().domain([start, end]).range([0, innerW]), [start, end, innerW]);
  const y = useMemo(() => scaleLinear().domain([0, yMax]).range([innerH, 0]), [yMax, innerH]);

  const layers = useMemo(() => {
    const rows = samples.map((s) => ({ year: s.year, ...Object.fromEntries(series.map((k) => [k.key, s.counts[k.key] ?? 0])) }));
    return stack<Record<string, number>>().keys(series.map((k) => k.key))(rows as Record<string, number>[]);
  }, [samples, series]);
  const shape = area<[number, number] & { data: Record<string, number> }>()
    .x((d) => x(d.data.year))
    .y0((d) => y(d[0]))
    .y1((d) => y(d[1]))
    .curve(curveMonotoneX);

  const indexAt = (px: number) => {
    const target = x.invert(px);
    let best = 0;
    samples.forEach((s, i) => {
      if (Math.abs(s.year - target) < Math.abs(samples[best].year - target)) best = i;
    });
    return best;
  };
  const move = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const px = Math.max(0, Math.min(innerW, e.clientX - box.left));
    const i = indexAt(px);
    setHover(i);
    if (dragging) onScrub?.(samples[i].year);
  };
  const hovered = hover !== null ? samples[hover] : undefined;

  return (
    <div ref={ref} className="relative w-full select-none" style={{ height }}>
      {width > 0 && samples.length > 1 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block">
          <g transform={`translate(${M.left},${M.top})`}>
            {linearTicks(yMax, 4).map((t) => (
              <g key={t}>
                <line x1={0} x2={innerW} y1={y(t)} y2={y(t)} strokeWidth={1} style={{ stroke: chrome.grid }} />
                <text x={-8} y={y(t)} dy="0.32em" textAnchor="end" className="text-caption tabular" style={{ fill: chrome.ink }}>
                  {formatInt(t)}
                </text>
              </g>
            ))}
            {layers.map((layer, i) => (
              <path key={series[i].key} d={shape(layer as never) ?? ""} style={{ fill: series[i].color, opacity: 0.85 }} />
            ))}
            {yearTicks(Math.ceil(start), end, innerW).map((t) => (
              <text key={t} x={x(t)} y={innerH + 18} textAnchor="middle" className="text-caption tabular" style={{ fill: chrome.ink }}>
                {t}
              </text>
            ))}
            {markers.map((m) => (
              <g key={`${m.year}-${m.label}`} transform={`translate(${x(m.year)},0)`}>
                <line y1={-6} y2={innerH} strokeWidth={1} strokeDasharray="2 3" style={{ stroke: m.tone === "critical" ? "var(--status-critical)" : chrome.axis }} />
                <circle cy={-8} r={3.5} style={{ fill: m.tone === "critical" ? "var(--status-critical)" : "var(--label-3)" }}>
                  <title>{`${formatDecimalYear(m.year)} · ${m.label}`}</title>
                </circle>
              </g>
            ))}
            <g transform={`translate(${x(Math.min(end, Math.max(start, year)))},0)`}>
              <line y1={-12} y2={innerH} strokeWidth={2} style={{ stroke: "var(--label)" }} />
              <rect x={-26} y={-24} width={52} height={17} rx={8.5} style={{ fill: "var(--label)" }} />
              <text y={-12} textAnchor="middle" className="text-caption font-semibold tabular" style={{ fill: "var(--bg)" }}>
                {Math.floor(year)}
              </text>
            </g>
            <rect
              width={innerW}
              height={innerH}
              fill="transparent"
              className="cursor-ew-resize"
              onPointerMove={move}
              onPointerLeave={() => {
                setHover(null);
                setDragging(false);
              }}
              onPointerDown={(e) => {
                setDragging(true);
                e.currentTarget.setPointerCapture(e.pointerId);
                const box = e.currentTarget.getBoundingClientRect();
                onScrub?.(samples[indexAt(e.clientX - box.left)].year);
              }}
              onPointerUp={() => setDragging(false)}
            />
          </g>
        </svg>
      )}
      <ChartTooltip visible={!!hovered && !dragging} x={hovered ? M.left + x(hovered.year) : 0} y={M.top + 40} containerWidth={width}>
        {hovered && (
          <>
            <TooltipTitle>{formatDecimalYear(hovered.year)}</TooltipTitle>
            {[...series].reverse().map((k) => (
              <TooltipRow key={k.key} kind="rect" color={k.color} label={k.label} value={formatInt(hovered.counts[k.key] ?? 0)} />
            ))}
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
