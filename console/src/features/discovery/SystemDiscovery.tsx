import { ArrowRight, Ellipsis, History, Pencil, Play, Plus, Radar, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Button, IconButton } from "@/design/components/Button";
import { TextField } from "@/design/components/Field";
import { Menu, MenuContent, MenuItem, MenuSeparator, MenuTrigger, Tooltip } from "@/design/components/Menu";
import { Confirm, Sheet } from "@/design/components/Sheet";
import { Card, CardHeader, EmptyState, Skeleton } from "@/design/components/Surface";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { useCan } from "@/lib/access";
import { formatInt, formatRelative } from "@/lib/format";
import { useInventorySummary, useRemoveSource, useRenameSource, useSources, useStartScan } from "@/lib/queries";
import type { Source, SystemRecord } from "@/lib/types";
import { Meter } from "@/viz/charts/Meter";
import { SystemRiskCard } from "../risk/SystemRiskCard";
import { AddSourceSheet } from "./AddSourceSheet";
import { ASSESSED, KIND_ORDER, KindGlyph, KINDS, QUANTUM, QUANTUM_ORDER, ScanStatusBadge, SourceGlyph } from "./vocab";

/** The cryptography of one system: what was found, and where FALCON looks. */
export function SystemDiscovery({ system }: { system: SystemRecord }) {
  const canRead = useCan("inventory.read");
  const [adding, setAdding] = useState(false);
  if (!canRead) return null;
  return (
    <>
      <SystemRiskCard system={system} />
      <InventorySnapshot system={system} />
      <SourcesCard system={system} onAdd={() => setAdding(true)} />
      <AddSourceSheet open={adding} onOpenChange={setAdding} system={system} />
    </>
  );
}

function InventorySnapshot({ system }: { system: SystemRecord }) {
  const navigate = useNavigate();
  const summary = useInventorySummary(system.id);
  const data = summary.data;
  if (!data || data.total === 0) return null;
  const segments = QUANTUM_ORDER.map((q) => ({
    key: q,
    label: QUANTUM[q].label,
    color: QUANTUM[q].color,
    value: ASSESSED.reduce((n, k) => n + (data.matrix[k]?.[q] ?? 0), 0),
  })).filter((s) => s.key !== "unknown" || s.value > 0);

  return (
    <Card>
      <CardHeader
        title="Cryptography"
        subtitle={`${formatInt(data.total)} artefacts discovered${system.inventory?.last_scan_at ? `, last scanned ${formatRelative(system.inventory.last_scan_at)}` : ""}.`}
        actions={
          <Button variant="plain" size="sm" trailingIcon={<ArrowRight />} onClick={() => navigate(`/inventory?system=${system.id}`)}>
            Inventory
          </Button>
        }
      />
      <div className="mb-5 grid grid-cols-4 gap-2 sm:grid-cols-7">
        {KIND_ORDER.map((kind) => (
          <button
            key={kind}
            type="button"
            onClick={() => navigate(`/inventory?system=${system.id}&kind=${kind}`)}
            className="flex flex-col items-center gap-1 rounded-[12px] px-1 py-2.5 text-center transition-colors hover:bg-fill-2 focus-visible:focus-ring"
            title={KINDS[kind].summary}
          >
            <KindGlyph kind={kind} size={28} />
            <span className={data.by_kind[kind] ? "text-headline tabular text-label" : "text-headline tabular text-label-4"}>{formatInt(data.by_kind[kind] ?? 0)}</span>
            <span className="w-full truncate text-caption text-label-3">{KINDS[kind].label}</span>
          </button>
        ))}
      </div>
      <div className="mb-2 text-footnote font-semibold text-label-2">Quantum status</div>
      <Meter segments={segments} unit="artefacts" ariaLabel={`Quantum status of ${system.name}'s artefacts: ${segments.map((s) => `${s.label} ${s.value}`).join(", ")}`} />
    </Card>
  );
}

