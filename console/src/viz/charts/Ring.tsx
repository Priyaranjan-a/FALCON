import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { spring } from "@/design/motion";

interface RingProps {
  /** 0–1 */
  value: number;
  size?: number;
  thickness?: number;
  color?: string;
  children?: ReactNode;
  ariaLabel: string;
}

/**
 * Progress ring. The track is a lighter step of the fill's own hue, so the
 * whole ring reads as one meter; the fill draws on with a spring.
 */
export function Ring({ value, size = 88, thickness = 9, color = "var(--accent)", children, ariaLabel }: RingProps) {
  const reduce = useReducedMotion();
  const r = (size - thickness) / 2;
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }} role="img" aria-label={ariaLabel}>
      <svg width={size} height={size} className="absolute inset-0 -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={thickness} style={{ stroke: `color-mix(in srgb, ${color} 18%, transparent)` }} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          strokeWidth={thickness}
          strokeLinecap="round"
          style={{ stroke: color }}
          initial={{ pathLength: reduce ? clamped : 0 }}
          animate={{ pathLength: clamped === 0 ? 0.0001 : clamped }}
          transition={{ ...spring.data, delay: 0.1 }}
        />
      </svg>
      <div className="relative text-center">{children}</div>
    </div>
  );
}
