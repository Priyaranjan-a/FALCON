import { ChevronDown, FlaskConical, Network, Route, SlidersHorizontal } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Badge, Card, Chip, EmptyState } from "@/design/components/Surface";
import { Button } from "@/design/components/Button";
import { spring } from "@/design/motion";
import { formatDecimalYear, formatInt, formatPercent, formatYears } from "@/lib/format";
import { useMigrationPlan } from "@/lib/queries";
import type { MigrationPlan, Wave } from "@/lib/types";
import { Roadmap } from "@/viz/charts/Roadmap";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { ChartFrame } from "@/viz/core/ChartFrame";
import { KindGlyph } from "../discovery/vocab";
import { RiskBadge } from "../risk/vocab";
import { Page, PageSkeleton } from "../shell/Page";
import { ACTIONS, WAVE_ORDER, WAVES } from "./vocab";

export default function MigrationPage() {
  const navigate = useNavigate();
  const plan = useMigrationPlan();
  if (plan.isPending) return <PageSkeleton />;
  const data = plan.data;
  return (
    <Page
      title="Migration Plan"
      subtitle="Every artefact with a post-quantum or hybrid replacement, grouped into waves and scheduled per system against your planning horizon and the policy deadlines."
      width="wide"
      actions={
        <>
          <Button variant="gray" icon={<Network />} onClick={() => navigate("/blast-radius")}>
            Blast radius
          </Button>
          <Button variant="gray" icon={<SlidersHorizontal />} onClick={() => navigate("/simulator")}>
            What-if
          </Button>
          <Button variant="gray" icon={<FlaskConical />} onClick={() => navigate("/lab")}>
            Benchmark lab
          </Button>
        </>
      }
    >
      {!data || data.totals.artefacts === 0 ? (
        <Card>
          <EmptyState icon={<Route />} title="Nothing to migrate" message="Either nothing has been scanned yet, or everything found is already quantum-safe." />
        </Card>
      ) : (
        <div className="space-y-4">
          <Headline data={data} />
          <ChartFrame
            title="Roadmap"
            subtitle="Each system’s work by wave. Waves 1–3 start now in parallel; the rest follow. The red rule is the planning horizon; dashed rules are NIST’s 2030 deprecation and 2035 disallowance."
            legend={WAVE_ORDER.map((k) => ({ label: WAVES[k].label, color: WAVES[k].color }))}
            table={{
              caption: "Roadmap by system and wave",
              rows: data.lanes.flatMap((l) => l.bars.map((b) => ({ ...b, system: l.system }))),
              rowKey: (r) => `${r.system.id}-${r.wave}`,
              columns: [
                { key: "s", header: "System", cell: (r) => r.system.code },
                { key: "w", header: "Wave", cell: (r) => WAVES[r.wave].label },
                { key: "a", header: "Start", cell: (r) => formatDecimalYear(r.start) },
                { key: "b", header: "Finish", cell: (r) => formatDecimalYear(r.finish) },
                { key: "n", header: "Artefacts", numeric: true, cell: (r) => r.count },
              ],
            }}
          >
            <Roadmap
              ariaLabel="Migration roadmap by system and wave"
              domain={[Math.floor(data.model.now * 4) / 4, Math.max(Math.ceil(Math.max(data.completion, data.horizon, 2036.2)), 2037)]}
              tracks={WAVE_ORDER.map((k) => ({ key: k, label: WAVES[k].label, color: WAVES[k].color }))}
              lanes={data.lanes.map((l) => ({ id: l.system.id, label: l.system.code, sublabel: l.system.name, bars: l.bars.map((b) => ({ track: b.wave, start: b.start, finish: b.finish, count: b.count })) }))}
              markers={[
                { year: data.horizon, label: "Planning horizon (Z)", tone: "critical" },
                { year: 2031, label: "NIST IR 8547: 112-bit deprecated", tone: "neutral" },
                { year: 2036, label: "NIST IR 8547: disallowed", tone: "neutral" },
              ]}
              onSelect={(_, wave) => document.getElementById(`wave-${wave}`)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            />
          </ChartFrame>
          <div className="space-y-3">
            {data.waves.map((w, i) => (
              <WaveCard key={w.key} wave={w} index={i + 1} />
            ))}
          </div>
        </div>
      )}
    </Page>
  );
}

function Headline({ data }: { data: MigrationPlan }) {
  const late = data.completion > data.horizon;
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <Card>
        <div className="text-subhead font-medium text-label-2">To migrate</div>
        <AnimatedNumber value={data.totals.artefacts} format={(n) => formatInt(Math.round(n))} className="mt-3 block text-title-1 text-label" />
        <p className="mt-1 text-footnote text-label-3">
          Across {data.totals.systems} system{data.totals.systems === 1 ? "" : "s"}; {formatYears(data.totals.effort_years)} of effort in total.
        </p>
      </Card>
      <Card>
        <div className="text-subhead font-medium text-label-2">Programme completes</div>
        <div className="mt-3 text-title-1 text-label">{formatDecimalYear(data.completion)}</div>
        <p className="mt-1 text-footnote text-label-3">
          {late ? "After" : "Before"} the planning horizon ({formatDecimalYear(data.horizon)}). {formatPercent(data.completion_probability)} chance a CRQC exists by then.
        </p>
      </Card>
      <Card className="lg:col-span-2">
        <div className="text-subhead font-medium text-label-2">Replacing with</div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {data.totals.targets.map((t) => (
            <span key={t.name} className="inline-flex h-7 items-center gap-2 rounded-full bg-fill-2 px-3 text-footnote font-medium text-label">
              {t.name}
              <span className="tabular text-label-3">{t.count}</span>
            </span>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-footnote text-label-3">
          {Object.entries(data.totals.actions).map(([action, count]) => (
            <span key={action}>
              {ACTIONS[action as keyof typeof ACTIONS]?.label ?? action} <span className="font-semibold tabular text-label-2">{count}</span>
            </span>
          ))}
        </div>
      </Card>
    </div>
  );
}

function WaveCard({ wave, index }: { wave: Wave; index: number }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(index <= 2);
  const meta = WAVES[wave.key];
  return (
    <Card padded={false} id={`wave-${wave.key}`} className="scroll-mt-16 overflow-hidden">
      <button type="button" onClick={() => setOpen((o) => !o)} className="hover-light flex w-full items-center gap-4 px-5 py-4 text-left">
        <span className="grid size-9 shrink-0 place-items-center rounded-[10px] text-headline font-semibold text-white" style={{ background: meta.color }}>
          {index}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-headline text-label">{wave.title}</span>
            {wave.on_time === true && <Badge tone="good">Before its deadline</Badge>}
            {wave.on_time === false && <Badge tone="critical">Misses its deadline</Badge>}
          </span>
          <span className="block text-footnote text-label-3">{wave.summary}</span>
        </span>
        <span className="hidden shrink-0 text-right sm:block">
          <span className="block text-subhead font-semibold tabular text-label">{formatInt(wave.artefacts)} artefacts</span>
          <span className="block text-caption text-label-3">
            {wave.artefacts ? `${formatDecimalYear(wave.start)} – ${formatDecimalYear(wave.finish)}` : "Nothing in this wave"}
          </span>
        </span>
        <ChevronDown className={cn("size-4 shrink-0 text-label-3 transition-transform duration-300", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && wave.items.length > 0 && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={spring.smooth} className="overflow-hidden">
            <ul className="px-2 pb-2">
              {wave.items.map((item) => {
                const Icon = ACTIONS[item.action].icon;
                return (
                  <li key={item.id} className="hairline-t first:shadow-none">
                    <button type="button" onClick={() => navigate(`/inventory/${item.id}`)} className="hover-light grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors hover:bg-fill-2 sm:grid-cols-[auto_minmax(0,1.1fr)_minmax(0,1fr)_auto_auto]">
                      <KindGlyph kind={item.kind} size={28} />
                      <span className="min-w-0">
                        <span className="block truncate text-callout font-medium text-label">{item.name}</span>
                        <span className="flex items-center gap-1.5 text-caption text-label-3">
                          <Chip>{item.system.code}</Chip> {item.effort} · {formatYears(item.years)}
                        </span>
                      </span>
                      <span className="hidden min-w-0 items-center gap-2 text-subhead text-label-2 sm:flex">
                        <Icon className="size-4 shrink-0 text-label-3" />
                        <span className="truncate">{item.recommendation}</span>
                      </span>
                      <span className="hidden sm:block">{item.primary && <Chip className="font-sans">{item.primary}</Chip>}</span>
                      <RiskBadge band={item.band} score={item.score} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
