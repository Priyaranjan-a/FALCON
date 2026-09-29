/**
 * The discovery vocabulary: how every artefact class, quantum and classical
 * status, source type and scan state is named, drawn and coloured. Status
 * colours carry meaning only (never identity) and always travel with an icon
 * and a label.
 */
import {
  Binary,
  CircleCheck,
  CircleDashed,
  CircleSlash2,
  CircleX,
  Clock3,
  Cloud,
  Container,
  Cpu,
  FileArchive,
  FileBadge,
  FolderOpen,
  GitBranch,
  Globe,
  KeyRound,
  Network,
  OctagonX,
  Package,
  PackageSearch,
  ShieldAlert,
  ShieldCheck,
  ShieldPlus,
  ShieldQuestion,
  TriangleAlert,
  Atom,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/design/cn";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { Badge } from "@/design/components/Surface";
import type { ArtefactKind, ClassicalStatus, QuantumStatus, ScanStatus, SourceKind } from "@/lib/types";
import { status } from "@/viz/core/tokens";

type Tone = "neutral" | "accent" | "good" | "warning" | "serious" | "critical";

interface StatusMeta {
  label: string;
  short: string;
  tone: Tone;
  color: string;
  icon: LucideIcon;
  summary: string;
}

/* The safe statuses share the good hue in three steps, so the meter reads
   "red → amber → grey → green" while each safe class stays distinguishable. */
const goodStep = (share: number) => `color-mix(in srgb, ${status.good} ${share}%, var(--surface))`;

export const QUANTUM_ORDER: QuantumStatus[] = ["vulnerable", "weakened", "unknown", "resistant", "hybrid", "pqc"];

export const QUANTUM: Record<QuantumStatus, StatusMeta> = {
  vulnerable: {
    label: "Quantum-vulnerable",
    short: "Vulnerable",
    tone: "critical",
    color: status.critical,
    icon: ShieldAlert,
    summary: "Broken outright by Shor’s algorithm on a cryptographically relevant quantum computer.",
  },
  weakened: {
    label: "Weakened",
    short: "Weakened",
    tone: "warning",
    color: status.warning,
    icon: TriangleAlert,
    summary: "Grover’s algorithm halves its effective strength below a safe margin.",
  },
  unknown: {
    label: "Not assessed",
    short: "Not assessed",
    tone: "neutral",
    color: "var(--label-4)",
    icon: ShieldQuestion,
    summary: "FALCON could not determine the parameters needed to assess it.",
  },
  resistant: {
    label: "Quantum-resistant",
    short: "Resistant",
    tone: "good",
    color: goodStep(45),
    icon: ShieldCheck,
    summary: "Symmetric or hash strength that keeps a safe margin against Grover’s algorithm.",
  },
  hybrid: {
    label: "Hybrid post-quantum",
    short: "Hybrid",
    tone: "good",
    color: goodStep(72),
    icon: ShieldPlus,
    summary: "Combines a classical and a post-quantum algorithm: safe if either holds.",
  },
  pqc: {
    label: "Post-quantum",
    short: "Post-quantum",
    tone: "good",
    color: status.good,
    icon: Atom,
    summary: "A NIST-standardised post-quantum algorithm (FIPS 203, 204 or 205).",
  },
};

export const CLASSICAL_ORDER: ClassicalStatus[] = ["broken", "weak", "legacy", "acceptable", "strong", "unknown"];

export const CLASSICAL: Record<ClassicalStatus, StatusMeta> = {
  broken: { label: "Broken", short: "Broken", tone: "critical", color: status.critical, icon: OctagonX, summary: "Practically attackable today, without a quantum computer." },
  weak: { label: "Weak", short: "Weak", tone: "serious", color: status.serious, icon: TriangleAlert, summary: "Below today’s minimum strength (SP 800-131A)." },
  legacy: { label: "Legacy", short: "Legacy", tone: "warning", color: status.warning, icon: Clock3, summary: "Permitted for existing data only; do not use for new protection." },
  acceptable: { label: "Acceptable", short: "Acceptable", tone: "neutral", color: "var(--label-3)", icon: CircleCheck, summary: "Meets today’s minimum strength." },
  strong: { label: "Strong", short: "Strong", tone: "good", color: status.good, icon: ShieldCheck, summary: "Meets or exceeds current recommendations." },
  unknown: { label: "Not assessed", short: "Not assessed", tone: "neutral", color: "var(--label-4)", icon: ShieldQuestion, summary: "Not assessed." },
};

export const KIND_ORDER: ArtefactKind[] = ["algorithm", "key", "certificate", "protocol", "library", "hardware", "cloud_service"];

/** Classes whose risk is a quantum status; libraries and hardware are assessed differently. */
export const ASSESSED: ArtefactKind[] = ["algorithm", "key", "certificate", "protocol", "cloud_service"];

export const KINDS: Record<ArtefactKind, { label: string; singular: string; icon: LucideIcon; summary: string }> = {
  algorithm: { label: "Algorithms", singular: "Algorithm", icon: Binary, summary: "Ciphers, hashes, signatures and key exchange in code and configuration" },
  key: { label: "Keys", singular: "Key", icon: KeyRound, summary: "Public and private keys, keystores and JWKs (secrets never stored)" },
  certificate: { label: "Certificates", singular: "Certificate", icon: FileBadge, summary: "X.509 certificates and signing requests" },
  protocol: { label: "Protocols", singular: "Protocol", icon: Network, summary: "TLS, SSH and IPsec versions in use" },
  library: { label: "Libraries", singular: "Library", icon: Package, summary: "Cryptographic libraries and toolkits, with versions" },
  hardware: { label: "Hardware", singular: "Hardware module", icon: Cpu, summary: "HSMs, TPMs and PKCS#11 modules" },
  cloud_service: { label: "Cloud services", singular: "Cloud service", icon: Cloud, summary: "Cloud KMS keys and managed certificates" },
};

export const SOURCE_KINDS: Record<SourceKind, { label: string; icon: LucideIcon; summary: string; placeholder?: string }> = {
  directory: { label: "Folder", icon: FolderOpen, summary: "A source tree, build output or configuration folder on this machine.", placeholder: "C:\\src\\payments or /srv/app" },
  archive: { label: "Archive", icon: FileArchive, summary: "A .zip, .tar, .tar.gz or .jar of a codebase or release." },
  git: { label: "Git repository", icon: GitBranch, summary: "Cloned shallowly over HTTPS or SSH, hooks disabled.", placeholder: "https://github.com/org/service.git" },
  "image-archive": { label: "Image tarball", icon: Container, summary: "A container image saved with docker save or podman save." },
  "image-registry": { label: "Registry image", icon: PackageSearch, summary: "Pulled layer by layer from an OCI registry.", placeholder: "registry-1.docker.io/library/nginx:1.27" },
  endpoint: { label: "TLS endpoints", icon: Globe, summary: "Live servers probed with a post-quantum TLS 1.3 handshake.", placeholder: "portal.gov.example\n10.20.0.14:8443" },
};

export const SCAN_STATUS: Record<ScanStatus, { label: string; tone: Tone; icon: LucideIcon }> = {
  queued: { label: "Queued", tone: "neutral", icon: CircleDashed },
  running: { label: "Scanning", tone: "accent", icon: CircleDashed },
  succeeded: { label: "Completed", tone: "good", icon: CircleCheck },
  failed: { label: "Failed", tone: "critical", icon: CircleX },
  cancelled: { label: "Cancelled", tone: "neutral", icon: CircleSlash2 },
};

const toneInk: Record<Tone, string> = {
  neutral: "var(--label-3)",
  accent: "var(--accent)",
  good: status.good,
  warning: status.warning,
  serious: status.serious,
  critical: status.critical,
};

export function QuantumBadge({ value, short, className }: { value: QuantumStatus | null | undefined; short?: boolean; className?: string }) {
  const meta = QUANTUM[value ?? "unknown"];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className} icon={<Icon style={{ color: meta.tone === "good" ? status.good : meta.color }} strokeWidth={2.25} />}>
      {short ? meta.short : meta.label}
    </Badge>
  );
}

