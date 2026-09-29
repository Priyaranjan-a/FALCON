import { Braces, Check, Copy, FileCode2, FileSpreadsheet, Package, ScanSearch, Boxes, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Tooltip } from "@/design/components/Menu";
import { spring } from "@/design/motion";
import type { Drift, ReportFormatId, RiskBand, VerificationCheck } from "@/lib/types";
import { BAND_ORDER, BANDS } from "../risk/vocab";

export const FORMAT_META: Record<ReportFormatId, { icon: LucideIcon; standard: string; audience: string }> = {
  "cyclonedx-json": { icon: Boxes, standard: "OWASP CycloneDX 1.6", audience: "CBOM tools, Dependency-Track, auditors" },
  "cyclonedx-xml": { icon: FileCode2, standard: "OWASP CycloneDX 1.6", audience: "XML toolchains and archives" },
  sarif: { icon: ScanSearch, standard: "OASIS SARIF 2.1.0", audience: "GitHub, GitLab, Azure DevOps, IDEs" },
  spdx: { icon: Package, standard: "ISO/IEC 5962 SPDX 2.3", audience: "SBOM programmes and procurement" },
  csv: { icon: FileSpreadsheet, standard: "RFC 4180 CSV", audience: "Spreadsheets and risk registers" },
  json: { icon: Braces, standard: "FALCON JSON", audience: "Scripts and dashboards" },
};

export const CHECKS: Record<VerificationCheck["check"], string> = {
  envelope: "Envelope",
  key: "Public key",
  signature: "ML-DSA-65 signature",
  statement: "In-toto statement",
  digest: "CBOM digest",
};

export const DRIFT_VERDICT: Record<Drift["verdict"], { label: string; tone: "good" | "critical" | "warning" | "neutral" | "accent" }> = {
  improved: { label: "Improved", tone: "good" },
  regressed: { label: "Regressed", tone: "critical" },
  mixed: { label: "Mixed", tone: "warning" },
  changed: { label: "Changed", tone: "accent" },
  unchanged: { label: "No change", tone: "neutral" },
};

/** Groups a hex digest for reading aloud or comparing by eye: 4-character blocks. */
export function groupHex(hex: string, blocks = 8): string {
  return (hex.match(/.{1,4}/g) ?? []).slice(0, blocks).join(" ");
}

/** Copies text and confirms in place: the icon turns into a check on a spring, then settles back. */
export function CopyButton({ text, label, className }: { text: string; label: string; className?: string }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      window.setTimeout(() => setDone(false), 1400);
    } catch {
      toast.error("Copying is blocked here. Select the text and copy it instead.");
    }
  };
  return (
    <Tooltip content={done ? "Copied" : label}>
      <button
        type="button"
        onClick={copy}
        aria-label={label}
        className={cn(
          "hover-light relative grid size-7 shrink-0 place-items-center rounded-[8px] text-label-2 transition-[background-color,transform] duration-150 hover:bg-fill hover:text-label active:scale-[0.92] focus-visible:focus-ring",
          className,
        )}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={done ? "done" : "copy"}
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.4, opacity: 0 }}
            transition={spring.snappy}
            className={cn("flex", done && "text-good")}
          >
            {done ? <Check className="size-4" strokeWidth={2.5} /> : <Copy className="size-[15px]" />}
          </motion.span>
        </AnimatePresence>
      </button>
    </Tooltip>
  );
}

/** A snapshot's risk profile as one thin segmented bar; the counts are printed beside it. */
export function BandStrip({ bands, className }: { bands: Record<RiskBand, number>; className?: string }) {
  const total = BAND_ORDER.reduce((s, b) => s + (bands[b] ?? 0), 0) || 1;
  return (
    <div className={cn("flex h-1.5 w-full gap-[2px] overflow-hidden rounded-full", className)} aria-hidden>
      {BAND_ORDER.filter((b) => bands[b]).map((b) => (
        <span key={b} className="h-full first:rounded-l-full last:rounded-r-full" style={{ width: `${(bands[b] / total) * 100}%`, background: BANDS[b].color }} />
      ))}
    </div>
  );
}
