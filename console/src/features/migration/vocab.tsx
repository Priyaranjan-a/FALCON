import { ArrowUpCircle, Cpu, FileBadge, Power, RefreshCw, Replace, ShieldCheck, type LucideIcon } from "lucide-react";
import type { Recommendation, WaveKey } from "@/lib/types";
import { series } from "@/viz/core/tokens";

/* Waves are an ordered set of categories: categorical slots in fixed order. */
export const WAVES: Record<WaveKey, { label: string; short: string; color: string }> = {
  "fix-now": { label: "Fix what is broken today", short: "Fix now", color: series[7] },
  "stop-harvest": { label: "Stop the harvest", short: "Stop the harvest", color: series[1] },
  "long-lead": { label: "Long lead times", short: "Long lead", color: series[6] },
  "before-2030": { label: "Before the 2030 deprecation", short: "Before 2030", color: series[0] },
  complete: { label: "Complete the transition", short: "Complete", color: series[2] },
};
export const WAVE_ORDER: WaveKey[] = ["fix-now", "stop-harvest", "long-lead", "before-2030", "complete"];

export const ACTIONS: Record<Recommendation["action"], { label: string; icon: LucideIcon }> = {
  replace: { label: "Replace", icon: Replace },
  upgrade: { label: "Upgrade", icon: ArrowUpCircle },
  enable: { label: "Enable", icon: Power },
  reissue: { label: "Re-issue", icon: FileBadge },
  refresh: { label: "Refresh hardware", icon: Cpu },
  strengthen: { label: "Strengthen", icon: RefreshCw },
  keep: { label: "Keep", icon: ShieldCheck },
};

export function formatBytesShort(n: number): string {
  if (Math.abs(n) < 1024) return `${n} B`;
  return `${(n / 1024).toFixed(Math.abs(n) < 10240 ? 1 : 0)} KB`;
}

export function formatMicros(us: number): string {
  if (us < 1000) return `${us < 10 ? us.toFixed(1) : Math.round(us)} µs`;
  if (us < 1_000_000) return `${(us / 1000).toFixed(us < 10_000 ? 2 : 1)} ms`;
  return `${(us / 1_000_000).toFixed(2)} s`;
}
