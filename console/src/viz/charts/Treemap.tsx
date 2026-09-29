import { hierarchy, treemap, treemapSquarify, type HierarchyRectangularNode } from "d3-hierarchy";
import { useMemo, useState } from "react";
import { ChartTooltip, TooltipRow, TooltipTitle } from "../core/ChartTooltip";
import { ramp } from "../core/tokens";
import { useMeasure } from "../core/useMeasure";

export interface TreemapLeaf {
  /** Path-like key; the first segment becomes the group. */
  key: string;
  /** Area. */
  size: number;
  /** 0–1: how much of the cell is filled (e.g. files scanned). */
  progress: number;
  /** Colour step 0–5: 0 is neutral ("nothing found"), 1–5 walk the ordinal ramp. */
  intensity: number;
  label?: string;
  tooltip: { title: string; sub?: string; rows: { label: string; value: string }[] };
}

interface Node {
  name: string;
  leaf?: TreemapLeaf;
  children?: Node[];
}

const GROUP_HEADER = 18;
const GAP = 2;
/* SVG geometry animates as CSS properties (x, y, width, height) so cells glide on re-layout and fill smoothly. */
const GEOMETRY = "motion-safe:[transition-property:x,y,width,height] motion-safe:duration-500";
const EASE = "cubic-bezier(0.22, 1, 0.36, 1)";

/** Fill for an intensity step; step 0 is the neutral "scanned, nothing found". */
export function intensityColor(step: number): string {
  return step <= 0 ? "var(--fill-hover)" : ramp[Math.min(4, step - 1)];
}

/** Text colour that stays legible on a filled cell of the given step, in either appearance. */
function inkOn(step: number): { primary: string; secondary: string } {
  if (step <= 0) return { primary: "var(--label)", secondary: "var(--label-2)" };
  const ink = `var(--on-ramp-${Math.min(5, step)})`;
  return { primary: ink, secondary: ink };
}

/** Cells not yet analysed: a faint track, clearly lighter than "nothing found". */
export const PENDING_FILL = "var(--fill-2)";

function build(leaves: TreemapLeaf[]): Node {
  const groups = new Map<string, Node>();
  for (const leaf of leaves) {
    const [head, ...rest] = leaf.key === "." ? ["(root)"] : leaf.key.split("/");
    const group = groups.get(head) ?? { name: head, children: [] };
    groups.set(head, group);
    group.children!.push({ name: rest.join("/") || (leaf.key === "." ? "(root)" : `${head}/`), leaf });
  }
  return { name: "root", children: [...groups.values()] };
}

/**
 * Squarified treemap of where things are. Each cell fills from the bottom as
 * its progress advances, and its colour reports intensity, so a live scan
 * reads as the estate lighting up. Groups carry a caption strip; cells are
 * separated by 2px surface gaps.
 */
