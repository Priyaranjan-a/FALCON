import { ChevronRight, Search, ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useDeferredValue, useMemo, useState } from "react";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { TextField } from "@/design/components/Field";
import { Segmented } from "@/design/components/Segmented";
import { Card, EmptyState, Skeleton } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { useCan } from "@/lib/access";
import { formatInt, formatRelative } from "@/lib/format";
import { useAudit, useVerifyLedger } from "@/lib/queries";
import type { AuditEvent, LedgerVerification } from "@/lib/types";
import NotFound from "../shell/NotFound";
import { Page } from "../shell/Page";
import { eventIcon } from "./ActivityFeed";

const CATEGORY_LABELS: Record<string, string> = {
  all: "All",
  identity: "Sign-ins",
  members: "Members",
  tokens: "Tokens",
  organisation: "Organisation",
  systems: "Systems",
  discovery: "Discovery",
  ledger: "Ledger",
};

export default function LedgerPage() {
  const allowed = useCan("audit.read");
  const [category, setCategory] = useState("all");
  const [q, setQ] = useState("");
  const deferredQ = useDeferredValue(q);
  const audit = useAudit({ category: category === "all" ? undefined : category, q: deferredQ.trim() || undefined }, { enabled: allowed });
  const events = useMemo(() => audit.data?.pages.flatMap((p) => p.events) ?? [], [audit.data]);
  const head = audit.data?.pages[0]?.head ?? null;

  if (!allowed) return <NotFound />;

  return (
    <Page title="Audit Ledger" subtitle="Every change in FALCON, in order. Each event is hash-chained to the one before it, so altering, removing or reordering any record is detectable.">
      <IntegrityCard head={head} />

      <div className="mb-4 mt-8 flex flex-wrap items-center gap-2">
        <Segmented label="Category" value={category} onChange={setCategory} options={Object.entries(CATEGORY_LABELS).map(([value, label]) => ({ value, label }))} />
        <TextField aria-label="Search events" placeholder="Search events or people" leading={<Search />} value={q} onChange={(e) => setQ(e.target.value)} containerClassName="ml-auto w-[260px] max-sm:w-full" />
      </div>

      <Card padded={false} className={cn("transition-opacity", audit.isPlaceholderData && "opacity-60")}>
        {audit.isPending ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-11" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <EmptyState compact icon={<Search />} title="No matching events" message="Try another category or search." />
        ) : (
          <div className="px-5 py-2">
            {groupByDay(events).map(([day, items]) => (
              <section key={day}>
                <h3 className="sticky top-[52px] z-[1] -mx-5 bg-[var(--glass-header)] px-5 pb-1.5 pt-3 text-footnote font-semibold text-label-3">{day}</h3>
                <div className="divide-y divide-separator">
                  {items.map((e) => (
                    <LedgerRow key={e.id} event={e} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </Card>
      {audit.hasNextPage && (
        <div className="mt-4 flex justify-center">
          <Button variant="gray" loading={audit.isFetchingNextPage} onClick={() => audit.fetchNextPage()}>
            Load earlier events
          </Button>
        </div>
      )}
    </Page>
  );
}

function groupByDay(events: AuditEvent[]): [string, AuditEvent[]][] {
  const groups = new Map<string, AuditEvent[]>();
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86_400_000).toDateString();
  for (const e of events) {
    const d = new Date(e.occurred_at);
    const key = d.toDateString() === today ? "Today" : d.toDateString() === yesterday ? "Yesterday" : d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    groups.set(key, [...(groups.get(key) ?? []), e]);
  }
  return [...groups.entries()];
}

function LedgerRow({ event }: { event: AuditEvent }) {
  const [open, setOpen] = useState(false);
  const Icon = eventIcon(event.action);
  return (
    <div className="py-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="group -mx-2 flex w-[calc(100%+16px)] items-start gap-3 rounded-[10px] px-2 py-2 text-left outline-none transition-colors hover:bg-fill-2 focus-visible:bg-accent-tint"
      >
        <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-fill-2 text-label-2">
          <Icon className="size-3.5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-callout text-label">{event.summary}</span>
          <span className="mt-0.5 block text-footnote tabular text-label-3">
            <time dateTime={event.occurred_at} title={new Date(event.occurred_at).toLocaleString()}>
              {formatRelative(event.occurred_at)}
            </time>
            {event.ip && <> · {event.ip}</>} · #{formatInt(event.seq)}
          </span>
        </span>
        <ChevronRight className={cn("mt-1.5 size-4 shrink-0 text-label-4 transition-transform duration-200 group-hover:text-label-3", open && "rotate-90")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={spring.smooth} className="overflow-hidden">
            <dl className="mb-2 ml-10 mt-1 grid grid-cols-[88px_1fr] gap-x-3 gap-y-1 rounded-[10px] bg-fill-2 p-3 text-footnote">
              <dt className="text-label-3">By</dt>
              <dd className="text-label-2">{event.actor_label}</dd>
              <dt className="text-label-3">Action</dt>
              <dd className="font-mono text-label-2">{event.action}</dd>
              {event.target_type && (
                <>
                  <dt className="text-label-3">Target</dt>
                  <dd className="break-all font-mono text-label-2">
                    {event.target_type}:{event.target_id ?? "—"}
                  </dd>
                </>
              )}
              <dt className="text-label-3">Hash</dt>
              <dd className="break-all font-mono text-label-2">{event.hash}</dd>
              <dt className="text-label-3">Previous</dt>
              <dd className="break-all font-mono text-label-3">{event.prev_hash}</dd>
              {event.detail && (
                <>
                  <dt className="text-label-3">Detail</dt>
                  <dd>
                    <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[11px] leading-4 text-label-2">{JSON.stringify(event.detail, null, 2)}</pre>
                  </dd>
                </>
              )}
            </dl>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const STRIP = 28;

function IntegrityCard({ head }: { head: { seq: number; hash: string } | null }) {
  const verify = useVerifyLedger();
  const [result, setResult] = useState<LedgerVerification | null>(null);
  const [phase, setPhase] = useState<"idle" | "checking" | "done">("idle");
  const chain = useAudit({}, { limit: STRIP });
  const blocks = useMemo(() => [...(chain.data?.pages[0]?.events ?? [])].reverse(), [chain.data]);

  const run = async () => {
    setPhase("checking");
    setResult(null);
    const started = performance.now();
    try {
      const outcome = await verify.mutateAsync();
      // Let the wave finish so the result lands after the animation, not before it.
      const wave = Math.max(0, blocks.length * 35 + 250 - (performance.now() - started));
      setTimeout(() => {
        setResult(outcome);
        setPhase("done");
      }, wave);
    } catch {
      setPhase("idle");
    }
  };

  const state = phase === "done" && result ? (result.valid ? "intact" : "broken") : "unknown";
  const Icon = state === "intact" ? ShieldCheck : state === "broken" ? ShieldAlert : ShieldQuestion;

  return (
    <Card>
      <div className="flex flex-wrap items-start gap-5">
        <div className={cn("grid size-14 shrink-0 place-items-center rounded-[16px] transition-colors duration-300", state === "intact" ? "bg-[var(--status-good-tint)]" : state === "broken" ? "bg-[var(--status-critical-tint)]" : "bg-fill-2")}>
          <Icon className={cn("size-7", state === "intact" ? "text-good" : state === "broken" ? "text-critical" : "text-label-3")} strokeWidth={1.75} />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-title-3 text-label">
            {state === "intact" ? "Ledger intact" : state === "broken" ? "Ledger integrity broken" : "Ledger integrity"}
          </h2>
          <p className="mt-1 text-subhead text-label-2">
            {state === "intact" && result
              ? `All ${formatInt(result.checked)} events recomputed and every link matches, from the genesis block to the head.`
              : state === "broken" && result
                ? `Event #${result.broken_at}: ${result.reason}. Treat the records from this point as untrusted and investigate.`
                : "Recompute every hash from the first event to the latest and confirm nothing has been altered."}
          </p>
          {head && (
            <p className="mt-2 font-mono text-footnote text-label-3">
              Head #{formatInt(head.seq)} · {head.hash.slice(0, 16)}…{head.hash.slice(-8)}
            </p>
          )}
        </div>
        <Button variant={state === "broken" ? "destructive-tinted" : "tinted"} loading={phase === "checking"} onClick={run}>
          {phase === "done" ? "Verify again" : "Verify ledger"}
        </Button>
      </div>

      {blocks.length > 0 && (
        <div className="mt-6 overflow-x-auto pb-1" aria-hidden>
          <div className="flex items-center">
            {blocks.map((e, i) => {
              const broken = result && !result.valid && result.broken_at !== null && e.seq >= result.broken_at;
              const lit = phase !== "idle";
              return (
                <div key={e.id} className="flex items-center">
                  {i > 0 && <span className={cn("h-px w-2.5 transition-colors duration-300", lit ? (broken ? "bg-critical" : "bg-good") : "bg-separator-strong")} style={{ transitionDelay: lit ? `${i * 35}ms` : "0ms" }} />}
                  <motion.div
                    title={`#${e.seq} ${e.hash.slice(0, 12)}…`}
                    className="grid h-7 w-9 shrink-0 place-items-center rounded-[6px] font-mono text-[9.5px] font-medium tabular transition-colors duration-300"
                    style={{
                      transitionDelay: lit ? `${i * 35}ms` : "0ms",
                      background: lit ? (broken ? "var(--status-critical-tint)" : "var(--status-good-tint)") : "var(--fill-2)",
                      color: lit ? "var(--label)" : "var(--label-3)",
                    }}
                    animate={phase === "checking" ? { y: [0, -3, 0] } : { y: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.035 }}
                  >
                    {e.hash.slice(0, 4)}
                  </motion.div>
                </div>
              );
            })}
          </div>
          <p className="mt-2 text-caption text-label-3">
            The latest {blocks.length} events. Each block shows the first characters of its hash, which covers its content and the hash before it.
          </p>
        </div>
      )}
    </Card>
  );
}
