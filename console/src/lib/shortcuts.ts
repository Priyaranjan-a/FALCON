/**
 * Keyboard shortcuts: one registry, customisable per device.
 *
 * A binding is either a chord ("Mod+K", "Mod+Shift+L", "Shift+?") or a
 * sequence of plain keys ("G R": press G, then R). "Mod" is ⌘ on a Mac and
 * Ctrl elsewhere. Plain-key shortcuts never fire while typing in a field, and
 * can be switched off as a group, as Gmail allows.
 */
import { useSyncExternalStore } from "react";

export const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

export type ShortcutGroup = "General" | "Navigate" | "Appearance";

export interface ShortcutDef {
  id: string;
  label: string;
  group: ShortcutGroup;
  keys: string; // default binding
  path?: string; // navigation target
}

export const SHORTCUTS: ShortcutDef[] = [
  { id: "palette", label: "Search and commands", group: "General", keys: "Mod+K" },
  { id: "shortcuts", label: "Show keyboard shortcuts", group: "General", keys: "Shift+?" },
  { id: "sidebar", label: "Show or hide the sidebar", group: "General", keys: "Mod+\\" },
  { id: "find", label: "Search this page", group: "General", keys: "/" },
  { id: "exports", label: "Show exports and downloads", group: "General", keys: "G D" },
  { id: "sounds", label: "Turn interface sounds on or off", group: "General", keys: "M" },
  { id: "go.overview", label: "Overview", group: "Navigate", keys: "G O", path: "/" },
  { id: "go.systems", label: "Systems", group: "Navigate", keys: "G S", path: "/systems" },
  { id: "go.horizon", label: "Threat Horizon", group: "Navigate", keys: "G H", path: "/horizon" },
  { id: "go.inventory", label: "Inventory", group: "Navigate", keys: "G I", path: "/inventory" },
  { id: "go.scans", label: "Scans", group: "Navigate", keys: "G N", path: "/scans" },
  { id: "go.risk", label: "Quantum Risk", group: "Navigate", keys: "G R", path: "/risk" },
  { id: "go.time", label: "Time Machine", group: "Navigate", keys: "G T", path: "/time-machine" },
  { id: "go.compliance", label: "Compliance", group: "Navigate", keys: "G C", path: "/compliance" },
  { id: "go.migration", label: "Migration Plan", group: "Navigate", keys: "G M", path: "/migration" },
  { id: "go.blast", label: "Blast Radius", group: "Navigate", keys: "G B", path: "/blast-radius" },
  { id: "go.whatif", label: "What-if", group: "Navigate", keys: "G W", path: "/simulator" },
  { id: "go.lab", label: "Benchmark Lab", group: "Navigate", keys: "G L", path: "/lab" },
  { id: "go.reports", label: "Reports", group: "Navigate", keys: "G E", path: "/reports" },
  { id: "go.brief", label: "Executive Brief", group: "Navigate", keys: "G X", path: "/brief" },
  { id: "go.settings", label: "Settings", group: "Navigate", keys: "Mod+,", path: "/settings" },
  { id: "appearance.light", label: "Light appearance", group: "Appearance", keys: "Mod+Shift+1" },
  { id: "appearance.dark", label: "Dark appearance", group: "Appearance", keys: "Mod+Shift+2" },
  { id: "appearance.system", label: "Match the system", group: "Appearance", keys: "Mod+Shift+0" },
];

interface Prefs {
  bindings: Record<string, string>; // id -> keys ("" disables)
  singleKey: boolean;
}

const KEY = "falcon.shortcuts";
const listeners = new Set<() => void>();

function read(): Prefs {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (raw && typeof raw === "object") return { bindings: raw.bindings ?? {}, singleKey: raw.singleKey !== false };
  } catch {
    /* defaults */
  }
  return { bindings: {}, singleKey: true };
}

let prefs = read();

function save(next: Prefs) {
  prefs = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* the choice lasts for this page view */
  }
  listeners.forEach((l) => l());
}

export function useShortcutPrefs(): Prefs {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => prefs,
  );
}

export function bindingFor(id: string, p: Prefs = prefs): string {
  const custom = p.bindings[id];
  return custom !== undefined ? custom : (SHORTCUTS.find((s) => s.id === id)?.keys ?? "");
}

export function setBinding(id: string, keys: string): void {
  const def = SHORTCUTS.find((s) => s.id === id);
  const bindings = { ...prefs.bindings };
  if (def && keys === def.keys) delete bindings[id];
  else bindings[id] = keys;
  save({ ...prefs, bindings });
}

export function resetShortcuts(): void {
  save({ bindings: {}, singleKey: prefs.singleKey });
}

export function setSingleKeyShortcuts(on: boolean): void {
  save({ ...prefs, singleKey: on });
}

/** Another shortcut already using these keys, if any. */
export function conflictFor(id: string, keys: string): ShortcutDef | undefined {
  if (!keys) return undefined;
  return SHORTCUTS.find((s) => s.id !== id && bindingFor(s.id) === keys);
}

export function isChord(keys: string): boolean {
  return /(^|\+)(Mod|Ctrl|Alt)\+/.test(keys) || keys.startsWith("Mod+") || keys.startsWith("Alt+");
}

/* ----------------------------------------------------------- key names */

const NAMES: Record<string, string> = { " ": "Space", Escape: "Esc", ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→" };

/** The canonical name of a key press: "Mod+Shift+E", "Shift+?", "G". */
export function eventKeys(e: KeyboardEvent): string | null {
  if (["Shift", "Control", "Alt", "Meta", "CapsLock", "Tab"].includes(e.key)) return null;
  const mod = isMac ? e.metaKey : e.ctrlKey;
  let key = NAMES[e.key] ?? e.key;
  // Digits with Shift report symbols on most layouts; name them by their key code.
  if (e.code.startsWith("Digit") && (e.shiftKey || mod)) key = e.code.slice(5);
  if (key.length === 1) key = key.toUpperCase();
  const parts: string[] = [];
  if (mod) parts.push("Mod");
  if (e.altKey) parts.push("Alt");
  if (e.shiftKey && (mod || e.altKey || !/^[A-Z]$/.test(key) || key === "?")) parts.push("Shift");
  parts.push(key);
  return parts.join("+");
}

/** Display form: ["⌘", "K"] on a Mac, ["Ctrl", "K"] elsewhere; sequences as ["G", "then", "R"]. */
export function displayKeys(keys: string): string[] {
  if (!keys) return [];
  if (keys.includes(" ") && !keys.includes("+")) return keys.split(" ").flatMap((k, i) => (i ? ["then", k] : [k]));
  return keys.split("+").map((k) => (k === "Mod" ? (isMac ? "⌘" : "Ctrl") : k === "Shift" ? (isMac ? "⇧" : "Shift") : k === "Alt" ? (isMac ? "⌥" : "Alt") : k));
}
