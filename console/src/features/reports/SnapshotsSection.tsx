import { ArrowDownRight, ArrowRight, ArrowUpRight, CircleCheck, CircleX, Download, FileSignature, ShieldCheck, ShieldX, Signature } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Select } from "@/design/components/Controls";
import { TextField } from "@/design/components/Field";
import { Sheet, SheetSection } from "@/design/components/Sheet";
import { Badge, Banner, Card, CardHeader, Chip, EmptyState, GroupedList, GroupedRow, Skeleton } from "@/design/components/Surface";
import { ease, spring } from "@/design/motion";
import { useCan } from "@/lib/access";
import { saveExport } from "@/lib/exports";
import { formatDateTime, formatInt, formatRelative } from "@/lib/format";
import { useCreateSnapshot, useDrift, useSnapshot, useSnapshots, useSystems } from "@/lib/queries";
import type { Drift, DriftRow, Snapshot, SnapshotDetail } from "@/lib/types";
import { AnimatedNumber } from "@/viz/charts/Stat";
import { QuantumBadge } from "../discovery/vocab";
import { BANDS } from "../risk/vocab";
import { BandStrip, CHECKS, CopyButton, DRIFT_VERDICT, groupHex } from "./vocab";

/** Signed snapshots: the list, the selected snapshot with its verification, and drift from it. */
export function SnapshotsSection({ signOpen, onSignOpenChange }: { signOpen: boolean; onSignOpenChange: (open: boolean) => void }) {
  const snapshots = useSnapshots();
  const [selected, setSelected] = useState<string | null>(null);
  const items = snapshots.data ?? [];
  const current = selected && items.some((s) => s.id === selected) ? selected : items[0]?.id ?? null;
  const canSign = useCan("reports.sign");

  return (
    <>
      <Card className="mt-4">
        <CardHeader
          title="Signed snapshots"
          subtitle="The CBOM at a moment, signed with the organisation’s ML-DSA-65 key (FIPS 204) in a DSSE envelope. Anyone with the public key can prove what the inventory was, and that it has not changed since."
        />
        {snapshots.isPending ? (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <Skeleton className="h-[320px] rounded-[14px]" />
            <Skeleton className="h-[320px] rounded-[14px]" />
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<FileSignature />}
            title="No snapshots yet"
            message="Sign a snapshot to fix today’s inventory as evidence: for an audit, a board report, or a baseline to measure migration against."
            action={canSign && <Button variant="filled" icon={<Signature />} onClick={() => onSignOpenChange(true)}>Sign a snapshot</Button>}
          />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <SnapshotList items={items} selected={current} onSelect={setSelected} />
            <div className="min-w-0">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={current}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -6, transition: { duration: 0.12 } }}
                  transition={{ duration: 0.3, ease: ease.out }}
                >
                  {current && <SnapshotPanel id={current} />}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        )}
      </Card>
      {current && items.length > 0 && <DriftCard base={items.find((s) => s.id === current)!} snapshots={items} />}
      <SignSheet open={signOpen} onOpenChange={onSignOpenChange} onSigned={(s) => setSelected(s.id)} />
    </>
  );
}