function SourcesCard({ system, onAdd }: { system: SystemRecord; onAdd: () => void }) {
  const canManage = useCan("sources.manage");
  const canScan = useCan("scans.run");
  const sources = useSources(system.id);

  return (
    <Card padded={false}>
      <div className="px-5 pt-5">
        <CardHeader
          title="Sources"
          subtitle="Where FALCON looks for this system’s cryptography."
          actions={
            canManage && (
              <Button variant="tinted" size="sm" icon={<Plus />} onClick={onAdd}>
                Add source
              </Button>
            )
          }
        />
      </div>
      {sources.isPending ? (
        <div className="space-y-3 px-5 pb-5">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : !sources.data?.length ? (
        <EmptyState
          compact
          icon={<Radar />}
          title="Nothing scanned yet"
          message={`Add ${system.name}’s code, build artefacts, container images or live endpoints. FALCON discovers the algorithms, keys, certificates, protocols and libraries inside.`}
          action={canManage && <Button variant="filled" icon={<Plus />} onClick={onAdd}>Add a source</Button>}
        />
      ) : (
        <ul className="pb-1.5">
          {sources.data.map((source) => (
            <SourceRow key={source.id} source={source} canManage={canManage} canScan={canScan} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function SourceRow({ source, canManage, canScan }: { source: Source; canManage: boolean; canScan: boolean }) {
  const navigate = useNavigate();
  const start = useStartScan();
  const remove = useRemoveSource();
  const [renaming, setRenaming] = useState(false);
  const [removing, setRemoving] = useState(false);
  const active = source.active_scan;
  const last = source.last_scan;
  const open = active ?? last;

  const scan = () =>
    start.mutate(source.id, {
      onSuccess: (s) => navigate(`/scans/${s.id}`),
      onError: (e) => toast.error(e.message),
    });

  return (
    <li className="relative px-2 [&+&]:before:absolute [&+&]:before:inset-x-5 [&+&]:before:top-0 [&+&]:before:h-px [&+&]:before:bg-separator">
      <div className="flex items-center gap-3 rounded-[12px] px-3 py-3">
        <button type="button" disabled={!open} onClick={() => open && navigate(`/scans/${open.id}`)} className="flex min-w-0 flex-1 items-center gap-3 rounded-[8px] text-left focus-visible:focus-ring">
          <SourceGlyph kind={source.kind} size={36} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-callout font-medium text-label">{source.name}</span>
            <span className="block truncate font-mono text-caption text-label-3" title={source.locator}>
              {source.locator.split("\n").join(", ")}
            </span>
          </span>
          <span className="hidden shrink-0 text-right sm:block">
            {active ? (
              <span className="flex items-center gap-2 text-footnote font-medium text-accent-ink">
                <ActivityIndicator size={13} label="Scanning" />
                {active.files_total ? `${Math.round((active.files_done / active.files_total) * 100)}%` : active.status === "queued" ? "Queued" : "Preparing"}
              </span>
            ) : last ? (
              <>
                {last.status === "succeeded" ? (
                  <span className="block text-footnote font-medium text-label">{formatInt(last.artefacts)} artefacts</span>
                ) : (
                  <ScanStatusBadge status={last.status} />
                )}
                <span className="block text-caption text-label-3">{formatRelative(last.finished_at ?? last.queued_at)}</span>
              </>
            ) : (
              <span className="text-footnote text-label-3">Not scanned</span>
            )}
          </span>
        </button>
        {canScan && !active && (
          <Tooltip content="Scan now">
            <IconButton label={`Scan ${source.name} now`} onClick={scan} disabled={start.isPending}>
              {start.isPending ? <ActivityIndicator size={14} /> : <Play />}
            </IconButton>
          </Tooltip>
        )}
        {(canManage || last) && (
          <Menu>
            <MenuTrigger asChild>
              <IconButton label={`More actions for ${source.name}`}>
                <Ellipsis />
              </IconButton>
            </MenuTrigger>
            <MenuContent>
              {last && (
                <MenuItem icon={<History />} onSelect={() => navigate(`/scans/${last.id}`)}>
                  Latest scan
                </MenuItem>
              )}
              {canManage && (
                <>
                  <MenuItem icon={<Pencil />} onSelect={() => setRenaming(true)}>
                    Rename
                  </MenuItem>
                  <MenuSeparator />
                  <MenuItem destructive icon={<Trash2 />} disabled={!!active} onSelect={() => setRemoving(true)}>
                    Remove source
                  </MenuItem>
                </>
              )}
            </MenuContent>
          </Menu>
        )}
      </div>
      <RenameSheet source={source} open={renaming} onOpenChange={setRenaming} />
      <Confirm
        open={removing}
        onOpenChange={setRemoving}
        title={`Remove ${source.name}?`}
        message="Its scans and evidence are removed, and artefacts found only here leave the inventory."
        confirmLabel="Remove"
        destructive
        onConfirm={async () => {
          await remove.mutateAsync(source.id);
          toast.success(`${source.name} removed`);
        }}
      />
    </li>
  );
}

function RenameSheet({ source, open, onOpenChange }: { source: Source; open: boolean; onOpenChange: (open: boolean) => void }) {
  const rename = useRenameSource();
  const [name, setName] = useState(source.name);
  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (next) setName(source.name);
        onOpenChange(next);
      }}
      width={420}
      title="Rename source"
      footer={
        <>
          <Button variant="gray" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="filled"
            loading={rename.isPending}
            disabled={!name.trim() || name.trim() === source.name}
            onClick={() => rename.mutate({ id: source.id, name: name.trim() }, { onSuccess: () => onOpenChange(false), onError: (e) => toast.error(e.message) })}
          >
            Save
          </Button>
        </>
      }
    >
      <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={160} />
    </Sheet>
  );
}
