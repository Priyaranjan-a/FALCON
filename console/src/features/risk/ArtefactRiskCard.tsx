import { ArrowUpRight, Radio } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/design/cn";
import { Card, CardHeader, Skeleton } from "@/design/components/Surface";
import { formatDecimalYear, formatPercent, formatYears } from "@/lib/format";
import { useRiskArtefact } from "@/lib/queries";
import type { RiskDetail } from "@/lib/types";
import { Ring } from "@/viz/charts/Ring";
import { KINDS } from "../discovery/vocab";
import { MoscaGlyph } from "./RiskPage";
import { BANDS, deadlineLabel, PolicyBadge, RiskBadge, ROLES } from "./vocab";

const LIFETIME_LABELS: Record<string, string> = { ephemeral: "Under 1 year", short: "1–5 years", medium: "5–10 years", long: "10–25 years", archival: "25 years or more" };
const CRITICALITY_LABELS: Record<string, string> = { critical: "Mission-critical", high: "Business-critical", moderate: "Important", low: "Supporting" };

/** Why an artefact scores what it does, term by term, and where it stands against policy. */
export function ArtefactRiskCard({ artefactId }: { artefactId: string }) {
  const risk = useRiskArtefact(artefactId);
  if (risk.isPending) return <Skeleton className="h-[420px] rounded-[18px]" />;
  if (!risk.data) return null;
  const r = risk.data;
  return (
    <>
      <Card id="risk">
        <CardHeader
          title="Quantum risk"
          subtitle="Business impact × likelihood, where likelihood is the strongest of classical attack, a quantum computer arriving in time (Mosca), and policy deadlines."
          actions={<RiskBadge band={r.band} score={r.score} />}
        />
        <div className="grid gap-6 md:grid-cols-[auto_1fr] md:items-center">
          <div className="flex justify-center">
            <Ring value={r.score / 100} size={128} thickness={11} color={BANDS[r.band].color} ariaLabel={`Risk score ${r.score} of 100`}>
              <span className="block text-title-1 tabular text-label">{r.score}</span>
              <span className="text-caption text-label-3">of 100</span>
            </Ring>
          </div>
          <div className="space-y-3">
            <Factor label="Business impact" value={r.impact.value} detail={impactDetail(r)} />
            <Factor label="Classical attack" value={r.likelihood.classical} driver={r.likelihood.driver === "classical"} detail="Attackable today, without a quantum computer" />
            <Factor
              label="Quantum computer in time"
              value={r.likelihood.quantum}
              driver={r.likelihood.driver === "quantum"}
              detail={`${formatPercent(r.mosca.probability)} chance within X + Y = ${formatYears(r.mosca.x + r.mosca.y)}, × severity ${r.likelihood.quantum_severity}`}
            />
            <Factor
              label="Policy deadline"
              value={r.likelihood.policy}
              driver={r.likelihood.driver === "policy"}
              detail={r.likelihood.policy_deadline ? `Nearest NIST date: ${deadlineLabel(r.likelihood.policy_deadline)}` : "No NIST deadline applies"}
            />
          </div>
        </div>
        {r.drivers.length > 0 && (
          <ul className="mt-5 space-y-1.5 rounded-[12px] bg-fill-2 px-4 py-3">
            {r.drivers.map((d) => (
              <li key={d} className="flex gap-2 text-subhead text-label">
                <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-full" style={{ background: BANDS[r.band].color }} />
                {d}
              </li>
            ))}
          </ul>
        )}

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <div className="mb-2 text-footnote font-semibold text-label-2">Mosca’s inequality for this artefact</div>
            <MoscaGlyph x={r.mosca.x} y={r.mosca.y} z={r.mosca.z} width={260} />
            <dl className="mt-3 grid grid-cols-3 gap-3">
              <Mini label="Lifetime X" value={formatYears(r.mosca.x)} hint={r.lifetime.basis} />
              <Mini label="Migration Y" value={formatYears(r.mosca.y)} hint={r.migration.label} />
              <Mini label="Horizon Z" value={formatYears(r.mosca.z)} hint={r.model.planning_label} />
            </dl>
            <p className="mt-3 text-footnote text-label-2">
              {r.classification.mosca === "not-affected"
                ? "Quantum-resistant: Mosca’s inequality does not apply."
                : r.mosca.exposure_years > 0
                  ? `X + Y exceeds Z by ${formatYears(r.mosca.exposure_years)}. It should have been migrated by ${formatDecimalYear(r.mosca.start_by + r.mosca.y)}.`
                  : `Inside the horizon by ${formatYears(-r.mosca.exposure_years)}. Start migrating by ${formatDecimalYear(r.mosca.start_by)}.`}
            </p>
          </div>
          <div>
            <div className="mb-2 text-footnote font-semibold text-label-2">Classification</div>
            <div className="flex flex-wrap gap-1.5">
              <Tag>{KINDS[r.kind].singular}</Tag>
              {r.roles.map((role) => (
                <Tag key={role} title={ROLES[role].summary}>
                  {ROLES[role].label}
                </Tag>
              ))}
              <Tag>Lifetime: {LIFETIME_LABELS[r.lifetime.band] ?? r.lifetime.band}</Tag>
              <Tag>{CRITICALITY_LABELS[r.classification.criticality]}</Tag>
            </div>
            <div className={cn("mt-4 flex items-start gap-3 rounded-[12px] px-3.5 py-3", r.hndl.exposed ? "bg-[var(--status-critical-tint)]" : "bg-fill-2")}>
              <Radio className={cn("mt-0.5 size-[18px] shrink-0", r.hndl.exposed ? "text-critical" : "text-label-3")} />
              <div className="text-subhead text-label">
                <div className="font-semibold">{r.hndl.exposed ? "Harvest now, decrypt later" : r.hndl.applies ? "Harvestable, inside the horizon" : "Not harvestable"}</div>
                <div className="text-label-2">
                  {r.hndl.exposed
                    ? `Traffic protected by it can be recorded ${r.hndl.reach === "internet" ? "from the internet" : r.hndl.reach === "partner" ? "on partner links" : "inside the network"} today and read once a CRQC exists, while the data still matters.`
                    : r.hndl.applies
                      ? "It protects confidentiality with quantum-vulnerable cryptography, but the data expires before the horizon."
                      : "It does not protect the confidentiality of recorded data with quantum-vulnerable cryptography."}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card padded={false}>
        <div className="px-5 pt-5">
          <CardHeader title="Policy" subtitle="Where this artefact stands against published transition rules, today and at their deadlines." />
        </div>
        <ul>
          {r.policies.map((p) => (
            <li key={p.framework} className="grid gap-2 px-5 py-3.5 hairline-t sm:grid-cols-[180px_1fr_auto] sm:items-start">
              <div>
                <div className="text-callout font-semibold text-label">{p.name}</div>
                <a href={p.source} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-caption text-accent-ink hover:underline">
                  {p.authority} <ArrowUpRight className="size-3" />
                </a>
              </div>
              <div className="text-subhead text-label-2">
                {p.rule}
                {(p.deprecated_from || p.disallowed_from) && (
                  <div className="mt-0.5 text-footnote text-label-3">
                    {p.deprecated_from ? (p.deprecated_from <= r.model.now + 0.01 ? "Deprecated today. " : `Deprecated from the ${deadlineLabel(p.deprecated_from)}. `) : ""}
                    {p.disallowed_from ? `${p.framework.startsWith("nist") ? "Disallowed" : "Deadline"}: ${deadlineLabel(p.disallowed_from)}.` : ""}
                  </div>
                )}
              </div>
              <PolicyBadge value={p.status_now} />
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

function impactDetail(r: RiskDetail): string {
  const parts = [`criticality ${r.impact.criticality}`, `exposure ${r.impact.exposure}`];
  if (r.impact.classification !== null) parts.push(`data ${r.impact.classification}`);
  return parts.join(" × ");
}

function Factor({ label, value, detail, driver }: { label: string; value: number; detail: string; driver?: boolean }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className={cn("text-subhead", driver ? "font-semibold text-label" : "text-label")}>
          {label}
          {driver && <span className="ml-1.5 rounded-[4px] bg-accent-tint px-1 text-[10px] font-semibold uppercase tracking-wide text-accent-ink">Driver</span>}
        </span>
        <span className="text-subhead font-semibold tabular text-label">{value.toFixed(2)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-fill">
        <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(value > 0 ? 2 : 0, value * 100)}%`, background: driver ? "var(--label)" : "var(--label-3)" }} />
      </div>
      <div className="mt-0.5 truncate text-caption text-label-3">{detail}</div>
    </div>
  );
}

function Mini({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-caption text-label-3">{label}</dt>
      <dd className="text-headline tabular text-label">{value}</dd>
      <dd className="truncate text-caption text-label-3" title={hint}>
        {hint}
      </dd>
    </div>
  );
}

function Tag({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <span title={title} className="inline-flex h-6 items-center rounded-full bg-fill-2 px-2.5 text-footnote font-medium text-label-2">
      {children}
    </span>
  );
}
