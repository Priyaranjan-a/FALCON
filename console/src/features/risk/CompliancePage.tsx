import { ArrowUpRight, ScrollText, Search } from "lucide-react";
import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { cn } from "@/design/cn";
import { Card, Chip, EmptyState, Skeleton } from "@/design/components/Surface";
import { Segmented } from "@/design/components/Segmented";
import { Table, type Column } from "@/design/components/Table";
import { formatInt } from "@/lib/format";
import { useRiskPolicies, useRiskRegister } from "@/lib/queries";
import type { FrameworkId, PolicyOverview, PolicyStatus, RiskRow } from "@/lib/types";
import { Meter } from "@/viz/charts/Meter";
import { KindGlyph } from "../discovery/vocab";
import { Page, PageSkeleton } from "../shell/Page";
import { deadlineLabel, FRAMEWORK_ORDER, PolicyBadge, POLICY_STATUS, RiskBadge } from "./vocab";

const SHOWN: PolicyStatus[] = ["disallowed", "deprecated", "not-approved", "transition", "acceptable", "approved"];

export default function CompliancePage() {
  const policies = useRiskPolicies();
  const [params, setParams] = useSearchParams();
  const framework = (params.get("framework") as FrameworkId) ?? "nist-ir-8547";
  const status = (params.get("status") as PolicyStatus) ?? null;
  const select = (fw: FrameworkId, st: PolicyStatus | null) => {
    const next = new URLSearchParams(params);
    next.set("framework", fw);
    if (st) next.set("status", st);
    else next.delete("status");
    setParams(next, { replace: true });
    document.getElementById("affected")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (policies.isPending) return <PageSkeleton />;
  const data = policies.data;
  if (!data) return null;
  const ordered = FRAMEWORK_ORDER.map((id) => data.frameworks.find((f) => f.id === id)!).filter(Boolean);

  return (
    <Page
      title="Compliance"
      subtitle="Every artefact mapped to the published transition rules, today and at each deadline. Dates follow the texts: “after 2030” takes effect on 1 January 2031."
      width="wide"
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {ordered.map((f) => (
          <FrameworkCard key={f.id} framework={f} selected={framework === f.id} onSelect={(st) => select(f.id, st)} />
        ))}
      </div>
      <Affected framework={framework} status={status} data={data} onStatus={(st) => select(framework, st)} />
    </Page>
  );
}

function FrameworkCard({ framework: f, selected, onSelect }: { framework: PolicyOverview["frameworks"][number]; selected: boolean; onSelect: (s: PolicyStatus | null) => void }) {
  const segments = SHOWN.map((s) => ({ key: s, label: POLICY_STATUS[s].label, value: f.now[s] ?? 0, color: POLICY_STATUS[s].color }));
  const applicable = segments.reduce((n, s) => n + s.value, 0);
  const checkpoints = Object.entries(f.at).map(([year, counts]) => ({ year: Number(year), counts }));
  const bad = (c: Partial<Record<PolicyStatus, number>>) => (c.disallowed ?? 0) + (c["not-approved"] ?? 0);
  return (
    <Card className={cn("flex flex-col", selected && "outline outline-2 -outline-offset-2 outline-[var(--accent)]")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-caption font-medium text-label-3">
            {f.authority} · {f.publication}
          </div>
          <h2 className="mt-0.5 text-title-3 text-label">{f.name}</h2>
          <p className="text-footnote text-label-2">{f.title}</p>
        </div>
        <a href={f.source} target="_blank" rel="noreferrer" className="hover-light inline-flex shrink-0 items-center gap-1 rounded-full bg-fill-2 px-2.5 py-1 text-footnote font-medium text-accent-ink">
          Source <ArrowUpRight className="size-3.5" />
        </a>
      </div>
      <p className="mt-3 text-subhead text-label-2">{f.summary}</p>
      <div className="mt-4">
        <Meter unit="artefacts" ariaLabel={`${f.name} today: ${segments.map((s) => `${s.label} ${s.value}`).join(", ")}`} segments={segments} />
      </div>
      <div className="mt-4 text-footnote font-semibold text-label-2">Out of compliance over time</div>
      <div className="mt-2 flex items-end gap-2">
        {checkpoints.map(({ year, counts }, i) => {
          const value = bad(counts);
          const pct = applicable ? value / applicable : 0;
          return (
            <div key={year} className="flex min-w-0 flex-1 flex-col items-center gap-1">
              <span className="text-caption font-semibold tabular text-label">{formatInt(value)}</span>
              <div className="flex h-16 w-full items-end rounded-[6px] bg-fill-2">
                <div className="w-full rounded-t-[4px] transition-[height] duration-700" style={{ height: `${Math.max(value ? 4 : 0, pct * 100)}%`, background: "var(--status-critical)" }} />
              </div>
              <span className="text-caption tabular text-label-3">{i === 0 ? "Today" : year}</span>
            </div>
          );
        })}
      </div>
      {f.dates.length > 0 && <p className="mt-3 text-caption text-label-3">Deadlines ahead: {f.dates.map(deadlineLabel).join(", ")}.</p>}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {SHOWN.filter((s) => (f.now[s] ?? 0) > 0).map((s) => (
          <button key={s} type="button" onClick={() => onSelect(s)} className="hover-light rounded-full bg-fill-2 px-2.5 py-1 text-footnote font-medium text-label-2 transition-colors hover:text-label">
            {formatInt(f.now[s] ?? 0)} {POLICY_STATUS[s].label.toLowerCase()}
          </button>
        ))}
      </div>
    </Card>
  );
}

function Affected({ framework, status, data, onStatus }: { framework: FrameworkId; status: PolicyStatus | null; data: PolicyOverview; onStatus: (s: PolicyStatus | null) => void }) {
  const navigate = useNavigate();
  const f = data.frameworks.find((x) => x.id === framework)!;
  const statuses = SHOWN.filter((s) => (f.now[s] ?? 0) > 0);
  const effective = status ?? statuses[0] ?? "disallowed";
  const register = useRiskRegister({ framework, policy_status: [effective], sort: "score" });
  const rows = useMemo(() => register.data?.pages.flatMap((p) => p.items) ?? [], [register.data]);
  const columns: Column<RiskRow>[] = [
    {
      key: "a",
      header: "Artefact",
      cell: (r) => (
        <div className="flex min-w-0 items-center gap-3">
          <KindGlyph kind={r.kind} size={28} />
          <div className="min-w-0">
            <div className="truncate font-medium text-label">{r.name}</div>
            <div className="truncate text-footnote text-label-3">{r.driver ?? r.migration.label}</div>
          </div>
        </div>
      ),
    },
    { key: "s", header: "System", hideBelow: "md", cell: (r) => <Chip>{r.system.code}</Chip> },
    { key: "p", header: f.name, cell: (r) => <PolicyBadge value={r.policy[framework]} /> },
    { key: "r", header: "Risk", hideBelow: "sm", cell: (r) => <RiskBadge band={r.band} score={r.score} /> },
  ];
  return (
    <div id="affected" className="mt-6 scroll-mt-16 space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-title-3 text-label">{f.name}</h2>
        {statuses.length > 1 && (
          <Segmented
            label="Status"
            value={effective}
            onChange={(s) => onStatus(s)}
            options={statuses.map((s) => ({ value: s, label: `${POLICY_STATUS[s].label} ${formatInt(f.now[s] ?? 0)}` }))}
          />
        )}
      </div>
      <Card padded={false} className="overflow-hidden">
        {register.isPending ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <Table
            caption={`Artefacts ${POLICY_STATUS[effective].label.toLowerCase()} under ${f.name}`}
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
            onRowClick={(r) => navigate(`/inventory/${r.id}`)}
            rowLabel={(r) => `Open ${r.name}`}
            empty={<EmptyState compact icon={statuses.length ? <Search /> : <ScrollText />} title="Nothing here" message="No artefact has this status." />}
          />
        )}
      </Card>
    </div>
  );
}
