import { useLayoutEffect, useRef, useState } from "react";

/** Tracks an element's content box. Charts render nothing until measured. */
export function useMeasure<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const update = (width: number, height: number) =>
      setSize((prev) => (prev.width === Math.round(width) && prev.height === Math.round(height) ? prev : { width: Math.round(width), height: Math.round(height) }));
    const rect = node.getBoundingClientRect();
    update(rect.width, rect.height);
    const observer = new ResizeObserver(([entry]) => update(entry.contentRect.width, entry.contentRect.height));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return [ref, size] as const;
}
