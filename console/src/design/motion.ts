import type { Transition } from "motion/react";

/**
 * Motion vocabulary. Springs, not durations, drive anything the user touches:
 * they stay continuous when interrupted, which is what makes UI feel physical.
 */
export const spring = {
  /** Controls: toggles, segmented thumbs, presses. */
  snappy: { type: "spring", stiffness: 520, damping: 40, mass: 0.8 },
  /** Panels, sheets, popovers. */
  smooth: { type: "spring", stiffness: 340, damping: 34, mass: 1 },
  /** Data: bars growing, markers settling. */
  data: { type: "spring", stiffness: 180, damping: 26, mass: 1 },
  /** Tooltips following the pointer. */
  follow: { type: "spring", stiffness: 700, damping: 50, mass: 0.6 },
} satisfies Record<string, Transition>;

export const ease = {
  out: [0.22, 1, 0.36, 1] as const,
  standard: [0.25, 0.1, 0.25, 1] as const,
};

export const fade = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: 0.28, ease: ease.out },
};
