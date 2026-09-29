import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

const easeOutCubic = (t: number) => 1 - (1 - t) ** 3;

interface TweenOptions {
  duration?: number;
  /** Value new entries grow from; "target" appears in place and only animates later changes. */
  from?: number | "target";
  delay?: number;
}

/**
 * Tweens a numeric array toward its target on every change, starting from
 * whatever is currently displayed, so an interrupted transition stays
 * continuous. Lengths may change; new entries grow from `from`.
 */
export function useTweenedArray(target: number[], { duration = 520, from = 0, delay = 0 }: TweenOptions = {}): number[] {
  const reduce = useReducedMotion();
  const origin = (i: number) => (from === "target" ? target[i] : from);
  const [value, setValue] = useState<number[]>(() => (reduce ? target : target.map((_, i) => origin(i))));
  const current = useRef(value);
  current.current = value;
  const key = target.join(",");

  useEffect(() => {
    if (reduce) {
      setValue(target);
      return;
    }
    const start = current.current;
    const begin = target.map((_, i) => start[i] ?? origin(i));
    if (begin.every((b, i) => b === target[i])) return;
    let frame = 0;
    let t0 = 0;
    const step = (now: number) => {
      if (!t0) t0 = now + delay;
      const t = Math.min(1, Math.max(0, (now - t0) / duration));
      const k = easeOutCubic(t);
      setValue(target.map((v, i) => begin[i] + (v - begin[i]) * k));
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // `key` stands in for `target`: a new array with the same content must not restart the tween.
  }, [key, reduce, duration, delay]);

  return value;
}

export function useTweenedNumber(target: number, options?: TweenOptions): number {
  return useTweenedArray([target], options)[0];
}