export function ClassicalBadge({ value, className }: { value: ClassicalStatus | null | undefined; className?: string }) {
  const meta = CLASSICAL[value ?? "unknown"];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.tone} className={className} icon={<Icon style={{ color: toneInk[meta.tone] }} strokeWidth={2.25} />}>
      {meta.label}
    </Badge>
  );
}

export function ScanStatusBadge({ status: value, className }: { status: ScanStatus; className?: string }) {
  const meta = SCAN_STATUS[value];
  const Icon = meta.icon;
  return (
    <Badge
      tone={meta.tone}
      className={className}
      icon={value === "running" ? <ActivityIndicator size={12} label="Scanning" /> : <Icon style={{ color: toneInk[meta.tone] }} strokeWidth={2.25} />}
    >
      {meta.label}
    </Badge>
  );
}

/** A class glyph on a quiet tile: identity by shape, not by colour. */
export function KindGlyph({ kind, size = 28, className }: { kind: ArtefactKind; size?: number; className?: string }) {
  const Icon = KINDS[kind].icon;
  return (
    <span
      aria-hidden
      className={cn("inline-grid shrink-0 place-items-center rounded-[8px] bg-fill-2 text-label-2", className)}
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.28) }}
    >
      <Icon style={{ width: size * 0.55, height: size * 0.55 }} strokeWidth={1.8} />
    </span>
  );
}

export function SourceGlyph({ kind, size = 32, className }: { kind: SourceKind; size?: number; className?: string }) {
  const Icon = SOURCE_KINDS[kind].icon;
  return (
    <span
      aria-hidden
      className={cn("inline-grid shrink-0 place-items-center bg-accent-tint text-accent", className)}
      style={{ width: size, height: size, borderRadius: Math.round(size * 0.28) }}
    >
      <Icon style={{ width: size * 0.5, height: size * 0.5 }} strokeWidth={1.9} />
    </span>
  );
}

const byteUnits = ["bytes", "KB", "MB", "GB", "TB"];

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} ${bytes === 1 ? "byte" : "bytes"}`;
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < byteUnits.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${byteUnits[unit]}`;
}

export function formatDuration(seconds: number): string {
  if (seconds < 1) return `${Math.max(0.1, Math.round(seconds * 10) / 10)} s`;
  if (seconds < 60) return `${Math.round(seconds * 10) / 10} s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return s ? `${m} min ${s} s` : `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h ${m % 60} min`;
}

/** Relations between artefacts, in words. */
export const RELATIONS: Record<string, { out: string; in: string }> = {
  "certifies-key": { out: "Certifies key", in: "Certified by" },
  "signed-with": { out: "Signed with", in: "Signs" },
  "protects-with": { out: "Uses algorithm", in: "Used by" },
  "uses-algorithm": { out: "Uses algorithm", in: "Used by" },
  negotiates: { out: "Negotiates", in: "Negotiated by" },
};

export function relationLabel(relation: string, direction: "in" | "out"): string {
  return RELATIONS[relation]?.[direction] ?? relation.replace(/-/g, " ");
}
