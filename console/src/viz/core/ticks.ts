/** Evenly spaced integer ticks whose density suits the available width. */
export function yearTicks(start: number, end: number, width: number, minSpacing = 64): number[] {
  const span = end - start;
  const steps = [1, 2, 5, 10, 20];
  const step = steps.find((s) => (span / s) * minSpacing <= width) ?? 20;
  const first = Math.ceil(start / step) * step;
  const out: number[] = [];
  for (let t = first; t <= end + 1e-9; t += step) out.push(t);
  return out;
}

/** Round a domain maximum up to a clean value (1, 2, 2.5, 5 × 10^n). */
export function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const base = 10 ** exponent;
  for (const m of [1, 2, 2.5, 5, 10]) if (m * base >= value) return m * base;
  return 10 * base;
}

/** A clean step (1, 2, 2.5, 5 × 10^n) giving roughly `count` intervals up to `max`. */
export function niceStep(max: number, count = 5): number {
  return niceMax(max / count);
}

/** Smallest multiple of a clean step that covers `value`. */
export function niceDomain(value: number, count = 6): number {
  const step = niceStep(value, count);
  return Math.max(step, Math.ceil(value / step - 1e-9) * step);
}

export function linearTicks(max: number, count = 5): number[] {
  const step = niceStep(max, count);
  const out: number[] = [];
  for (let t = 0; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}