function SnapshotList({ items, selected, onSelect }: { items: Snapshot[]; selected: string | null; onSelect: (id: string) => void }) {
  return (
    <ul className="-mx-1 max-h-[460px] space-y-0.5 overflow-y-auto px-1" aria-label="Snapshots">
      {items.map((s) => {
        const active = s.id === selected;
        return (
          <li key={s.id}>
            <button
              type="button"
              onClick={() => onSelect(s.id)}
              aria-current={active || undefined}
              className={cn(
                "hover-light relative flex w-full items-start gap-3 rounded-[12px] px-3 py-2.5 text-left transition-colors duration-150 focus-visible:focus-ring",
                !active && "hover:bg-fill-2",
              )}
            >
              {active && <motion.span layoutId="snapshot-selection" transition={spring.smooth} className="absolute inset-0 rounded-[12px] bg-accent-tint" />}
              <span className="relative grid size-9 shrink-0 place-items-center rounded-[10px] bg-[var(--status-good-tint)] text-good">
                <ShieldCheck className="size-[18px]" />
              </span>
              <span className="relative min-w-0 flex-1">
                <span className="block truncate text-callout font-medium text-label">{s.label}</span>
                <span className="block truncate text-footnote text-label-3">
                  {formatRelative(s.created_at)} · {s.created_by ?? "system"} · {formatInt(s.summary.artefacts)} artefacts
                </span>
                <BandStrip bands={s.summary.bands} className="mt-2" />
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function SnapshotPanel({ id }: { id: string }) {
  const detail = useSnapshot(id);
  if (detail.isPending) return <Skeleton className="h-[320px] rounded-[14px]" />;
  if (!detail.data) return null;
  return <SnapshotDetailView s={detail.data} />;
}

function SnapshotDetailView({ s }: { s: SnapshotDetail }) {
  const v = s.verification;
  const [busy, setBusy] = useState<"cbom" | "envelope" | null>(null);
  const get = async (part: "cbom" | "envelope") => {
    setBusy(part);
    try {
      await saveExport({ kind: "snapshot", snapshot_id: s.id, part });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const bands = s.summary.bands;
  return (
    <div className="rounded-[14px] bg-[var(--fill-2)] p-4 shadow-[inset_0_0_0_0.5px_var(--separator)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-title-3 text-label">{s.label}</div>
          <div className="text-footnote text-label-3">
            Signed {formatDateTime(s.created_at)} by {s.created_by ?? "system"} · {s.summary.scope}
          </div>
        </div>
        <VerifiedSeal valid={v.valid} />
      </div>

      <ol className="mt-4 grid grid-cols-1 gap-1.5 sm:grid-cols-2" aria-label="Verification">
        {v.checks.map((c, i) => (
          <motion.li
            key={c.check}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + i * 0.09, duration: 0.3, ease: ease.out }}
            className="flex min-w-0 items-start gap-2 rounded-[10px] bg-[var(--surface)] px-3 py-2 shadow-[inset_0_0_0_0.5px_var(--separator)]"
            title={c.detail}
          >
            {c.ok ? <CircleCheck className="mt-px size-4 shrink-0 text-good" /> : <CircleX className="mt-px size-4 shrink-0 text-critical" />}
            <span className="min-w-0">
              <span className="block text-subhead font-medium text-label">{CHECKS[c.check]}</span>
              <span className="block truncate text-caption text-label-3">{c.detail}</span>
            </span>
          </motion.li>
        ))}
      </ol>
      {v.stored_matches === false && (
        <Banner tone="critical" className="mt-3" title="The stored CBOM differs from what was signed">
          The record may have been altered after signing. Treat this snapshot as untrusted.
        </Banner>
      )}

      <GroupedList className="mt-4">
        <GroupedRow label="SHA-256" value={<span className="flex items-center justify-end gap-1 font-mono text-footnote tabular text-label"><span className="max-sm:hidden">{groupHex(s.digest, 6)}…</span><span className="sm:hidden">{groupHex(s.digest, 3)}…</span> <CopyButton text={s.digest} label="Copy digest" /></span>} />
        <GroupedRow label="Signing key" value={<span className="font-mono text-footnote text-label">{groupHex(s.key_id, 4)}</span>} />
        <GroupedRow label="Components" value={formatInt(s.components)} />
        <GroupedRow
          label="Risk at signing"
          value={
            <span className="flex flex-wrap justify-end gap-1.5">
              {(["critical", "high"] as const).map((b) => (
                <Badge key={b} tone={BANDS[b].tone}>
                  {formatInt(bands[b] ?? 0)} {BANDS[b].label.toLowerCase()}
                </Badge>
              ))}
              <Badge tone={s.summary.hndl_exposed ? "critical" : "good"}>{formatInt(s.summary.hndl_exposed)} HNDL</Badge>
            </span>
          }
        />
      </GroupedList>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="bordered" icon={<Download />} loading={busy === "cbom"} onClick={() => get("cbom")}>
          CycloneDX CBOM
        </Button>
        <Button variant="bordered" icon={<FileSignature />} loading={busy === "envelope"} onClick={() => get("envelope")}>
          Signed attestation
        </Button>
      </div>
    </div>
  );
}

function VerifiedSeal({ valid }: { valid: boolean }) {
  return (
    <motion.span
      initial={{ scale: 0.7, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ ...spring.snappy, delay: 0.45 }}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-subhead font-semibold",
        valid ? "bg-[var(--status-good-tint)] text-label" : "bg-[var(--status-critical-tint)] text-label",
      )}
    >
      {valid ? <ShieldCheck className="size-4 text-good" /> : <ShieldX className="size-4 text-critical" />}
      {valid ? "Verified" : "Not verified"}
    </motion.span>
  );
}

/* ----------------------------------------------------------------- drift */

function DriftCard({ base, snapshots }: { base: Snapshot; snapshots: Snapshot[] }) {
  const [head, setHead] = useState<string>("live");
  useEffect(() => setHead("live"), [base.id]);
  const drift = useDrift(base.id, head === "live" ? null : head);
  const options = [
    { value: "live", label: "Current inventory" },
    ...snapshots.filter((s) => s.id !== base.id).map((s) => ({ value: s.id, label: s.label, description: formatRelative(s.created_at) })),
  ];
  const d = drift.data;
  const verdict = d ? DRIFT_VERDICT[d.verdict] : null;
  return (
    <Card className="mt-4">
      <CardHeader
        title="Drift"
        subtitle={
          <>
            What changed since <span className="font-medium text-label">{base.label}</span>: cryptography retired, introduced or changed in risk. Verified against the signed CBOM.
          </>
        }
        actions={
          <div className="flex items-center gap-2">
            {verdict && <Badge tone={verdict.tone}>{verdict.label}</Badge>}
            <Select value={head} onChange={setHead} options={options} ariaLabel="Compare with" className="w-[220px] max-sm:w-full" />
          </div>
        }
      />
      {!d ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-[96px] rounded-[12px]" />)}
        </div>
      ) : (
        <div className={cn("transition-opacity duration-200", drift.isPlaceholderData && "opacity-60")}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Delta label="Total risk points" before={d.totals.risk_before} after={d.totals.risk_after} goodWhen="down" />
            <Delta label="Quantum-vulnerable" before={d.totals.vulnerable_before} after={d.totals.vulnerable_after} goodWhen="down" />
            <Delta label="Post-quantum or hybrid" before={d.totals.pqc_before} after={d.totals.pqc_after} goodWhen="up" />
          </div>
          <div className="mt-5 grid gap-5 lg:grid-cols-3">
            <DriftList title="Retired" icon={<ArrowDownRight className="size-4 text-label-3" />} rows={d.removed} empty="Nothing retired." />
            <DriftList title="Introduced" icon={<ArrowUpRight className="size-4 text-label-3" />} rows={d.added} empty="Nothing new." />
            <DriftList
              title="Changed"
              icon={<ArrowRight className="size-4 text-label-3" />}
              rows={d.changed.filter((c) => c.direction !== "same")}
              empty={`No change in risk. ${formatInt(d.unchanged)} artefacts identical.`}
              detail={(r) => describeChange(r)}
            />
          </div>
        </div>
      )}
    </Card>
  );
}

function describeChange(r: DriftRow): string {
  const c = r.changes ?? {};
  if (c["quantum-status"]) return `${c["quantum-status"].from ?? "unknown"} → ${c["quantum-status"].to ?? "unknown"}`;
  if (c["risk:band"]) return `risk ${c["risk:band"].from ?? "none"} → ${c["risk:band"].to ?? "none"}`;
  if (c["risk:score"]) return `score ${c["risk:score"].from} → ${c["risk:score"].to}`;
  return Object.keys(c).join(", ");
}

function Delta({ label, before, after, goodWhen }: { label: string; before: number; after: number; goodWhen: "up" | "down" }) {
  const change = after - before;
  const good = change === 0 ? null : (change < 0) === (goodWhen === "down");
  return (
    <div className="rounded-[12px] bg-fill-2 px-4 py-3">
      <div className="text-footnote text-label-3">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <AnimatedNumber value={after} format={(n) => formatInt(Math.round(n))} className="text-title-2 tabular text-label" />
        {change !== 0 && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-full px-1.5 text-footnote font-semibold tabular",
              good ? "bg-[var(--status-good-tint)] text-label" : "bg-[var(--status-critical-tint)] text-label",
            )}
          >
            {change < 0 ? <ArrowDownRight className="size-3.5" /> : <ArrowUpRight className="size-3.5" />}
            {formatInt(Math.abs(change))}
          </span>
        )}
      </div>
      <div className="text-caption text-label-3">was {formatInt(before)}</div>
    </div>
  );
}

