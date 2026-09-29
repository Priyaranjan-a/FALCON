/**
 * Colour roles for charts. Values are CSS custom properties defined in
 * design/tokens.css, so every chart switches appearance with the page.
 * Apply them through `style` (presentation attributes ignore var()).
 */
export const series = [
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
  "var(--series-4)",
  "var(--series-5)",
  "var(--series-6)",
  "var(--series-7)",
  "var(--series-8)",
] as const;

/** Ordinal ramp, low → high rank (flips anchor in dark appearance). */
export const ramp = ["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)", "var(--ramp-4)", "var(--ramp-5)"] as const;

export const status = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  serious: "var(--status-serious)",
  critical: "var(--status-critical)",
} as const;

export const chrome = {
  grid: "var(--chart-grid)",
  axis: "var(--chart-axis)",
  ink: "var(--chart-ink)",
  label: "var(--label)",
  label2: "var(--label-2)",
  surface: "var(--surface)",
  zone: "var(--chart-zone)",
} as const;

/** Mark specification shared by every chart. */
export const marks = {
  barMax: 24,
  cornerRadius: 4,
  gap: 2,
  line: 2,
  dotRadius: 4,
  ring: 2,
  hitMin: 24,
  areaOpacity: 0.1,
} as const;

/** Rounded-end horizontal bar: square at the baseline, 4px radius at the data end. */
export function barPathH(x: number, y: number, width: number, height: number, radius = marks.cornerRadius): string {
  if (width <= 0) return "";
  const r = Math.min(radius, width, height / 2);
  return `M${x},${y}h${width - r}a${r},${r} 0 0 1 ${r},${r}v${height - 2 * r}a${r},${r} 0 0 1 ${-r},${r}h${-(width - r)}z`;
}

/** Rounded-end vertical bar anchored at the baseline (bottom). */
export function barPathV(x: number, baseline: number, width: number, height: number, radius = marks.cornerRadius): string {
  if (height <= 0) return "";
  const r = Math.min(radius, height, width / 2);
  return `M${x},${baseline}v${-(height - r)}a${r},${r} 0 0 1 ${r},${-r}h${width - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${height - r}z`;
}
