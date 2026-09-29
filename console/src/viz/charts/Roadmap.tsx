import { scaleLinear } from "d3-scale";
import { useMemo, useState } from "react";
import { formatDecimalYear, formatInt } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { yearTicks } from "../core/ticks";
import { chrome } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export interface RoadmapTrack {
  key: string;
  label: string;
  color: string;
}

export interface RoadmapLane {
  id: string;
  label: string;
  sublabel?: string;
  bars: { track: string; start: number; finish: number; count: number }[];
}

export interface RoadmapMarker {
  year: number;
  label: string;
  tone: "critical" | "neutral";
}

interface RoadmapProps {
  lanes: RoadmapLane[];
  tracks: RoadmapTrack[];
  domain: [number, number];
  markers?: RoadmapMarker[];
  ariaLabel: string;
  onSelect?: (lane: string, track: string) => void;
}

const LABEL_W = 176;
const BAR_H = 9;
const BAR_GAP = 3;
const LANE_PAD = 10;
const AXIS_H = 26;

/**
 * The migration programme over time: one lane per system, one thin track per
 * wave, the planning horizon and policy deadlines as rules across every lane.
 */
export function Roadmap({ lanes, tracks, domain, markers = [], ariaLabel, onSelect }: RoadmapProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<{ lane: number; bar: number } | null>(null);
  const innerW = Math.max(0, width - LABEL_W - 16);
  const x = useMemo(() => scaleLinear().domain(domain).range([0, innerW]), [domain, innerW]);
  const trackIndex = new Map(tracks.map((t, i) => [t.key, i]));

  const layout = useMemo(() => {
    let y = AXIS_H;
    return lanes.map((lane) => {
      const used = [...new Set(lane.bars.map((b) => b.track))].sort((a, b) => (trackIndex.get(a) ?? 0) - (trackIndex.get(b) ?? 0));
      const height = LANE_PAD * 2 + used.length * (BAR_H + BAR_GAP) - BAR_GAP;
      const top = y;
      y += height;
      return { lane, top, height, rows: new Map(used.map((t, i) => [t, i])) };
    });
  }, [lanes, trackIndex]);
  const totalH = (layout.at(-1)?.top ?? AXIS_H) + (layout.at(-1)?.height ?? 0) + 4;
  const hovered = hover ? { lane: layout[hover.lane].lane, bar: layout[hover.lane].lane.bars[hover.bar] } : null;
  const hoveredPos = hover ? layout[hover.lane] : null;

  return (
    <div ref={ref} className="relative w-full" style={{ height: totalH }} onPointerLeave={() => setHover(null)}>
      {width > 0 && (
        <svg width={width} height={totalH} role="img" aria-label={ariaLabel} className="block">
          {layout.map(({ lane, top, height }, i) => (
            <g key={lane.id}>
              {i % 2 === 0 && <rect x={0} y={top} width={width} height={height} rx={8} style={{ fill: "var(--fill-2)", opacity: 0.6 }} />}
              <text x={10} y={top + height / 2 - (lane.sublabel ? 6 : 0)} dy="0.32em" className="text-subhead font-medium" style={{ fill: "var(--label)" }}>
                {lane.label}
              </text>
              {lane.sublabel && (
                <text x={10} y={top + height / 2 + 9} dy="0.32em" className="text-caption" style={{ fill: "var(--label-3)" }}>
                  {lane.sublabel}
                </text>
              )}
            </g>
          ))}
          <g transform={`translate(${LABEL_W},0)`}>
            {yearTicks(Math.ceil(domain[0]), domain[1], innerW, 56).map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={AXIS_H - 6} y2={totalH} strokeWidth={1} style={{ stroke: chrome.grid }} />
                <text x={x(t)} y={12} textAnchor="middle" className="text-caption tabular" style={{ fill: chrome.ink }}>
                  {t}
                </text>
              </g>
            ))}
            {markers.map((m) => (
              <g key={m.label} transform={`translate(${x(Math.min(domain[1], Math.max(domain[0], m.year)))},0)`}>
                <line y1={AXIS_H - 4} y2={totalH} strokeWidth={m.tone === "critical" ? 1.5 : 1} strokeDasharray={m.tone === "critical" ? undefined : "3 3"}
                  style={{ stroke: m.tone === "critical" ? "var(--status-critical)" : "var(--label-3)" }} />
                <title>{`${m.label} · ${formatDecimalYear(m.year)}`}</title>
              </g>
            ))}
            {layout.map(({ lane, top, rows }, li) =>
              lane.bars.map((bar, bi) => {
                const track = tracks[trackIndex.get(bar.track) ?? 0];
                const row = rows.get(bar.track) ?? 0;
                const x0 = x(bar.start);
                const w = Math.max(4, x(bar.finish) - x0);
                const active = hover?.lane === li && hover?.bar === bi;
                return (
                  <rect
                    key={`${lane.id}-${bar.track}`}
                    x={x0}
                    y={top + LANE_PAD + row * (BAR_H + BAR_GAP)}
                    width={w}
                    height={BAR_H}
                    rx={4}
                    className="cursor-pointer transition-opacity duration-200"
                    style={{ fill: track.color, opacity: hover && !active ? 0.45 : 1 }}
                    onPointerEnter={() => setHover({ lane: li, bar: bi })}
                    onClick={() => onSelect?.(lane.id, bar.track)}
                  />
                );
              }),
            )}
          </g>
        </svg>
      )}
      <ChartTooltip
        visible={!!hovered}
        x={hovered ? LABEL_W + x(hovered.bar.finish) : 0}
        y={hoveredPos ? hoveredPos.top + hoveredPos.height / 2 : 0}
        containerWidth={width}
      >
        {hovered && (
          <>
            <TooltipTitle sub={`${hovered.lane.label}${hovered.lane.sublabel ? ` · ${hovered.lane.sublabel}` : ""}`}>
              {tracks.find((t) => t.key === hovered.bar.track)?.label}
            </TooltipTitle>
            <TooltipRow kind="rect" color={tracks.find((t) => t.key === hovered.bar.track)?.color} label="artefacts" value={formatInt(hovered.bar.count)} />
            <TooltipRow kind="none" label="" value={`${formatDecimalYear(hovered.bar.start)} – ${formatDecimalYear(hovered.bar.finish)}`} />
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
