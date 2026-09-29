/**
 * Page-level loading marks. A component that stands in for a page still
 * loading (the page skeleton) marks itself here, so the falcon flies for code
 * as well as for data.
 */
import { useEffect, useSyncExternalStore } from "react";

let count = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function useLoadingMark(active = true): void {
  useEffect(() => {
    if (!active) return;
    count += 1;
    emit();
    return () => {
      count -= 1;
      emit();
    };
  }, [active]);
}

export function usePageLoading(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => count > 0,
  );
}
