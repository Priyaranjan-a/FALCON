import { useState } from "react";
import { cn } from "@/design/cn";
import { formatInt, formatPercent } from "@/lib/format";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { LegendKey } from "../core/ChartFrame";
import { useMeasure } from "../core/useMeasure";

export interface MeterSegment {
  key: string;
  label: string;
  value: number;
  color: string;
}

/**
 * Part-to-whole as one segmented capacity bar, like a storage meter. Segments
 * are separated by 2px gaps; every value is also printed in the legend, so
 * nothing depends on hovering or on colour alone.
 */
export function Meter({ segments, ariaLabel, unit = "systems", className }: { segments: MeterSegment[]; ariaLabel: string; unit?: string; className?: string }) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<string | null>(null);
  const total = segments.reduce((s, x) => s + x.value, 0);
  const visible = segments.filter((s) => s.value > 0);

  let offset = 0;
  const positions = visible.map((s) => {
    const share = total ? s.value / total : 0;
    const start = offset;
    offset += share;
    return { ...s, start, share };
  });
  const hovered = positions.find((s) => s.key === hover);

  return (
    <div className={cn("relative", className)}>
      <div ref={ref} role="img" aria-label={ariaLabel} className={cn("flex h-2.5 w-full gap-[2px] overflow-hidden rounded-full", total === 0 && "bg-fill-2")}>
        {positions.map((s) => (
          <div
            key={s.key}
            onPointerEnter={() => setHover(s.key)}
            onPointerLeave={() => setHover(null)}
            className="h-full min-w-[3px] transition-[flex-grow,filter] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] hover:brightness-110"
            style={{ flexGrow: s.value, flexBasis: 0, background: s.color }}
          />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5">
        {segments.map((s) => (
          <li key={s.key} className={cn("flex items-center gap-1.5 text-footnote", s.value === 0 ? "text-label-4" : "text-label-2")}>
            <LegendKey color={s.value === 0 ? "var(--fill)" : s.color} kind="rect" />
            <span className="truncate">{s.label}</span>
            <span className="ml-auto pl-2 font-medium tabular text-label">{formatInt(s.value)}</span>
          </li>
        ))}
      </ul>
      <ChartTooltip visible={!!hovered} containerWidth={width} x={hovered ? (hovered.start + hovered.share / 2) * width : 0} y={4}>
        {hovered && (
          <>
            <TooltipTitle>{hovered.label}</TooltipTitle>
            <TooltipRow kind="rect" color={hovered.color} label={unit} value={formatInt(hovered.value)} />
            <TooltipRow kind="none" label="of total" value={formatPercent(total ? hovered.value / total : 0)} />
          </>
        )}
      </ChartTooltip>
    </div>
  );
}
