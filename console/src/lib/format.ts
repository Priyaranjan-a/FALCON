/** Formatting shared by the whole console, so every number reads the same way. */

const locale = undefined; // the viewer's locale

const integer = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 });
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function formatInt(n: number): string {
  return integer.format(n);
}

export function formatCompact(n: number): string {
  return Math.abs(n) < 10_000 ? integer.format(n) : compact.format(n);
}

/** Probabilities: adaptive precision so small risks never round to zero. */
export function formatPercent(p: number, digits?: number): string {
  const v = p * 100;
  if (digits !== undefined) return `${v.toFixed(digits)}%`;
  if (v === 0) return "0%";
  if (v < 0.1) return "<0.1%";
  if (v < 10) return `${v.toFixed(1)}%`;
  if (v >= 99.95) return ">99.9%";
  if (v >= 99.5) return `${v.toFixed(1)}%`;
  return `${Math.round(v)}%`;
}

function roundYears(years: number): number {
  const v = Math.abs(years);
  return v >= 10 ? Math.round(v) : Math.round(v * 10) / 10;
}

/** 4.79 → "4.8 years", 12.3 → "12 years", 1 → "1 year". */
export function formatYears(years: number): string {
  const v = roundYears(years);
  return `${v} ${v === 1 ? "year" : "years"}`;
}

export function formatYearsShort(years: number): string {
  return `${roundYears(years)} yr`;
}

/** Decimal year → "Jul 2031". */
export function formatDecimalYear(year: number): string {
  const whole = Math.floor(year);
  const month = Math.min(11, Math.max(0, Math.floor((year - whole) * 12)));
  return `${MONTHS[month]} ${whole}`;
}

export function formatDate(iso: string, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }): string {
  return new Date(iso).toLocaleDateString(locale, opts);
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(locale, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatMilestoneDate(iso: string, precision: "day" | "month" | "year"): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (precision === "year") return `By end of ${d.getUTCFullYear()}`;
  if (precision === "month") return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

const relative = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

export function formatRelative(iso: string, now = Date.now()): string {
  const seconds = Math.round((new Date(iso).getTime() - now) / 1000);
  const abs = Math.abs(seconds);
  if (abs < 45) return "just now";
  if (abs < 3600) return relative.format(Math.round(seconds / 60), "minute");
  if (abs < 86_400) return relative.format(Math.round(seconds / 3600), "hour");
  if (abs < 86_400 * 30) return relative.format(Math.round(seconds / 86_400), "day");
  if (abs < 86_400 * 365) return relative.format(Math.round(seconds / (86_400 * 30)), "month");
  return relative.format(Math.round(seconds / (86_400 * 365)), "year");
}

export function daysUntil(iso: string, now = new Date()): number {
  const target = new Date(`${iso}T00:00:00Z`).getTime();
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((target - today) / 86_400_000);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

/** "Mozilla/5.0 (Windows NT…) Chrome/…" → "Chrome on Windows". */
export function describeAgent(agent: string | null): string {
  if (!agent) return "Unknown device";
  const browser = /Edg\//.test(agent)
    ? "Edge"
    : /Chrome\//.test(agent)
      ? "Chrome"
      : /Firefox\//.test(agent)
        ? "Firefox"
        : /Safari\//.test(agent)
          ? "Safari"
          : /python|httpx|curl/i.test(agent)
            ? "API client"
            : "Browser";
  const os = /Windows/.test(agent)
    ? "Windows"
    : /Mac OS X|Macintosh/.test(agent)
      ? "macOS"
      : /Android/.test(agent)
        ? "Android"
        : /iPhone|iPad/.test(agent)
          ? "iOS"
          : /Linux/.test(agent)
            ? "Linux"
            : "";
  return os ? `${browser} on ${os}` : browser;
}

export const SECTOR_LABELS: Record<string, string> = {
  government: "Government",
  defence: "Defence",
  banking: "Banking & finance",
  insurance: "Insurance",
  telecom: "Telecommunications",
  energy: "Energy & utilities",
  healthcare: "Healthcare",
  technology: "Technology",
  manufacturing: "Manufacturing",
  transport: "Transport",
  education: "Education & research",
  other: "Other",
};
