import { ArrowLeft, Ellipsis, Pencil, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useNavigate, useParams } from "react-router";
import { Button, IconButton } from "@/design/components/Button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/design/components/Menu";
import { Confirm } from "@/design/components/Sheet";
import { Card, CardHeader, Chip, EmptyState, GroupedList, GroupedRow, Skeleton } from "@/design/components/Surface";
import { useCan } from "@/lib/access";
import { ApiError } from "@/lib/api";
import { formatDate, formatDecimalYear, formatPercent, formatYears } from "@/lib/format";
import { decimalYear } from "@/lib/horizon";
import { useDeleteSystem, useSystem, useVocabulary } from "@/lib/queries";
import type { SystemRecord } from "@/lib/types";
import { MoscaChart, STATUS_META } from "@/viz/charts/MoscaChart";
import { ProbabilityCurve } from "@/viz/charts/ProbabilityCurve";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { series } from "@/viz/core/tokens";
import { useOrganisationModel } from "../horizon/useThreatModel";
import { SystemDiscovery } from "../discovery/SystemDiscovery";
import { ActivityFeed } from "../settings/ActivityFeed";
import { Page, PageSkeleton } from "../shell/Page";
import { CriticalityBars, MoscaBadge } from "./parts";
import { SystemSheet } from "./SystemSheet";

export default function SystemDetailPage() {
  const { systemId = "" } = useParams();
  const navigate = useNavigate();
  const system = useSystem(systemId);
  const vocabulary = useVocabulary().data;
  const canWrite = useCan("systems.write");
  const canDelete = useCan("systems.delete");
  const canAudit = useCan("audit.read");
  const remove = useDeleteSystem();
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);

  if (system.isPending) return <PageSkeleton />;
  if (system.isError) {
    const missing = system.error instanceof ApiError && system.error.status === 404;
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <EmptyState
          icon={<ArrowLeft />}
          title={missing ? "This system no longer exists" : "The system couldn’t be loaded"}
          message={missing ? "It may have been removed from the register." : system.error.message}
          action={<Button variant="tinted" onClick={() => navigate("/systems")}>Back to Systems</Button>}
        />
      </div>
    );
  }

  const s = system.data;
  const m = s.mosca;
  const meta = STATUS_META[m.status];

  return (
    <Page
      eyebrow={
        <span className="flex items-center gap-2">
          <button type="button" onClick={() => navigate("/systems")} className="inline-flex items-center gap-1 rounded text-accent-ink hover:underline">
            <ArrowLeft className="size-3.5" /> Systems
          </button>
          <span className="text-label-4">/</span>
          <Chip>{s.code}</Chip>
        </span>
      }
      title={s.name}
      subtitle={s.description ?? `${vocabulary?.kinds[s.kind].label ?? ""} · ${vocabulary?.environment[s.environment].label ?? ""}`}
      actions={
        <>
          {canWrite && (
            <Button variant="gray" icon={<Pencil />} onClick={() => setEditing(true)}>
              Edit
            </Button>
          )}
          {canDelete && (
            <Menu>
              <MenuTrigger asChild>
                <IconButton label="More actions">
                  <Ellipsis />
                </IconButton>
              </MenuTrigger>
              <MenuContent>
                <MenuItem destructive icon={<Trash2 />} onSelect={() => setConfirming(true)}>
                  Remove from register
                </MenuItem>
              </MenuContent>
            </Menu>
          )}
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader
              title="Quantum exposure"
              subtitle="Mosca’s inequality under the organisation’s threat model."
              actions={<MoscaBadge status={m.status} />}
            />
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <Figure label={m.exposure_years > 0 ? "Exposed by" : "Margin"} value={Math.abs(m.exposure_years)} format={(v) => formatYears(v)} />
              <Figure label="CRQC before data expires" value={m.probability} format={(v) => formatPercent(v)} />
              <FigureText label="Latest safe start" value={formatDecimalYear(m.start_by)} sub={relativeYears(m.start_by)} />
              <FigureText label="Latest safe completion" value={formatDecimalYear(m.complete_by)} sub={relativeYears(m.complete_by)} />
            </div>
            <div className="mt-6">
              <MoscaChart
                ariaLabel={`Mosca chart for ${s.name}`}
                rows={[{ id: s.id, code: s.code, name: s.name, x: m.x, y: m.y, status: m.status, probability: m.probability }]}
                z={m.z}
                labelWidth={170}
              />
            </div>
            <p className="text-subhead text-label-2">
              Data in {s.name} must stay confidential for <strong className="font-semibold text-label">{formatYears(m.x)}</strong>, and migrating it takes{" "}
              <strong className="font-semibold text-label">{formatYears(m.y)}</strong>. At your tolerance, a quantum adversary must be assumed within{" "}
              <strong className="font-semibold text-label">{formatYears(m.z)}</strong>.{" "}
              {m.status === "exposed"
                ? "Data encrypted today can be harvested now and decrypted while it still matters."
                : m.status === "watch"
                  ? "The margin is under two years; start planning the migration now."
                  : "The system is inside the horizon for now."}
            </p>
          </Card>

          <SystemDiscovery system={s} />

          <CostOfWaiting system={s} />

          {canAudit && (
            <Card>
              <CardHeader title="Activity" subtitle="Every change to this system, from the audit ledger." />
              <ActivityFeed target={s.id} limit={8} />
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <GroupedList header="Profile">
            <GroupedRow label="Criticality" value={<CriticalityBars value={s.criticality} vocabulary={vocabulary} />} />
            <GroupedRow label="Data classification" value={vocabulary?.classification[s.data_classification].label} />
            <GroupedRow label="Exposure" value={vocabulary?.exposure[s.exposure].label} />
            <GroupedRow label="Kind" value={vocabulary?.kinds[s.kind].label} />
            <GroupedRow label="Lifecycle" value={vocabulary?.lifecycle[s.lifecycle].label} />
            <GroupedRow label="Environment" value={vocabulary?.environment[s.environment].label} />
          </GroupedList>
          <GroupedList header="Ownership">
            <GroupedRow label="Business owner" value={s.owner ?? <span className="text-label-4">Not assigned</span>} />
            <GroupedRow label="Team" value={s.team ?? <span className="text-label-4">Not assigned</span>} />
            <GroupedRow label="Tags">
              <div className="flex flex-wrap justify-end gap-1">
                {s.tags.length ? s.tags.map((t) => <Chip key={t} className="font-sans">{t}</Chip>) : <span className="text-callout text-label-4">None</span>}
              </div>
            </GroupedRow>
          </GroupedList>
          <GroupedList>
            <GroupedRow label="Registered" value={formatDate(s.created_at)} />
            <GroupedRow label="Last updated" value={formatDate(s.updated_at)} />
          </GroupedList>
          <p className="px-1 text-footnote text-label-3">
            <meta.icon className="mr-1 inline size-3.5 align-[-2px]" style={{ color: meta.color }} />
            Status recalculates whenever the threat model or this system changes.
          </p>
        </div>
      </div>

      <SystemSheet open={editing} onOpenChange={setEditing} system={s} />
      <Confirm
        open={confirming}
        onOpenChange={setConfirming}
        title={`Remove ${s.name}?`}
        message="It will leave the register. The audit ledger keeps a record of the removal."
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          await remove.mutateAsync(s.id);
          toast.success(`${s.name} removed`);
          navigate("/systems", { replace: true });
        }}
      />
    </Page>
  );
}

