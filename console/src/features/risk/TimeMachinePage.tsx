import { CalendarClock, Pause, Play, RotateCcw } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Tooltip } from "@/design/components/Menu";
import { Segmented } from "@/design/components/Segmented";
import { Card, CardHeader, Chip, EmptyState } from "@/design/components/Surface";
import { formatDecimalYear, formatInt, formatPercent } from "@/lib/format";
import { useRiskTimeline } from "@/lib/queries";
import type { FrameworkId, RiskTimelinePayload, TimelineArtefact, TimelineEvent } from "@/lib/types";
import { StateArea } from "@/viz/charts/StateArea";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { ChartFrame } from "@/viz/core/ChartFrame";
import { KINDS } from "../discovery/vocab";
import { Page, PageSkeleton } from "../shell/Page";
import { stateAt, TIME_STATES, type TimeState } from "./vocab";

type Lens = "nist" | "cnsa-2.0" | "eu-pqc-roadmap";
const LENSES: { value: Lens; label: string }[] = [
  { value: "nist", label: "NIST" },
  { value: "cnsa-2.0", label: "CNSA 2.0" },
  { value: "eu-pqc-roadmap", label: "EU roadmap" },
];
const PLAY_SECONDS = 9;

/** The artefact's transitions under a policy lens: the lens's deadline can only bring "broken" earlier. */
function transitions(a: TimelineArtefact, lens: Lens) {
  if (lens === "nist") return a.t;
  const deadline = a.policy[lens as FrameworkId];
  if (deadline === undefined) return a.t;
  const broken = a.t.broken === null ? deadline : Math.min(a.t.broken, deadline);
  return { ...a.t, broken, at_risk: a.t.at_risk ?? broken };
}

function probabilityAt(data: RiskTimelinePayload, year: number): number {
  const curve = data.curve;
  if (!curve.length) return 0;
  if (year <= curve[0].year) return curve[0].p;
  for (let i = 1; i < curve.length; i++) {
    if (curve[i].year >= year) {
      const a = curve[i - 1];
      const b = curve[i];
      return a.p + ((b.p - a.p) * (year - a.year)) / (b.year - a.year || 1);
    }
  }
  return curve[curve.length - 1].p;
}

export default function TimeMachinePage() {
  const timeline = useRiskTimeline();
  if (timeline.isPending) return <PageSkeleton />;
  const data = timeline.data;
  if (!data || data.artefacts.length === 0) {
    return (
      <Page title="Quantum Time Machine">
        <Card>
          <EmptyState icon={<CalendarClock />} title="Nothing to replay yet" message="The time machine replays the discovered inventory. Scan a system first." />
        </Card>
      </Page>
    );
  }
  return <Machine data={data} />;
}

