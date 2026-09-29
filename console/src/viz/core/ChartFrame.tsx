import { ChartLine, Table2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { cn } from "@/design/cn";
import { Segmented } from "@/design/components/Segmented";
import { Card } from "@/design/components/Surface";
import { Table, type Column } from "@/design/components/Table";

export interface LegendItem {
  label: ReactNode;
  color: string;
  kind?: "rect" | "line" | "zone" | "dot";
}

export function Legend({ items, className }: { items: LegendItem[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      {items.map((item, i) => (
        <li key={i} className="flex items-center gap-1.5 text-footnote text-label-2">
          <LegendKey color={item.color} kind={item.kind ?? "rect"} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export function LegendKey({ color, kind }: { color: string; kind: LegendItem["kind"] }) {
  if (kind === "line") return <span aria-hidden className="h-[2px] w-3 rounded-full" style={{ background: color }} />;
  if (kind === "dot") return <span aria-hidden className="size-2 rounded-full" style={{ background: color }} />;
  if (kind === "zone") return <span aria-hidden className="size-2.5 rounded-[3px] shadow-[inset_0_0_0_0.5px_var(--separator-strong)]" style={{ background: color }} />;
  return <span aria-hidden className="size-2.5 rounded-[3px]" style={{ background: color }} />;
}

interface ChartFrameProps<T> {
  title: ReactNode;
  subtitle?: ReactNode;
  legend?: LegendItem[];
  actions?: ReactNode;
  /** The table twin: every chart's values are reachable without hovering. */
  table: { columns: Column<T>[]; rows: T[]; rowKey: (row: T) => string; caption: string };
  children: ReactNode;
  className?: string;
  footer?: ReactNode;
  /** Dim the chart while fresh data loads, keeping the frame (no skeleton flash). */
  refreshing?: boolean;
}

export function ChartFrame<T>({ title, subtitle, legend, actions, table, children, className, footer, refreshing }: ChartFrameProps<T>) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <Card className={cn("flex flex-col", className)}>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-headline text-label">{title}</h2>
          {subtitle && <p className="mt-0.5 text-subhead text-label-2">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
          {actions}
          <Segmented
            size="sm"
            label="Display as"
            value={view}
            onChange={setView}
            options={[
              { value: "chart", label: <ChartLine className="size-3.5" aria-label="Chart" /> },
              { value: "table", label: <Table2 className="size-3.5" aria-label="Table" /> },
            ]}
          />
        </div>
      </div>
      {legend && legend.length > 0 && view === "chart" && <Legend items={legend} className="mb-3" />}
      <div className={cn("relative min-h-0 flex-1 transition-opacity duration-200", refreshing && "opacity-60")}>
        <AnimatePresence mode="wait" initial={false}>
          {view === "chart" ? (
            <motion.div key="chart" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
              {children}
            </motion.div>
          ) : (
            <motion.div key="table" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} className="-mx-5 max-h-[420px] overflow-y-auto">
              <Table dense columns={table.columns} rows={table.rows} rowKey={table.rowKey} caption={table.caption} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      {footer}
    </Card>
  );
}
