import { ChevronDown } from "lucide-react";
import { useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "../cn";

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** Provide to make the column sortable. */
  sortValue?: (row: T) => number | string;
  align?: "left" | "right" | "center";
  width?: number | string;
  numeric?: boolean;
  className?: string;
  hideBelow?: "sm" | "md" | "lg";
}

interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  initialSort?: { key: string; direction: "asc" | "desc" };
  caption?: string;
  dense?: boolean;
  className?: string;
  empty?: ReactNode;
  rowLabel?: (row: T) => string;
}

const hide = { sm: "max-sm:hidden", md: "max-md:hidden", lg: "max-lg:hidden" };

export function Table<T>({ columns, rows, rowKey, onRowClick, initialSort, caption, dense, className, empty, rowLabel }: TableProps<T>) {
  const [sort, setSort] = useState(initialSort);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const factor = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = column.sortValue!(a);
      const bv = column.sortValue!(b);
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * factor;
      return String(av).localeCompare(String(bv), undefined, { numeric: true }) * factor;
    });
  }, [rows, columns, sort]);

  const toggle = (key: string) =>
    setSort((prev) => (prev?.key === key ? { key, direction: prev.direction === "asc" ? "desc" : "asc" } : { key, direction: "desc" }));

  const onKey = (e: KeyboardEvent, row: T) => {
    if (onRowClick && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onRowClick(row);
    }
  };

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full border-separate border-spacing-0 text-left">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={active ? (sort!.direction === "asc" ? "ascending" : "descending") : undefined}
                  style={{ width: c.width }}
                  className={cn(
                    "sticky top-0 z-[1] whitespace-nowrap bg-[var(--glass-header)] px-3 text-footnote font-medium text-label-3 hairline-b first:pl-5 last:pr-5",
                    dense ? "h-8" : "h-9",
                    c.align === "right" || c.numeric ? "text-right" : c.align === "center" ? "text-center" : "text-left",
                    c.hideBelow && hide[c.hideBelow],
                  )}
                >
                  {c.sortValue ? (
                    <button
                      type="button"
                      onClick={() => toggle(c.key)}
                      className={cn("inline-flex items-center gap-1 rounded hover:text-label-2", active && "text-label-2")}
                    >
                      {c.header}
                      <ChevronDown
                        className={cn("size-3 transition-transform duration-200", active ? "opacity-100" : "opacity-0", active && sort!.direction === "asc" && "rotate-180")}
                        strokeWidth={2.5}
                      />
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={rowKey(row)}
              tabIndex={onRowClick ? 0 : undefined}
              aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={onRowClick ? (e) => onKey(e, row) : undefined}
              className={cn("group outline-none", onRowClick && "cursor-pointer")}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={cn(
                    "px-3 align-middle text-callout text-label transition-colors duration-100 first:pl-5 last:pr-5",
                    "hairline-b group-last:shadow-none",
                    dense ? "h-10" : "h-[52px]",
                    onRowClick && "group-hover:bg-fill-2 group-focus-visible:bg-accent-tint",
                    (c.align === "right" || c.numeric) && "text-right",
                    c.align === "center" && "text-center",
                    c.numeric && "tabular",
                    c.hideBelow && hide[c.hideBelow],
                    c.className,
                  )}
                >
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && empty}
    </div>
  );
}
