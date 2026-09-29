import { AnimatePresence, motion, useSpring } from "motion/react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { spring } from "@/design/motion";

interface ChartTooltipProps {
  /** Anchor in container coordinates. */
  x: number;
  y: number;
  visible: boolean;
  containerWidth: number;
  children: ReactNode;
}

const OFFSET = 14;

/**
 * Follows its anchor on a stiff spring and flips sides near the container
 * edge. Pointer-transparent so it never steals hover from the marks.
 */
export function ChartTooltip({ x, y, visible, containerWidth, children }: ChartTooltipProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const left = useSpring(x, spring.follow);
  const top = useSpring(y, spring.follow);
  const wasVisible = useRef(false);

  useLayoutEffect(() => {
    if (ref.current) {
      const r = ref.current.getBoundingClientRect();
      if (r.width !== size.width || r.height !== size.height) setSize({ width: r.width, height: r.height });
    }
  });

  const flip = x + OFFSET + size.width > containerWidth - 4;
  const targetX = flip ? Math.max(4, x - OFFSET - size.width) : x + OFFSET;
  const targetY = Math.max(4, y - size.height / 2);

  useEffect(() => {
    if (visible && !wasVisible.current) {
      left.jump(targetX);
      top.jump(targetY);
    } else {
      left.set(targetX);
      top.set(targetY);
    }
    wasVisible.current = visible;
  }, [visible, targetX, targetY, left, top]);

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          ref={ref}
          role="presentation"
          className="pointer-events-none absolute left-0 top-0 z-20 min-w-[148px] rounded-[10px] bg-elevated px-3 py-2.5 shadow-pop vibrancy"
          style={{ x: left, y: top }}
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.1 } }}
          transition={{ duration: 0.12 }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function TooltipTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-1.5">
      <div className="text-footnote font-semibold text-label">{children}</div>
      {sub && <div className="text-caption text-label-3">{sub}</div>}
    </div>
  );
}

/** Values lead, labels follow; series keyed by a short stroke of their colour. */
export function TooltipRow({ color, label, value, kind = "line" }: { color?: string; label: ReactNode; value: ReactNode; kind?: "line" | "rect" | "none" }) {
  return (
    <div className="flex items-center gap-2 py-[1px] text-footnote">
      {kind !== "none" && color && (
        <span
          aria-hidden
          className="shrink-0"
          style={kind === "line" ? { width: 10, height: 2, borderRadius: 1, background: color } : { width: 8, height: 8, borderRadius: 2, background: color }}
        />
      )}
      <span className="font-semibold tabular text-label">{value}</span>
      <span className="truncate text-label-2">{label}</span>
    </div>
  );
}
