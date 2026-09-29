import { ArrowRight, Radio } from "lucide-react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/design/components/Button";
import { Card, CardHeader } from "@/design/components/Surface";
import { useCan } from "@/lib/access";
import { formatInt, formatYears } from "@/lib/format";
import { useRiskSummary, useUpdateSystem } from "@/lib/queries";
import type { SystemRecord } from "@/lib/types";
import { Meter } from "@/viz/charts/Meter";
import { KindGlyph } from "../discovery/vocab";
import { BAND_ORDER, BANDS, RiskBadge } from "./vocab";

/** A system's quantum risk, and the migration time (Y) its discovered cryptography implies. */
export function SystemRiskCard({ system }: { system: SystemRecord }) {
  const navigate = useNavigate();
  const canWrite = useCan("systems.write");
  const summary = useRiskSummary(system.id);
  const update = useUpdateSystem(system.id);
  const data = summary.data;
  if (!data || data.total === 0) return null;
  const row = data.systems.find((s) => s.id === system.id);
  const estimated = row?.estimated_y ?? null;
  const differs = estimated !== null && Math.abs(estimated - system.migration_years) >= 0.5;

  return (
    <Card>
      <CardHeader
        title="Quantum risk"
        subtitle={`${formatInt(data.bands.critical + data.bands.high)} of ${formatInt(data.total)} artefacts need action this cycle.`}
        actions={
          <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate(`/risk?system=${system.id}`)}>
            Risk
          </Button>
        }
      />
      <Meter
        unit="artefacts"
        ariaLabel={`Risk bands for ${system.name}`}
        segments={BAND_ORDER.map((b) => ({ key: b, label: BANDS[b].label, value: data.bands[b], color: BANDS[b].color }))}
      />
      {data.hndl.exposed > 0 && (
        <div className="mt-4 flex items-start gap-3 rounded-[12px] bg-[var(--status-critical-tint)] px-3.5 py-3">
          <Radio className="mt-0.5 size-[18px] shrink-0 text-critical" />
          <p className="text-subhead text-label">
            <strong className="font-semibold">{data.hndl.exposed} key exchanges are harvestable now.</strong>{" "}
            <span className="text-label-2">Data recorded today stays sensitive for {formatYears(system.data_shelf_life_years)}, beyond the planning horizon.</span>
          </p>
        </div>
      )}
      {differs && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[12px] bg-fill-2 px-3.5 py-3">
          <p className="text-subhead text-label">
            Discovery suggests migration will take <strong className="font-semibold">{formatYears(estimated!)}</strong>; the register says {formatYears(system.migration_years)}.
            <span className="block text-footnote text-label-3">The longest artefact migration, plus coordination for {formatInt(data.assessed)} affected artefacts.</span>
          </p>
          {canWrite && (
            <Button
              variant="tinted"
              size="sm"
              loading={update.isPending}
              onClick={() =>
                update.mutate(
                  { migration_years: Math.round(estimated! * 2) / 2 },
                  { onSuccess: () => toast.success(`Migration time set to ${formatYears(Math.round(estimated! * 2) / 2)}`), onError: (e) => toast.error(e.message) },
                )
              }
            >
              Use {formatYears(Math.round(estimated! * 2) / 2)}
            </Button>
          )}
        </div>
      )}
      {data.top.length > 0 && (
        <>
          <div className="mb-1 mt-5 text-footnote font-semibold text-label-2">Highest risks</div>
          <ul>
            {data.top.slice(0, 5).map((r) => (
              <li key={r.id}>
                <button type="button" onClick={() => navigate(`/inventory/${r.id}`)} className="hover-light -mx-2 flex w-[calc(100%+16px)] items-center gap-3 rounded-[10px] px-2 py-2 text-left transition-colors hover:bg-fill-2">
                  <KindGlyph kind={r.kind} size={26} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-callout font-medium text-label">{r.name}</span>
                    <span className="block truncate text-caption text-label-3">{r.driver}</span>
                  </span>
                  <RiskBadge band={r.band} score={r.score} />
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