function DriftList({ title, icon, rows, empty, detail }: { title: string; icon: ReactNode; rows: DriftRow[]; empty: string; detail?: (r: DriftRow) => string }) {
  const navigate = useNavigate();
  return (
    <div className="min-w-0">
      <div className="mb-1.5 flex items-center gap-1.5 text-footnote font-semibold text-label-2">
        {icon} {title} <span className="font-normal text-label-3">{rows.length}</span>
      </div>
      {rows.length === 0 ? (
        <p className="text-footnote text-label-3">{empty}</p>
      ) : (
        <ul className="max-h-[260px] space-y-0.5 overflow-y-auto">
          {rows.map((r) => (
            <li key={r.ref}>
              <button
                type="button"
                onClick={() => navigate(`/inventory?q=${encodeURIComponent(r.name)}`)}
                className="hover-light flex w-full items-center gap-2 rounded-[8px] px-1.5 py-1 text-left transition-colors hover:bg-fill-2"
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-subhead text-label">{r.name}</span>
                  <span className="block truncate text-caption text-label-3">{detail ? detail(r) : `${r.kind.replace("_", " ")} · ${r.system ?? ""}`}</span>
                </span>
                {r.quantum && <QuantumBadge value={r.quantum} short />}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ sign */

function SignSheet({ open, onOpenChange, onSigned }: { open: boolean; onOpenChange: (open: boolean) => void; onSigned: (s: Snapshot) => void }) {
  const create = useCreateSnapshot();
  const systems = useSystems({ sort: "name" });
  const [label, setLabel] = useState("");
  const [scope, setScope] = useState("all");
  useEffect(() => {
    if (open) {
      setLabel("");
      setScope("all");
    }
  }, [open]);
  const submit = () =>
    create.mutate(
      { label: label.trim() || undefined, system_id: scope === "all" ? null : scope },
      {
        onSuccess: (s) => {
          toast.success("Snapshot signed", { description: `${formatInt(s.summary.artefacts)} artefacts, ML-DSA-65` });
          onSigned(s);
          onOpenChange(false);
        },
        onError: (e) => toast.error(e.message),
      },
    );
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title="Sign a snapshot"
      description="FALCON writes the current inventory as a CycloneDX 1.6 CBOM, hashes it, and signs the hash with the organisation’s post-quantum key."
      width={500}
      footer={
        <>
          <Button variant="gray" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="filled" icon={<Signature />} loading={create.isPending} onClick={submit}>Sign snapshot</Button>
        </>
      }
    >
      <SheetSection>
        <div className="space-y-4">
          <TextField label="Label" placeholder="Quarterly baseline, board report, pre-migration…" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={160} optional />
          <Select
            label="Scope"
            value={scope}
            onChange={setScope}
            options={[{ value: "all", label: "All systems" }, ...(systems.data?.items ?? []).map((s) => ({ value: s.id, label: s.name, description: s.code }))]}
          />
        </div>
      </SheetSection>
      <SheetSection title="What is signed">
        <ul className="space-y-2 text-subhead text-label-2">
          <li className="flex gap-2"><Chip>CBOM</Chip> Every algorithm, key, certificate, protocol and library with its evidence and risk.</li>
          <li className="flex gap-2"><Chip>SHA-256</Chip> The digest of the canonical CBOM, as an in-toto statement.</li>
          <li className="flex gap-2"><Chip>ML-DSA-65</Chip> A FIPS 204 signature over the DSSE envelope, 3,309 bytes.</li>
        </ul>
      </SheetSection>
    </Sheet>
  );
}

export type { Drift };
