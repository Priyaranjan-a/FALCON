/**
 * Page code is split per route, which keeps the first load small. To keep
 * navigation instant as well, every page's chunk is fetched in the background
 * once the console is idle, one at a time so it never competes with the
 * user's own requests.
 */
type Loader = () => Promise<unknown>;

const loaders: Loader[] = [];

export function registerPage(load: Loader): void {
  loaders.push(load);
}

type IdleWindow = Window & {
  requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
  cancelIdleCallback?: (id: number) => void;
};

export function prefetchPages(): () => void {
  const w = window as IdleWindow;
  // Respect metered or slow connections.
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
  if (connection?.saveData || connection?.effectiveType === "2g") return () => {};

  let cancelled = false;
  let handle = 0;
  const queue = [...loaders];
  const schedule = (fn: () => void) =>
    w.requestIdleCallback ? w.requestIdleCallback(fn, { timeout: 2000 }) : window.setTimeout(fn, 200);
  const next = () => {
    if (cancelled) return;
    const load = queue.shift();
    if (!load) return;
    load().catch(() => undefined).finally(() => {
      handle = schedule(next);
    });
  };
  handle = window.setTimeout(() => (handle = schedule(next)), 1200);
  return () => {
    cancelled = true;
    window.clearTimeout(handle);
    w.cancelIdleCallback?.(handle);
  };
}
