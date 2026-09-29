/**
 * Recently visited pages, for the command palette's "Recent" group, the way
 * Spotlight and VS Code surface what you were just looking at. Per device.
 */
import { useSyncExternalStore } from "react";

export interface Recent {
  path: string;
  title: string;
  at: number;
}

const KEY = "falcon.recents";
const MAX = 8;
const listeners = new Set<() => void>();

function read(): Recent[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((r) => r && typeof r.path === "string" && typeof r.title === "string").slice(0, MAX) : [];
  } catch {
    return [];
  }
}

let recents = read();

export function remember(path: string, title: string): void {
  if (!title || path === "/") return;
  recents = [{ path, title, at: Date.now() }, ...recents.filter((r) => r.path !== path)].slice(0, MAX);
  try {
    localStorage.setItem(KEY, JSON.stringify(recents));
  } catch {
    /* kept for this page view */
  }
  listeners.forEach((l) => l());
}

export function useRecents(): Recent[] {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => recents,
  );
}