export function Treemap({ leaves, height = 300, ariaLabel }: { leaves: TreemapLeaf[]; height?: number; ariaLabel: string }) {
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const [hover, setHover] = useState<{ key: string; x: number; y: number } | null>(null);

  const layout = useMemo(() => {
    if (!width || leaves.length === 0) return null;
    const root = hierarchy<Node>(build(leaves))
      .sum((d) => (d.leaf ? Math.max(d.leaf.size, 1) : 0))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    return treemap<Node>()
      .tile(treemapSquarify.ratio(1.3))
      .size([width, height])
      .paddingInner(GAP)
      .paddingTop((d) => (d.depth === 1 ? GROUP_HEADER : 0))
      .round(true)(root);
  }, [leaves, width, height]);

  const groups = (layout?.children ?? []) as HierarchyRectangularNode<Node>[];
  const cells = (layout?.leaves() ?? []).filter((d) => d.data.leaf) as HierarchyRectangularNode<Node>[];
  const hovered = hover ? cells.find((c) => c.data.leaf!.key === hover.key)?.data.leaf : undefined;

  return (
    <div ref={ref} className="relative w-full" style={{ height }} onPointerLeave={() => setHover(null)}>
      {layout && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block overflow-visible">
          {groups.map((g) => {
            const w = g.x1 - g.x0;
            return (
              <text
                key={g.data.name}
                className="text-caption font-semibold motion-safe:transition-transform motion-safe:duration-500"
                style={{ fill: "var(--label-2)", transform: `translate(${g.x0 + 1}px, ${g.y0 + 12}px)`, transitionTimingFunction: EASE }}
              >
                {w > 44 ? truncate(g.data.name, Math.floor(w / 6.4)) : ""}
              </text>
            );
          })}
          {cells.map((c) => {
            const leaf = c.data.leaf!;
            const w = Math.max(0, c.x1 - c.x0);
            const h = Math.max(0, c.y1 - c.y0);
            const filled = h * Math.max(0, Math.min(1, leaf.progress));
            const active = hover?.key === leaf.key;
            const clip = `tm-${leaf.key.replace(/[^\w-]/g, "_")}`;
            const showLabel = w > 54 && h > 30;
            // Text sits at the top of the cell, over the fill only once the cell is full.
            const ink = leaf.progress >= 0.99 ? inkOn(leaf.intensity) : inkOn(0);
            const box = { x: c.x0, y: c.y0, width: w, height: h };
            return (
              <g
                key={leaf.key}
                onPointerMove={(e) => {
                  const bounds = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                  setHover({ key: leaf.key, x: e.clientX - bounds.left, y: e.clientY - bounds.top });
                }}
              >
                <clipPath id={clip}>
                  <rect rx={4} className={GEOMETRY} style={{ ...box, transitionTimingFunction: EASE }} />
                </clipPath>
                <g clipPath={`url(#${clip})`}>
                  <rect className={GEOMETRY} style={{ ...box, fill: PENDING_FILL, opacity: 0.6, transitionTimingFunction: EASE }} />
                  <rect
                    className="motion-safe:[transition-property:x,y,width,height,fill] motion-safe:duration-500"
                    style={{ x: c.x0, y: c.y1 - filled, width: w, height: filled, fill: intensityColor(leaf.intensity), transitionTimingFunction: EASE }}
                  />
                </g>
                {active && <rect x={c.x0 + 0.75} y={c.y0 + 0.75} width={Math.max(0, w - 1.5)} height={Math.max(0, h - 1.5)} rx={3.5} fill="none" strokeWidth={1.5} style={{ stroke: "var(--label)" }} />}
                {showLabel && (
                  <text
                    className="pointer-events-none text-caption font-medium motion-safe:transition-transform motion-safe:duration-500"
                    style={{ transform: `translate(${c.x0 + 7}px, ${c.y0 + 16}px)`, transitionTimingFunction: EASE }}
                  >
                    <tspan style={{ fill: ink.primary }}>{truncate(c.data.name, Math.floor((w - 12) / 6.2))}</tspan>
                    {leaf.label && h > 44 && (
                      <tspan x={0} dy={15} className="tabular" style={{ fill: ink.secondary, fillOpacity: ink.secondary === ink.primary ? 0.8 : 1 }}>
                        {leaf.label}
                      </tspan>
                    )}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
      <ChartTooltip visible={!!hovered} x={hover?.x ?? 0} y={hover?.y ?? 0} containerWidth={width}>
        {hovered && (
          <>
            <TooltipTitle sub={hovered.tooltip.sub}>{hovered.tooltip.title}</TooltipTitle>
            {hovered.tooltip.rows.map((r) => (
              <TooltipRow key={r.label} kind="none" label={r.label} value={r.value} />
            ))}
          </>
        )}
      </ChartTooltip>
    </div>
  );
}

function truncate(text: string, max: number): string {
  if (max <= 1) return "";
  return text.length > max ? `${text.slice(0, Math.max(1, max - 1))}…` : text;
}