function Figure({ label, value, format }: { label: string; value: number; format: (v: number) => string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-footnote font-medium text-label-3">{label}</div>
      <AnimatedNumber value={value} format={format} className="text-title-2 text-label" />
    </div>
  );
}

function FigureText({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-footnote font-medium text-label-3">{label}</div>
      <div className="truncate text-title-2 text-label">{value}</div>
      {sub && <div className="truncate text-footnote text-label-3">{sub}</div>}
    </div>
  );
}

/** "Passed 7.7 years ago" or "In 2 years", relative to today. */
function relativeYears(year: number): string {
  const delta = year - decimalYear();
  return delta < 0 ? `Passed ${formatYears(-delta)} ago` : `In ${formatYears(delta)}`;
}

/** Chance of exposure as a function of when migration starts. */
function CostOfWaiting({ system }: { system: SystemRecord }) {
  const { model } = useOrganisationModel();
  const curve = useMemo(() => {
    if (!model) return null;
    const { x, y } = system.mosca;
    const points = Array.from({ length: 12 * 4 + 1 }, (_, i) => {
      const delay = i / 4;
      return { year: model.now + delay, p: model.probabilityBy(delay + x + y) };
    });
    return points;
  }, [model, system.mosca]);

  if (!model || !curve) return <Skeleton className="h-[320px] rounded-[18px]" />;
  const { x, y } = system.mosca;
  const latestStart = model.now + model.planningYears - x - y;
  const today = curve[0].p;
  const inFive = curve[20].p;

  return (
    <Card>
      <CardHeader
        title="The cost of waiting"
        subtitle={`Chance a CRQC exists before ${system.name}'s data expires, by the year migration starts.`}
      />
      <p className="mb-2 text-subhead text-label-2">
        Starting today: <strong className="font-semibold tabular text-label">{formatPercent(today)}</strong>. Starting in five years:{" "}
        <strong className="font-semibold tabular text-label">{formatPercent(inFive)}</strong>.
        {latestStart < model.now ? " The latest start within tolerance has already passed." : ` Start by ${formatDecimalYear(latestStart)} to stay within tolerance.`}
      </p>
      <ProbabilityCurve
        ariaLabel={`Exposure probability for ${system.name} by migration start year`}
        series={[{ id: "exposure", label: "Chance of exposure", color: series[0], points: curve, emphasis: true }]}
        domain={[model.now, model.now + 12]}
        tolerance={model.tolerance}
        marker={latestStart >= model.now ? { year: latestStart, p: model.tolerance, title: "Latest safe start", value: formatDecimalYear(latestStart) } : undefined}
        height={260}
        readout="Chance of exposure if migration starts then"
      />
    </Card>
  );
}
