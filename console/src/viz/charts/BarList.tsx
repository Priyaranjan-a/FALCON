import { cn } from "@/design/cn";
import { formatInt } from "@/lib/format";
import { series } from "../core/tokens";

export interface BarListItem {
  key: string;
  label: string;
  value: number;
  hint?: string;
}

/**
 * Ranked horizontal bars for one nominal series: one colour (slot 1) for
 * every bar, value at the tip, thin marks, rows that lift on hover.
 */
export function BarList({ items, ariaLabel, color = series[0], onSelect, className }: { items: BarListItem[]; ariaLabel: string; color?: string; onSelect?: (key: string) => void; className?: string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul aria-label={ariaLabel} className={cn("space-y-0.5", className)}>
      {items.map((item) => {
        const share = item.value / max;
        const Row = onSelect ? "button" : "div";
        return (
          <li key={item.key}>
            <Row
              type={onSelect ? "button" : undefined}
              onClick={onSelect ? () => onSelect(item.key) : undefined}
              title={item.hint}
              className={cn("group flex w-full items-center gap-3 rounded-[8px] px-1.5 py-1.5 text-left transition-colors", onSelect && "hover:bg-fill-2 focus-visible:focus-ring")}
            >
              <span className={cn("w-28 shrink-0 truncate text-subhead", item.value ? "text-label" : "text-label-3")}>{item.label}</span>
              <span className="relative flex h-2 min-w-0 flex-1 items-center">
                <span
                  className="h-2 rounded-r-[4px] transition-[width] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
                  style={{ width: item.value ? `max(3px, ${share * 100}%)` : 0, background: color }}
                />
              </span>
              <span className="w-8 shrink-0 text-right text-subhead font-medium tabular text-label">{formatInt(item.value)}</span>
            </Row>
          </li>
        );
      })}
    </ul>
  );
}
