import { useSyncExternalStore } from "react";

export type Appearance = "system" | "light" | "dark";

const KEY = "falcon.appearance";
const listeners = new Set<() => void>();

function read(): Appearance {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

let current: Appearance = read();

export function setAppearance(value: Appearance): void {
  current = value;
  try {
    if (value === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, value);
  } catch {
    /* storage unavailable: the choice lasts for this page view */
  }
  const root = document.documentElement;
  // Suppress transitions for one frame so every surface switches together.
  root.classList.add("appearance-switching");
  if (value === "system") delete root.dataset.theme;
  else root.dataset.theme = value;
  requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("appearance-switching")));
  listeners.forEach((l) => l());
}

export function useAppearance(): Appearance {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
  );
}

/* ------------------------------------------------ accent and transparency */

export type Accent = "blue" | "purple" | "pink" | "red" | "orange" | "green" | "graphite";
export const ACCENTS: { value: Accent; label: string; swatch: string }[] = [
  { value: "blue", label: "Blue", swatch: "#0a84ff" },
  { value: "purple", label: "Purple", swatch: "#bf5af2" },
  { value: "pink", label: "Pink", swatch: "#ff375f" },
  { value: "red", label: "Red", swatch: "#ff453a" },
  { value: "orange", label: "Orange", swatch: "#ff9f0a" },
  { value: "green", label: "Green", swatch: "#30d158" },
  { value: "graphite", label: "Graphite", swatch: "#98989d" },
];

function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* the choice lasts for this page view */
  }
}

let accent: Accent = (ACCENTS.find((a) => a.value === readLocal("falcon.accent"))?.value ?? "blue") as Accent;
let reducedTransparency = readLocal("falcon.transparency") === "reduced";

export function setAccent(value: Accent): void {
  accent = value;
  writeLocal("falcon.accent", value === "blue" ? null : value);
  const root = document.documentElement;
  if (value === "blue") delete root.dataset.accent;
  else root.dataset.accent = value;
  listeners.forEach((l) => l());
}

export function setReducedTransparency(on: boolean): void {
  reducedTransparency = on;
  writeLocal("falcon.transparency", on ? "reduced" : null);
  const root = document.documentElement;
  if (on) root.dataset.transparency = "reduced";
  else delete root.dataset.transparency;
  listeners.forEach((l) => l());
}

export function useAccent(): Accent {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => accent,
  );
}

export function useReducedTransparency(): boolean {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => reducedTransparency,
  );
}