function Machine({ data }: { data: RiskTimelinePayload }) {
  const reduce = useReducedMotion();
  const start = data.model.now;
  const end = data.until + 1;
  const [year, setYear] = useState(start);
  const [playing, setPlaying] = useState(false);
  const [lens, setLens] = useState<Lens>("nist");

  // Playback: sweep from the current year to the end in PLAY_SECONDS.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setYear((y) => {
        const next = y + (dt * (end - start)) / PLAY_SECONDS;
        if (next >= end) {
          setPlaying(false);
          return end;
        }
        return next;
      });
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playing, start, end]);

  const states = useMemo(() => data.artefacts.map((a) => ({ a, t: transitions(a, lens) })), [data, lens]);
  const counts = useMemo(() => {
    const c: Record<TimeState, number> = { secure: 0, "at-risk": 0, exposed: 0, broken: 0 };
    states.forEach(({ t }) => (c[stateAt(t, year)] += 1));
    return c;
  }, [states, year]);
  const samples = useMemo(() => {
    const out = [];
    for (let y = start; y <= end + 1e-6; y += 0.25) {
      const c: Record<string, number> = { secure: 0, "at-risk": 0, exposed: 0, broken: 0 };
      states.forEach(({ t }) => (c[stateAt(t, y)] += 1));
      out.push({ year: y, counts: c });
    }
    return out;
  }, [states, start, end]);

  const probability = probabilityAt(data, year);
  const total = data.artefacts.length;
  const events = data.events.filter((e) => lens === "nist" ? !e.framework || e.framework.startsWith("nist") : !e.framework || e.framework === lens || e.framework.startsWith("nist"));
  const now = events.filter((e) => Math.abs(e.year - year) <= 0.5);
  const upcoming = events.filter((e) => e.year > year + 0.5).slice(0, 6);
  const past = events.filter((e) => e.year < year - 0.5).length;

  return (
    <Page
      title="Quantum Time Machine"
      subtitle="Replay your cryptographic estate year by year: when each artefact becomes exposed to harvest-now-decrypt-later, when policy disallows it, and when a quantum adversary becomes more likely than your tolerance."
      width="wide"
    >
      <div className="space-y-4">
        <Card className="overflow-hidden">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div>
              <div className="flex items-center gap-3">
                <Button
                  variant="filled"
                  size="lg"
                  icon={playing ? <Pause className="fill-current" /> : <Play className="fill-current" />}
                  onClick={() => {
                    if (!playing && year >= end - 0.01) setYear(start);
                    setPlaying((p) => !p);
                  }}
                >
                  {playing ? "Pause" : year >= end - 0.01 ? "Replay" : "Play"}
                </Button>
                <Button variant="gray" size="lg" icon={<RotateCcw />} onClick={() => { setPlaying(false); setYear(start); }} disabled={year === start}>
                  Today
                </Button>
                <div className="ml-2 hidden sm:block">
                  <Segmented label="Policy lens" value={lens} onChange={setLens} options={LENSES} />
                </div>
              </div>
              <motion.div
                key={Math.floor(year)}
                initial={reduce ? false : { opacity: 0.4, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="mt-5 text-[64px] font-semibold leading-none tracking-[-0.04em] tabular text-label max-sm:text-[48px]"
              >
                {formatDecimalYear(year)}
              </motion.div>
              <p className="mt-2 text-subhead text-label-2">
                {year - start < 0.05 ? "Today." : `${(year - start).toFixed(1)} years from today.`} A {formatPercent(probability)} chance a cryptographically relevant quantum computer exists by then
                {year >= data.model.planning_year ? " — beyond your planning horizon." : "."}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
              {TIME_STATES.map((s) => (
                <div key={s.key} className="min-w-[120px]">
                  <dt className="flex items-center gap-1.5 text-footnote font-medium text-label-3">
                    <span className="size-2.5 rounded-[3px]" style={{ background: s.color }} /> {s.label}
                  </dt>
                  <dd>
                    <AnimatedNumber value={counts[s.key]} format={(n) => formatInt(Math.round(n))} className="block text-title-1 tabular text-label" />
                    <span className="text-caption text-label-3">{formatPercent(counts[s.key] / total, 0)} of artefacts</span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>
          <YearScrubber start={start} end={end} year={year} events={events} planningYear={data.model.planning_year} onChange={(y) => { setPlaying(false); setYear(y); }} />
        </Card>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <ChartFrame
            title="The estate over time"
            subtitle="Artefacts in each state by year. Drag across the chart to travel."
            legend={[...TIME_STATES].map((s) => ({ label: s.label, color: s.color }))}
            table={{
              caption: "Artefacts in each state, by year",
              rows: samples.filter((s) => Math.abs(s.year - Math.round(s.year)) < 0.01),
              rowKey: (s) => String(s.year),
              columns: [
                { key: "y", header: "Year", cell: (s) => Math.round(s.year) },
                ...TIME_STATES.map((st) => ({ key: st.key, header: st.label, numeric: true, cell: (s: (typeof samples)[number]) => formatInt(s.counts[st.key]) })),
              ],
            }}
          >
            <StateArea
              ariaLabel="Artefacts by state over time"
              samples={samples}
              series={[...TIME_STATES].map((s) => ({ key: s.key, label: s.label, color: s.color }))}
              year={year}
              markers={[
                { year: data.model.planning_year, label: "Planning horizon (Z)", tone: "critical" as const },
                ...events.filter((e) => e.kind === "policy").map((e) => ({ year: e.year, label: e.title, tone: "neutral" as const })),
              ]}
              onScrub={(y) => { setPlaying(false); setYear(y); }}
              height={280}
            />
          </ChartFrame>
          <Card>
            <CardHeader title={`In ${Math.floor(year)}`} subtitle={now.length ? "What changes around this year." : "No milestones this year."} />
            <ul className="space-y-3">
              {now.map((e) => (
                <EventRow key={`${e.year}${e.title}`} event={e} />
              ))}
            </ul>
            {upcoming.length > 0 && (
              <>
                <div className="mb-2 mt-5 text-footnote font-semibold text-label-3">Next</div>
                <ul className="space-y-1">
                  {upcoming.map((e) => (
                    <li key={`${e.year}${e.title}`}>
                      <button type="button" onClick={() => { setPlaying(false); setYear(e.year); }} className="hover-light flex w-full items-start gap-3 rounded-[10px] px-2 py-1.5 text-left transition-colors hover:bg-fill-2">
                        <span className="w-14 shrink-0 pt-px text-footnote font-semibold tabular text-label-2">{formatDecimalYear(e.year).split(" ")[1]}</span>
                        <span className="text-footnote text-label">{e.title}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {past > 0 && <p className="mt-4 text-caption text-label-3">{past} earlier milestone{past === 1 ? "" : "s"} already passed on this timeline.</p>}
          </Card>
        </div>

        <EstateGrid data={data} states={states} year={year} />
      </div>
    </Page>
  );
}

function EventRow({ event }: { event: TimelineEvent }) {
  const tone = event.kind === "horizon" ? "var(--status-critical)" : event.kind === "policy" ? "var(--status-serious)" : "var(--accent)";
  return (
    <li className="flex gap-3">
      <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: tone }} />
      <div className="min-w-0">
        <div className="text-callout font-medium text-label">{event.title}</div>
        <div className="text-footnote text-label-3">
          {formatDecimalYear(event.year)} · {event.detail}
        </div>
      </div>
    </li>
  );
}

/* ----------------------------------------------------------------- scrubber */

function YearScrubber({ start, end, year, events, planningYear, onChange }: { start: number; end: number; year: number; events: TimelineEvent[]; planningYear: number; onChange: (y: number) => void }) {
  const track = useRef<HTMLDivElement>(null);
  const pct = (y: number) => `${((Math.min(end, Math.max(start, y)) - start) / (end - start)) * 100}%`;
  const fromPointer = (e: PointerEvent) => {
    const box = track.current!.getBoundingClientRect();
    onChange(start + Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)) * (end - start));
  };
  const years: number[] = [];
  for (let y = Math.ceil(start); y <= end; y++) years.push(y);
  return (
    <div className="mt-7">
      <div
        ref={track}
        role="slider"
        tabIndex={0}
        aria-label="Year"
        aria-valuemin={Math.floor(start)}
        aria-valuemax={Math.floor(end)}
        aria-valuenow={Math.floor(year)}
        aria-valuetext={formatDecimalYear(year)}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId);
          fromPointer(e);
        }}
        onPointerMove={(e) => e.buttons === 1 && fromPointer(e)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") onChange(Math.min(end, year + 1));
          if (e.key === "ArrowLeft") onChange(Math.max(start, year - 1));
          if (e.key === "Home") onChange(start);
          if (e.key === "End") onChange(end);
        }}
        className="group relative h-10 cursor-ew-resize rounded-full focus-visible:focus-ring"
      >
        <div className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-fill" />
        <div className="absolute left-0 top-1/2 h-2 -translate-y-1/2 rounded-full bg-accent" style={{ width: pct(year) }} />
        <div className="absolute top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-[var(--status-critical)]" style={{ left: pct(planningYear) }} title="Planning horizon (Z)" />
        {events
          .filter((e) => e.kind === "policy")
          .map((e) => (
            <Tooltip key={`${e.year}${e.title}`} content={`${formatDecimalYear(e.year)} · ${e.title}`}>
              <span className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-label-3" style={{ left: pct(e.year) }} />
            </Tooltip>
          ))}
        <div
          className="absolute top-1/2 size-6 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-thumb transition-transform duration-150 group-active:scale-110"
          style={{ left: pct(year) }}
        />
      </div>
      <div className="relative mt-1 h-4">
        {years.map((y) => (
          <span key={y} className={cn("absolute -translate-x-1/2 text-caption tabular", y % 5 === 0 ? "text-label-2" : "text-label-4 max-sm:hidden")} style={{ left: pct(y) }}>
            {y}
          </span>
        ))}
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- the estate */

function EstateGrid({ data, states, year }: { data: RiskTimelinePayload; states: { a: TimelineArtefact; t: TimelineArtefact["t"] }[]; year: number }) {
  const navigate = useNavigate();
  const colors = Object.fromEntries(TIME_STATES.map((s) => [s.key, s.color]));
  const bySystem = data.systems
    .map((s) => ({ system: s, items: states.filter((x) => x.a.system_id === s.id) }))
    .filter((g) => g.items.length > 0);
  return (
    <Card>
      <CardHeader title="Every artefact" subtitle="One square per artefact, grouped by system. Watch the estate change as you travel." />
      <div className="space-y-4">
        {bySystem.map(({ system, items }) => (
          <div key={system.id} className="grid gap-3 sm:grid-cols-[200px_1fr]">
            <button type="button" onClick={() => navigate(`/systems/${system.id}`)} className="hover-light flex items-center gap-2 self-start rounded-[8px] px-1 py-0.5 text-left">
              <Chip>{system.code}</Chip>
              <span className="truncate text-subhead text-label">{system.name}</span>
            </button>
            <div className="flex flex-wrap gap-[3px]">
              {items.map(({ a, t }) => {
                const state = stateAt(t, year);
                return (
                  <Tooltip key={a.id} content={`${a.name} · ${KINDS[a.kind].singular} · ${TIME_STATES.find((s) => s.key === state)!.label}`}>
                    <button
                      type="button"
                      aria-label={`${a.name}: ${state}`}
                      onClick={() => navigate(`/inventory/${a.id}`)}
                      className="size-[14px] rounded-[4px] transition-[background-color,transform] duration-500 hover:scale-125"
                      style={{ background: colors[state] }}
                    />
                  </Tooltip>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
