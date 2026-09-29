import { scaleLinear, scaleSqrt } from "d3-scale";
import { useId, useMemo, useState } from "react";
import { formatInt, formatYears } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { linearTicks, niceDomain } from "../core/ticks";
import { chrome } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export interface PlanePoint {
  x: number;
  y: number;
  count: number;
  color: string;
  label: string;
  detail: string[];
  exposure: number;
}

interface MoscaPlaneProps {
  points: PlanePoint[];
  z: number;
  height?: number;
  ariaLabel: string;
  onSelect?: (point: PlanePoint) => void;
}

const M = { top: 20, right: 24, bottom: 44, left: 52 };

/**
 * Mosca's inequality as a plane. Lifetime X runs along the bottom, migration
 * effort Y up the side; the line X + Y = Z divides what is safe (below) from
 * what is exposed (the shaded region above). Bubbles are artefacts sharing a
 * position, sized by count and coloured by risk band.
 */
export function MoscaPlane({ points, z, height = 340, ariaLabel, onSelect }: MoscaPlaneProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const clip = useId();
  const [hover, setHover] = useState<number | null>(null);
  const innerW = Math.max(0, width - M.left - M.right);
  const innerH = height - M.top - M.bottom;

  // Wide enough for the horizon and the data, but never so wide that the line hugs the axis.
  const xMax = niceDomain(Math.min(Math.max(z * 1.25, ...points.map((p) => p.x + 1), 5), Math.max(z * 3, 30)));
  const yMax = niceDomain(Math.max(Math.min(z, 6), ...points.map((p) => p.y + 0.5), 3));
  const x = useMemo(() => scaleLinear().domain([0, xMax]).range([0, innerW]), [xMax, innerW]);
  const y = useMemo(() => scaleLinear().domain([0, yMax]).range([innerH, 0]), [yMax, innerH]);
  const r = useMemo(() => scaleSqrt().domain([1, Math.max(2, ...points.map((p) => p.count))]).range([6, 22]), [points]);

  // The exposed region: everything above the line x + y = z inside the plot.
  const lineStart = { x: x(Math.max(0, z - yMax)), y: y(Math.min(z, yMax)) };
  const lineEnd = { x: x(Math.min(z, xMax)), y: y(Math.max(0, z - xMax)) };
  const zone = `M${lineStart.x},${lineStart.y} L${lineEnd.x},${lineEnd.y} L${x(xMax)},${lineEnd.y} L${x(xMax)},${y(yMax)} L${lineStart.x},${y(yMax)} Z`;
  const hovered = hover !== null ? points[hover] : undefined;
  const ordered = points.map((p, i) => ({ p, i })).sort((a, b) => b.p.count - a.p.count);

  return (
    <div ref={ref} className="relative w-full" style={{ height }} onPointerLeave={() => setHover(null)}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block">
          <defs>
            <clipPath id={clip}>
              <rect x={0} y={0} width={innerW} height={innerH} />
            </clipPath>
          </defs>
          <g transform={`translate(${M.left},${M.top})`}>
            <path d={zone} style={{ fill: chrome.zone }} clipPath={`url(#${clip})`} />
            {linearTicks(yMax, 4).map((t) => (
              <g key={`y${t}`}>
                <line x1={0} x2={innerW} y1={y(t)} y2={y(t)} strokeWidth={1} style={{ stroke: chrome.grid }} />
                <text x={-10} y={y(t)} dy="0.32em" textAnchor="end" className="text-caption tabular" style={{ fill: chrome.ink }}>
                  {t}
                </text>
              </g>
            ))}
            {linearTicks(xMax, Math.max(3, Math.floor(innerW / 90))).map((t) => (
              <text key={`x${t}`} x={x(t)} y={innerH + 18} textAnchor="middle" className="text-caption tabular" style={{ fill: chrome.ink }}>
                {t}
              </text>
            ))}
            <line x1={0} x2={innerW} y1={innerH} y2={innerH} strokeWidth={1} style={{ stroke: chrome.axis }} />
            <line x1={lineStart.x} y1={lineStart.y} x2={lineEnd.x} y2={lineEnd.y} strokeWidth={1.5} strokeDasharray="5 4" style={{ stroke: "var(--label)" }} />
            <text x={lineStart.x + 8} y={lineStart.y + 14} textAnchor="start" className="text-caption font-semibold" style={{ fill: "var(--label)" }}>
              X + Y = Z ({formatYears(z)})
            </text>
            <text x={innerW - 6} y={14} textAnchor="end" className="text-caption font-medium" style={{ fill: "var(--status-critical)" }}>
              Exposed
            </text>
            <text x={8} y={innerH - 8} className="text-caption font-medium" style={{ fill: "var(--label-3)" }}>
              Inside the horizon
            </text>
            <g clipPath={`url(#${clip})`}>
              {ordered.map(({ p, i }) => (
                <circle
                  key={i}
                  cx={x(Math.min(p.x, xMax))}
                  cy={y(Math.min(p.y, yMax))}
                  r={r(p.count)}
                  strokeWidth={2}
                  className="cursor-pointer transition-[r,opacity] duration-300"
                  style={{ fill: p.color, stroke: "var(--surface)", opacity: hover === null || hover === i ? 0.92 : 0.45 }}
                  onPointerEnter={() => setHover(i)}
                  onClick={() => onSelect?.(p)}
                />
              ))}
            </g>
          </g>
          <text x={M.left + innerW / 2} y={height - 6} textAnchor="middle" className="text-caption font-medium" style={{ fill: "var(--label-2)" }}>
            Lifetime X — how long what it protects must stay safe (years)
          </text>
          <text transform={`translate(14,${M.top + innerH / 2}) rotate(-90)`} textAnchor="middle" className="text-caption font-medium" style={{ fill: "var(--label-2)" }}>
            Migration effort Y (years)
          </text>
        </svg>
      )}
      <ChartTooltip
        visible={!!hovered}
        x={hovered ? M.left + x(Math.min(hovered.x, xMax)) : 0}
        y={hovered ? M.top + y(Math.min(hovered.y, yMax)) : 0}
        containerWidth={width}
      >
        {hovered && (
          <>
            <TooltipTitle sub={`X ${formatYears(hovered.x)} · Y ${formatYears(hovered.y)}`}>{hovered.label}</TooltipTitle>
            <TooltipRow kind="rect" color={hovered.color} label="artefacts" value={formatInt(hovered.count)} />
            <TooltipRow kind="none" label={hovered.exposure > 0 ? "beyond the horizon" : "inside the horizon"} value={formatYears(Math.abs(hovered.exposure))} />
            {hovered.detail.map((d) => (
              <div key={d} className="mt-0.5 max-w-[220px] truncate text-caption text-label-2">
                {d}
              </div>
            ))}
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
