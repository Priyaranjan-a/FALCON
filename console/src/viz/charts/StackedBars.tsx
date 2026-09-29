import { useState, type PointerEvent, type ReactNode } from "react";
import { cn } from "@/design/cn";
import { formatInt, formatPercent } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { useMeasure } from "../core/useMeasure";

export interface StackSeries {
  key: string;
  label: string;
  color: string;
}

export interface StackRow {
  key: string;
  label: string;
  icon?: ReactNode;
  values: Record<string, number>;
}

interface StackedBarsProps {
  rows: StackRow[];
  series: StackSeries[];
  ariaLabel: string;
  unit?: string;
  onSelect?: (row: string, series?: string) => void;
  selected?: string | null;
}

/**
 * Horizontal stacked bars on one shared scale: part-to-whole per row and
 * rows comparable with each other. Segments are separated by 2px surface
 * gaps; only the data end is rounded; the row total sits at the tip.
 */
export function StackedBars({ rows, series, ariaLabel, unit = "artefacts", onSelect, selected }: StackedBarsProps) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<{ row: string; series: string; x: number; y: number } | null>(null);
  const totals = rows.map((r) => series.reduce((n, s) => n + (r.values[s.key] ?? 0), 0));
  const max = Math.max(1, ...totals);

  const hoveredRow = hover ? rows.find((r) => r.key === hover.row) : undefined;
  const hoveredSeries = hover ? series.find((s) => s.key === hover.series) : undefined;
  const hoveredTotal = hoveredRow ? totals[rows.indexOf(hoveredRow)] : 0;

  const track = (e: PointerEvent, row: string, key: string) => {
    const rect = ref.current?.getBoundingClientRect();
    if (rect) setHover({ row, series: key, x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div
      ref={ref}
      className="relative"
      role="img"
      aria-label={ariaLabel}
      onPointerLeave={() => setHover(null)}
    >
      <ul className="space-y-1">
        {rows.map((row, i) => {
          const total = totals[i];
          const visible = series.filter((s) => (row.values[s.key] ?? 0) > 0);
          const Row = onSelect ? "button" : "div";
          return (
            <li key={row.key}>
              <Row
                type={onSelect ? "button" : undefined}
                onClick={onSelect ? () => onSelect(row.key, hover?.row === row.key ? hover.series : undefined) : undefined}
                className={cn(
                  "group grid w-full grid-cols-[132px_1fr] items-center gap-3 rounded-[8px] px-1.5 py-[7px] text-left transition-colors max-sm:grid-cols-[104px_1fr]",
                  onSelect && "hover:bg-fill-2 focus-visible:focus-ring",
                  selected === row.key && "bg-accent-tint hover:bg-accent-tint",
                )}
              >
                <span className={cn("flex min-w-0 items-center gap-2 text-subhead", total ? "text-label" : "text-label-3")}>
                  {row.icon && <span className="flex shrink-0 text-label-3 [&>svg]:size-[15px]">{row.icon}</span>}
                  <span className="truncate">{row.label}</span>
                </span>
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    className="flex h-3 min-w-0 gap-[2px] transition-[width] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
                    style={{ width: total ? `max(4px, calc((100% - 44px) * ${total / max}))` : 0 }}
                  >
                    {visible.map((s, k) => (
                      <span
                        key={s.key}
                        onPointerMove={(e) => track(e, row.key, s.key)}
                        className={cn(
                          "h-full min-w-[3px] transition-[flex-grow,opacity] duration-500",
                          k === visible.length - 1 && "rounded-r-[4px]",
                          hover && hover.row === row.key && hover.series !== s.key && "opacity-55",
                        )}
                        style={{ flexGrow: row.values[s.key], flexBasis: 0, background: s.color }}
                      />
                    ))}
                  </span>
                  <span className="shrink-0 text-subhead font-medium tabular text-label">{total ? formatInt(total) : <span className="text-label-4">0</span>}</span>
                </span>
              </Row>
            </li>
          );
        })}
      </ul>
      <ChartTooltip visible={!!(hoveredRow && hoveredSeries)} x={hover?.x ?? 0} y={hover?.y ?? 0} containerWidth={width}>
        {hoveredRow && hoveredSeries && (
          <>
            <TooltipTitle sub={`${formatInt(hoveredTotal)} ${unit} in total`}>{hoveredRow.label}</TooltipTitle>
            <TooltipRow kind="rect" color={hoveredSeries.color} label={hoveredSeries.label} value={formatInt(hoveredRow.values[hoveredSeries.key] ?? 0)} />
            <TooltipRow kind="none" label="of this class" value={formatPercent(hoveredTotal ? (hoveredRow.values[hoveredSeries.key] ?? 0) / hoveredTotal : 0)} />
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
