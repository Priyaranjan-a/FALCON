import { useState, type PointerEvent } from "react";
import { cn } from "@/design/cn";
import { formatInt } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { status } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export interface MatrixAxis {
  key: string;
  label: string;
}

export interface MatrixCell {
  likelihood: string;
  impact: string;
  count: number;
  score: number;
}

interface RiskMatrixProps {
  likelihood: MatrixAxis[]; // low → high
  impact: MatrixAxis[]; // low → high
  cells: MatrixCell[];
  selected?: { likelihood: string; impact: string } | null;
  onSelect?: (cell: { likelihood: string; impact: string } | null) => void;
  ariaLabel: string;
}

/* The zone of a cell is the classic risk-matrix reading: likelihood rank plus impact rank. */
const ZONES = [
  { max: 2, color: status.good, label: "Low" },
  { max: 4, color: status.warning, label: "Moderate" },
  { max: 6, color: status.serious, label: "High" },
  { max: 8, color: status.critical, label: "Critical" },
];

function zone(rank: number) {
  return ZONES.find((z) => rank <= z.max) ?? ZONES[ZONES.length - 1];
}

/**
 * Likelihood × impact, five by five. Each cell is tinted by its zone and
 * carries its count in ink; cells that hold artefacts are solid enough to read
 * at a glance, empty ones recede. Selecting a cell filters the register.
 */
export function RiskMatrix({ likelihood, impact, cells, selected, onSelect, ariaLabel }: RiskMatrixProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<{ l: number; i: number; x: number; y: number } | null>(null);
  const lookup = new Map(cells.map((c) => [`${c.likelihood}|${c.impact}`, c]));
  const rows = [...likelihood].reverse(); // most likely at the top
  const hovered = hover ? lookup.get(`${likelihood[hover.l].key}|${impact[hover.i].key}`) : undefined;

  const track = (e: PointerEvent, l: number, i: number) => {
    const box = ref.current?.getBoundingClientRect();
    if (box) setHover({ l, i, x: e.clientX - box.left, y: e.clientY - box.top });
  };

  return (
    <div ref={ref} className="relative" onPointerLeave={() => setHover(null)}>
      <div className="grid grid-cols-[18px_auto_1fr] gap-x-2">
        <div className="row-span-2 flex items-center justify-center">
          <span className="-rotate-90 whitespace-nowrap text-caption font-medium text-label-3">Likelihood</span>
        </div>
        <div className="grid gap-[3px]" style={{ gridTemplateRows: `repeat(${rows.length}, minmax(0, 1fr))` }}>
          {rows.map((r) => (
            <div key={r.key} className="flex items-center justify-end pr-1 text-caption text-label-3">
              {r.label}
            </div>
          ))}
        </div>
        <div role="grid" aria-label={ariaLabel} className="grid gap-[3px]" style={{ gridTemplateColumns: `repeat(${impact.length}, minmax(0, 1fr))` }}>
          {rows.map((r) => {
            const l = likelihood.indexOf(r);
            return impact.map((c, i) => {
              const cell = lookup.get(`${r.key}|${c.key}`);
              const z = zone(l + i);
              const active = selected?.likelihood === r.key && selected?.impact === c.key;
              const count = cell?.count ?? 0;
              return (
                <button
                  key={`${r.key}-${c.key}`}
                  type="button"
                  role="gridcell"
                  disabled={!count}
                  aria-label={`${r.label} likelihood, ${c.label} impact: ${count} artefacts`}
                  onPointerMove={(e) => track(e, l, i)}
                  onClick={() => onSelect?.(active ? null : { likelihood: r.key, impact: c.key })}
                  className={cn(
                    "hover-light relative grid aspect-[1.35] min-h-[42px] place-items-center rounded-[8px] text-subhead font-semibold tabular transition-[transform,box-shadow] duration-200 disabled:cursor-default",
                    count ? "text-label hover:scale-[1.04]" : "text-transparent",
                    active && "shadow-[0_0_0_2px_var(--label)]",
                  )}
                  style={{ background: `color-mix(in srgb, ${z.color} ${count ? 34 + Math.min(30, count * 2) : 9}%, transparent)` }}
                >
                  {count ? formatInt(count) : "·"}
                </button>
              );
            });
          })}
        </div>
        <div />
        <div className="mt-1.5 grid gap-[3px]" style={{ gridTemplateColumns: `repeat(${impact.length}, minmax(0, 1fr))` }}>
          {impact.map((c) => (
            <div key={c.key} className="truncate text-center text-caption text-label-3">
              {c.label}
            </div>
          ))}
        </div>
        <div />
        <div />
        <div className="mt-0.5 text-center text-caption font-medium text-label-3">Business impact</div>
      </div>
      <ChartTooltip visible={!!hover} x={hover?.x ?? 0} y={hover?.y ?? 0} containerWidth={width}>
        {hover && (
          <>
            <TooltipTitle sub={`${zone(hover.l + hover.i).label} zone`}>
              {likelihood[hover.l].label} · {impact[hover.i].label} impact
            </TooltipTitle>
            <TooltipRow kind="rect" color={zone(hover.l + hover.i).color} label="artefacts" value={formatInt(hovered?.count ?? 0)} />
            {hovered && <TooltipRow kind="none" label="highest score" value={String(hovered.score)} />}
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
