import { ArrowRight, Check } from "lucide-react";
import { Card, CardHeader, Skeleton } from "@/design/components/Surface";
import { formatYears } from "@/lib/format";
import { useRecommendation } from "@/lib/queries";
import type { PqcAlgorithm } from "@/lib/types";
import { ACTIONS, formatBytesShort, formatMicros } from "./vocab";

/** What to replace this artefact with, what it costs, and how. */
export function RecommendationCard({ artefactId }: { artefactId: string }) {
  const rec = useRecommendation(artefactId);
  if (rec.isPending) return <Skeleton className="h-[260px] rounded-[18px]" />;
  const r = rec.data;
  if (!r) return null;
  const Icon = ACTIONS[r.action].icon;
  if (r.action === "keep") {
    return (
      <Card>
        <div className="flex items-start gap-3">
          <span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-[var(--status-good-tint)]">
            <Check className="size-[18px] text-good" strokeWidth={2.5} />
          </span>
          <div>
            <h2 className="text-headline text-label">{r.title}</h2>
            <p className="text-subhead text-label-2">{r.summary}</p>
          </div>
        </div>
      </Card>
    );
  }
  return (
    <Card id="recommendation">
      <CardHeader title="Recommended migration" subtitle={`${r.grade} · ${r.effort.label}, about ${formatYears(r.effort.years)}`} />
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-[12px] bg-accent-tint text-accent">
          <Icon className="size-5" />
        </span>
        <div className="min-w-0">
          <div className="text-title-3 text-label">{r.title}</div>
          <p className="mt-0.5 text-subhead text-label-2">{r.summary}</p>
        </div>
      </div>

      {(r.primary || r.hybrid) && (
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {r.primary && <Option label="Primary" algorithm={r.primary} />}
          {r.hybrid && <Option label="Transition (hybrid)" algorithm={r.hybrid} />}
        </div>
      )}

      {(r.overhead || r.latency) && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {r.overhead && (
            <div className="rounded-[12px] bg-fill-2 px-3.5 py-3">
              <div className="text-caption text-label-3">On the wire</div>
              <div className="text-headline tabular text-label">
                {r.overhead.delta !== null ? `+${formatBytesShort(r.overhead.delta)}` : formatBytesShort(r.overhead.after)}
              </div>
              <div className="text-caption text-label-3">
                {r.overhead.before !== null ? `${formatBytesShort(r.overhead.before)} → ${formatBytesShort(r.overhead.after)} ` : ""}
                {r.overhead.unit}
              </div>
            </div>
          )}
          {r.latency && (
            <div className="rounded-[12px] bg-fill-2 px-3.5 py-3">
              <div className="text-caption text-label-3">Measured on this host</div>
              <div className="text-headline tabular text-label">
                {Object.entries(r.latency.after.operations)
                  .filter(([op]) => op !== "keygen")
                  .map(([op, us]) => `${op} ${formatMicros(us)}`)
                  .join(" · ")}
              </div>
              <div className="text-caption text-label-3">
                {r.latency.before
                  ? `${r.latency.before.algorithm}: ${Object.entries(r.latency.before.operations).filter(([op]) => op !== "keygen").map(([op, us]) => `${op} ${formatMicros(us)}`).join(" · ")}`
                  : r.latency.after.algorithm}
              </div>
            </div>
          )}
        </div>
      )}

      {r.steps.length > 0 && (
        <>
          <div className="mb-2 mt-5 text-footnote font-semibold text-label-2">Steps</div>
          <ol className="space-y-2">
            {r.steps.map((step, i) => (
              <li key={step} className="flex gap-3 text-subhead text-label">
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-fill text-caption font-semibold tabular text-label-2">{i + 1}</span>
                {step}
              </li>
            ))}
          </ol>
        </>
      )}
      {r.alternatives.length > 0 && (
        <>
          <div className="mb-2 mt-5 text-footnote font-semibold text-label-2">Alternatives</div>
          <ul className="space-y-1.5">
            {r.alternatives.map((a) => (
              <li key={a.name} className="flex items-start gap-2 text-subhead text-label-2">
                <ArrowRight className="mt-1 size-3.5 shrink-0 text-label-3" />
                <span>
                  <strong className="font-semibold text-label">{a.name}</strong> ({a.standard}). {a.why}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

function Option({ label, algorithm: a }: { label: string; algorithm: PqcAlgorithm }) {
  const sizes = [
    a.sizes.public_key && `public key ${formatBytesShort(a.sizes.public_key)}`,
    a.sizes.ciphertext && `ciphertext ${formatBytesShort(a.sizes.ciphertext)}`,
    a.sizes.signature && `signature ${formatBytesShort(a.sizes.signature)}`,
  ].filter(Boolean);
  return (
    <div className="rounded-[14px] p-4 shadow-[inset_0_0_0_1px_var(--separator)]">
      <div className="text-caption font-medium text-label-3">{label}</div>
      <div className="mt-0.5 text-headline text-label">{a.name}</div>
      <div className="text-footnote text-label-3">
        {a.standard}
        {a.category ? ` · NIST category ${a.category}` : ""}
      </div>
      <p className="mt-2 text-footnote text-label-2">{a.why || a.summary}</p>
      {sizes.length > 0 && <p className="mt-1.5 text-caption tabular text-label-3">{sizes.join(" · ")}</p>}
    </div>
  );
}
