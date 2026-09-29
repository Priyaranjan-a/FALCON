/**
 * The risk vocabulary. Risk bands and time-machine states are statuses, so
 * they use the reserved status colours and always carry an icon and a label.
 */
import {
  CircleCheck,
  CircleDot,
  Clock3,
  FileWarning,
  Flame,
  OctagonX,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/design/components/Surface";
import type { PolicyStatus, RiskBand, RiskRole } from "@/lib/types";
import { status } from "@/viz/core/tokens";

type Tone = "neutral" | "good" | "warning" | "serious" | "critical" | "accent";

export const BAND_ORDER: RiskBand[] = ["critical", "high", "medium", "low", "none"];

export const BANDS: Record<RiskBand, { label: string; tone: Tone; color: string; icon: LucideIcon; summary: string }> = {
  critical: { label: "Critical", tone: "critical", color: status.critical, icon: Flame, summary: "Act now: attackable today, disallowed, or harvestable with data that outlives the horizon." },
  high: { label: "High", tone: "serious", color: status.serious, icon: ShieldAlert, summary: "Migrate in the current planning cycle." },
  medium: { label: "Medium", tone: "warning", color: status.warning, icon: TriangleAlert, summary: "Schedule within the migration programme." },
  low: { label: "Low", tone: "neutral", color: `color-mix(in srgb, ${status.warning} 38%, var(--surface))`, icon: CircleDot, summary: "Track; replace at the next natural change." },
  none: { label: "No quantum risk", tone: "good", color: status.good, icon: ShieldCheck, summary: "Quantum-resistant or post-quantum, and compliant." },
};

export const ROLES: Record<RiskRole, { label: string; summary: string }> = {
  confidentiality: { label: "Confidentiality", summary: "Protects data in transit or at rest: exposed to harvest now, decrypt later." },
  authenticity: { label: "Authenticity", summary: "Signatures and certificates: forgeable once a CRQC exists." },
  integrity: { label: "Integrity", summary: "Hashes, MACs and key derivation: weakened by Grover's algorithm at most." },
  enabling: { label: "Enabling", summary: "Libraries and hardware that decide how fast migration can happen." },
};

export const POLICY_STATUS: Record<PolicyStatus, { label: string; tone: Tone; color: string; icon: LucideIcon }> = {
  approved: { label: "Approved", tone: "good", color: status.good, icon: CircleCheck },
  acceptable: { label: "Acceptable for now", tone: "neutral", color: "var(--label-3)", icon: Clock3 },
  "not-applicable": { label: "Not applicable", tone: "neutral", color: "var(--label-4)", icon: CircleDot },
  transition: { label: "Must transition", tone: "warning", color: status.warning, icon: TriangleAlert },
  "not-approved": { label: "Not approved", tone: "serious", color: status.serious, icon: FileWarning },
  deprecated: { label: "Deprecated", tone: "serious", color: status.serious, icon: TriangleAlert },
  disallowed: { label: "Disallowed", tone: "critical", color: status.critical, icon: OctagonX },
};

/** Time machine: the state of an artefact in a given year. */
export type TimeState = "secure" | "at-risk" | "exposed" | "broken";
export const TIME_STATES: { key: TimeState; label: string; color: string; summary: string }[] = [
  { key: "broken", label: "Broken or disallowed", color: status.critical, summary: "Beyond the planning horizon, or no longer permitted by policy." },
  { key: "exposed", label: "Exposed", color: status.serious, summary: "What it protects outlives the horizon: harvestable now, forgeable later." },
  { key: "at-risk", label: "At risk", color: status.warning, summary: "Quantum-vulnerable or weak, but not yet exposed." },
  { key: "secure", label: "Secure", color: status.good, summary: "Quantum-resistant or post-quantum." },
];

export function stateAt(t: { at_risk: number | null; exposed: number | null; broken: number | null }, year: number): TimeState {
  if (t.broken !== null && year >= t.broken) return "broken";
  if (t.exposed !== null && year >= t.exposed) return "exposed";
  if (t.at_risk !== null && year >= t.at_risk) return "at-risk";
  return "secure";
}

const ink: Record<Tone, string> = {
  neutral: "var(--label-3)",
  accent: "var(--accent)",
  good: status.good,
  warning: status.warning,
  serious: status.serious,
  critical: status.critical,
};

export function RiskBadge({ band, score, className }: { band: RiskBand; score?: number; className?: string }) {
  const meta = BANDS[band];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className} icon={<Icon style={{ color: band === "low" ? status.warning : ink[meta.tone] }} strokeWidth={2.25} />}>
      {meta.label}
      {score !== undefined && band !== "none" && <span className="tabular text-label-2">{score}</span>}
    </Badge>
  );
}

export function PolicyBadge({ value, className }: { value: PolicyStatus; className?: string }) {
  const meta = POLICY_STATUS[value];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className} icon={<Icon style={{ color: ink[meta.tone] }} strokeWidth={2.25} />}>
      {meta.label}
    </Badge>
  );
}

export const FRAMEWORK_ORDER = ["nist-ir-8547", "nist-sp-800-131a", "cnsa-2.0", "eu-pqc-roadmap"] as const;
export const FRAMEWORK_SHORT: Record<(typeof FRAMEWORK_ORDER)[number], string> = {
  "nist-ir-8547": "NIST IR 8547",
  "nist-sp-800-131a": "SP 800-131A",
  "cnsa-2.0": "CNSA 2.0",
  "eu-pqc-roadmap": "EU roadmap",
};

/** 2031.0 (the start of 2031) → "end of 2030", the way deadlines are published. */
export function deadlineLabel(year: number): string {
  const whole = Math.floor(year);
  return Math.abs(year - whole) < 0.02 ? `end of ${whole - 1}` : String(whole);
}
