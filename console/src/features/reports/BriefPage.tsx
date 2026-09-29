import { ArrowLeft, Printer, ShieldCheck } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { LogoMark } from "@/design/components/Logo";
import { Skeleton } from "@/design/components/Surface";
import { formatDate, formatDecimalYear, formatInt, formatPercent } from "@/lib/format";
import { useMigrationPlan, useOrganisation, useRiskPolicies, useRiskSummary, useSnapshots } from "@/lib/queries";
import type { MigrationPlan, PolicyOverview, RiskSummary, Snapshot } from "@/lib/types";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { Meter } from "@/viz/charts/Meter";
import { WAVES } from "../migration/vocab";
import { BAND_ORDER, BANDS, FRAMEWORK_ORDER, FRAMEWORK_SHORT, POLICY_STATUS, RiskBadge } from "../risk/vocab";
import { groupHex } from "./vocab";

const POLICY_ORDER = ["disallowed", "deprecated", "not-approved", "transition", "acceptable", "approved", "not-applicable"] as const;

/**
 * The executive brief: the organisation's quantum readiness on one document,
 * for a board, a minister or an auditor. Every figure comes from the live
 * inventory and the organisation's threat model; print it or save it as PDF.
 */
export default function BriefPage() {
  const navigate = useNavigate();
  const org = useOrganisation();
  const summary = useRiskSummary();
  const plan = useMigrationPlan();
  const policies = useRiskPolicies();
  const snapshots = useSnapshots();

  // Print in light appearance whatever the screen uses: paper is white.
  useEffect(() => {
    const root = document.documentElement;
    let previous: string | undefined;
    const before = () => {
      previous = root.dataset.theme;
      root.dataset.theme = "light";
    };
    const after = () => {
      if (previous === undefined) delete root.dataset.theme;
      else root.dataset.theme = previous;
    };
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);

  useEffect(() => {
    document.title = "Quantum Readiness Brief · FALCON";
    return () => {
      document.title = "FALCON";
    };
  }, []);

  const ready = org.data && summary.data && plan.data && policies.data;

  return (
    <div className="brief h-dvh overflow-y-auto">
      <div className="no-print sticky top-0 z-10 flex justify-center px-4 pt-3">
        <div className="glass-strong flex w-full max-w-[860px] items-center gap-2 rounded-[14px] px-2 py-1.5">
          <Button variant="plain" icon={<ArrowLeft />} onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/reports"))}>
            Back
          </Button>
          <span className="flex-1 truncate text-center text-subhead text-label-2">Quantum Readiness Brief</span>
          <Button variant="filled" icon={<Printer />} onClick={() => window.print()} disabled={!ready}>
            Print or save PDF
          </Button>
        </div>
      </div>

      <article className="brief-paper mx-auto my-6 w-[calc(100%-32px)] max-w-[860px] rounded-[20px] bg-[var(--surface)] px-8 py-10 shadow-[var(--shadow-glass)] sm:px-14 sm:py-14">
        {!ready ? (
          <div className="space-y-4" aria-busy="true">
            <Skeleton className="h-8 w-72" />
            <Skeleton className="h-5 w-96 max-w-full" />
            <Skeleton className="h-[120px] rounded-[14px]" />
            <Skeleton className="h-[220px] rounded-[14px]" />
          </div>
        ) : (
          <Brief organisation={org.data!.name} sector={org.data!.sector} summary={summary.data!} plan={plan.data!} policies={policies.data!} snapshot={snapshots.data?.[0]} />
        )}
      </article>
    </div>
  );
}

function Brief({ organisation, summary: s, plan, policies, snapshot }: { organisation: string; sector: string; summary: RiskSummary; plan: MigrationPlan; policies: PolicyOverview; snapshot?: Snapshot }) {
  const urgent = s.bands.critical + s.bands.high;
  const late = plan.completion > plan.horizon;
  const today = formatDate(new Date().toISOString(), { day: "numeric", month: "long", year: "numeric" });
  const worstSystems = [...s.systems].sort((a, b) => b.score - a.score).slice(0, 6);
  const waves = plan.waves.filter((w) => w.artefacts > 0);

  return (
    <div className="reveal">
      <header className="flex items-start justify-between gap-6 border-b border-[var(--separator)] pb-6">
        <div>
          <div className="text-subhead font-medium text-label-3">{organisation}</div>
          <h1 className="mt-1 text-[34px] font-bold leading-[40px] tracking-[-0.022em] text-label">Quantum Readiness Brief</h1>
          <p className="mt-2 text-callout text-label-2">
            {today} · Threat model: {s.model.scenario}, planning horizon {s.model.planning_label}, {formatPercent(s.model.tolerance)} tolerance.
          </p>
        </div>
        <LogoMark size={40} className="shrink-0" />
      </header>

      <section className="brief-section pt-7">
        <p className="text-[21px] font-semibold leading-[29px] tracking-[-0.012em] text-label">
          {formatInt(urgent)} of {formatInt(s.total)} cryptographic assets are at critical or high quantum risk.{" "}
          {s.hndl.exposed > 0 ? (
            <span>
              {formatInt(s.hndl.exposed)} protect data an adversary can record today and decrypt once a quantum computer exists, across {formatInt(s.hndl.systems)}{" "}
              {s.hndl.systems === 1 ? "system" : "systems"}.
            </span>
          ) : (
            <span>None protects data exposed to harvest now, decrypt later.</span>
          )}{" "}
          At the current plan, migration completes in {formatDecimalYear(plan.completion)}, {late ? "after" : "before"} the planning horizon.
        </p>
        <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Figure label="Assets inventoried" value={s.total} />
          <Figure label="Critical or high risk" value={urgent} tone={urgent ? "critical" : "good"} />
          <Figure label="Harvest now, decrypt later" value={s.hndl.exposed} tone={s.hndl.exposed ? "critical" : "good"} />
          <Figure label="Migration completes" value={plan.completion} format={(n) => formatDecimalYear(n)} animate={false} tone={late ? "critical" : "good"} detail={`${formatPercent(plan.completion_probability)} chance a CRQC exists by then`} />
        </div>
      </section>

      <Section title="Risk profile" lead="Every algorithm, key, certificate, protocol and library found, scored by Mosca’s inequality against the threat model.">
        <Meter
          ariaLabel="Assets by risk band"
          unit="assets"
          segments={BAND_ORDER.map((b) => ({ key: b, label: BANDS[b].label, value: s.bands[b] ?? 0, color: BANDS[b].color }))}
        />
      </Section>

      <Section title="Systems most at risk" lead="Ranked by the highest risk among their cryptography." flow>
        <table className="w-full text-left text-subhead">
          <thead>
            <tr className="text-footnote text-label-3">
              <th className="py-1.5 font-medium">System</th>
              <th className="py-1.5 font-medium">Risk</th>
              <th className="py-1.5 text-right font-medium">Assets</th>
              <th className="py-1.5 text-right font-medium">HNDL</th>
              <th className="py-1.5 text-right font-medium max-sm:hidden">Est. migration</th>
            </tr>
          </thead>
          <tbody>
            {worstSystems.map((sys) => (
              <tr key={sys.id} className="border-t border-[var(--separator)]">
                <td className="py-2 pr-3">
                  <div className="font-medium text-label">{sys.name}</div>
                  <div className="text-caption text-label-3">
                    {sys.code} · {sys.criticality} criticality · {sys.exposure}
                  </div>
                </td>
                <td className="py-2 pr-3">
                  <RiskBadge band={sys.band} score={sys.score} />
                </td>
                <td className="py-2 text-right tabular text-label">{formatInt(sys.artefacts)}</td>
                <td className="py-2 text-right tabular text-label">{formatInt(sys.hndl_exposed)}</td>
                <td className="py-2 text-right tabular text-label-2 max-sm:hidden">{sys.estimated_y !== null ? `${sys.estimated_y.toFixed(1)} yr` : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="Compliance today" lead="How the inventory stands against the frameworks that set the deadlines.">
        <div className="space-y-3.5">
          {FRAMEWORK_ORDER.map((id) => {
            const f = policies.frameworks.find((x) => x.id === id);
            if (!f) return null;
            const counts = f.now;
            const total = POLICY_ORDER.reduce((sum, k) => sum + (counts[k] ?? 0), 0) || 1;
            const blocking = (counts.disallowed ?? 0) + (counts.deprecated ?? 0) + (counts["not-approved"] ?? 0);
            const transition = counts.transition ?? 0;
            return (
              <div key={id} className="grid grid-cols-[120px_minmax(0,1fr)_auto] items-center gap-3 max-sm:grid-cols-[96px_minmax(0,1fr)_auto]">
                <span className="text-subhead font-medium text-label">{FRAMEWORK_SHORT[id]}</span>
                <div className="flex h-2 gap-[2px] overflow-hidden rounded-full bg-fill-2" role="img" aria-label={`${FRAMEWORK_SHORT[id]}: ${blocking} assets not permitted`}>
                  {POLICY_ORDER.filter((k) => counts[k]).map((k) => (
                    <span key={k} style={{ width: `${((counts[k] ?? 0) / total) * 100}%`, background: POLICY_STATUS[k].color }} />
                  ))}
                </div>
                <span className="text-footnote tabular text-label-2">{blocking ? `${formatInt(blocking)} not permitted` : transition ? `${formatInt(transition)} must transition` : "Compliant"}</span>
              </div>
            );
          })}
          <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
            {POLICY_ORDER.slice(0, 6).map((k) => (
              <li key={k} className="flex items-center gap-1.5 text-caption text-label-3">
                <span className="size-2 rounded-[2px]" style={{ background: POLICY_STATUS[k].color }} />
                {POLICY_STATUS[k].label}
              </li>
            ))}
          </ul>
        </div>
      </Section>

      <Section title="Migration roadmap" lead={`${formatInt(plan.totals.artefacts)} assets across ${formatInt(plan.totals.systems)} systems, in five waves ordered by urgency.`}>
        <ol className="space-y-2.5">
          {waves.map((w, i) => (
            <li key={w.key} className="flex items-start gap-3">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-caption font-semibold text-white" style={{ background: WAVES[w.key].color }}>
                {i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="text-callout font-semibold text-label">{w.title}</span>
                  <span className="text-footnote tabular text-label-2">
                    {formatDecimalYear(w.start)} – {formatDecimalYear(w.finish)} · {formatInt(w.artefacts)} assets
                    {w.on_time === false && <span className="ml-1.5 font-semibold text-critical">late</span>}
                  </span>
                </div>
                <p className="text-footnote text-label-2">{w.summary}</p>
              </div>
            </li>
          ))}
        </ol>
        {plan.totals.targets.length > 0 && (
          <p className="mt-4 text-footnote text-label-2">
            <span className="font-medium text-label">Replacements:</span> {plan.totals.targets.slice(0, 6).map((t) => `${t.name} (${formatInt(t.count)})`).join(", ")}.
          </p>
        )}
      </Section>

      <Section title="Act first" lead="The highest-risk assets, with the reason each one scores as it does.">
        <ol className="space-y-2">
          {s.top.slice(0, 6).map((r) => (
            <li key={r.id} className="flex items-start gap-3">
              <RiskBadge band={r.band} score={r.score} className="mt-0.5" />
              <div className="min-w-0">
                <div className="text-subhead font-medium text-label">
                  {r.name} <span className="font-normal text-label-3">· {r.system.name}</span>
                </div>
                {r.driver && <div className="text-footnote text-label-2">{r.driver}</div>}
              </div>
            </li>
          ))}
        </ol>
      </Section>

      <footer className="brief-section mt-8 flex items-start gap-3 rounded-[14px] bg-fill-2 p-4">
        <ShieldCheck className={cn("mt-0.5 size-5 shrink-0", snapshot ? "text-good" : "text-label-3")} />
        <div className="text-footnote text-label-2">
          {snapshot ? (
            <>
              <span className="font-medium text-label">Evidence:</span> signed snapshot “{snapshot.label}” of {formatDate(snapshot.created_at)}, CycloneDX 1.6 CBOM SHA-256{" "}
              <span className="font-mono">{groupHex(snapshot.digest, 4)}…</span>, signed with ML-DSA-65 key <span className="font-mono">{groupHex(snapshot.key_id, 2)}</span>.
              Verify it with FALCON or OpenSSL 3.5.
            </>
          ) : (
            <>No signed snapshot yet. Sign one under Reports to make this brief verifiable evidence.</>
          )}
          <div className="mt-1 text-caption text-label-3">
            Prepared by FALCON from the live inventory. Risk follows NIST IR 8547, NIST SP 800-131A, CNSA 2.0 and the EU PQC roadmap.
          </div>
        </div>
      </footer>
    </div>
  );
}

function Section({ title, lead, children, flow }: { title: string; lead?: string; children: ReactNode; flow?: boolean }) {
  return (
    <section className={cn("mt-9", flow ? "brief-flow" : "brief-section")}>
      <h2 className="text-title-3 text-label">{title}</h2>
      {lead && <p className="mb-4 mt-0.5 text-subhead text-label-2">{lead}</p>}
      {children}
    </section>
  );
}

function Figure({ label, value, format, tone, detail, animate = true }: { label: string; value: number; format?: (n: number) => string; tone?: "critical" | "good"; detail?: string; animate?: boolean }) {
  const show = format ?? ((n: number) => formatInt(Math.round(n)));
  return (
    <div className="flex flex-col rounded-[14px] bg-fill-2 px-4 py-3.5">
      <div className="text-footnote text-label-3">{label}</div>
      <div className="mt-auto flex items-center gap-1.5 pt-1">
        {tone && <span className={cn("size-2 rounded-full", tone === "critical" ? "bg-critical" : "bg-good")} aria-hidden />}
        {animate ? <AnimatedNumber value={value} format={show} className="whitespace-nowrap text-title-1 tabular text-label" /> : <span className="whitespace-nowrap text-title-1 tabular text-label">{show(value)}</span>}
      </div>
      <div className="mt-0.5 min-h-[16px] text-caption text-label-3">{detail}</div>
    </div>
  );
}
