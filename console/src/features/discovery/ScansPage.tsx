import { Radar, Server } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { FacetMenu } from "@/design/components/FacetMenu";
import { Segmented } from "@/design/components/Segmented";
import { Card, Chip, EmptyState, Skeleton } from "@/design/components/Surface";
import { Table, type Column } from "@/design/components/Table";
import { formatInt, formatRelative } from "@/lib/format";
import { useScans, useSystems } from "@/lib/queries";
import type { ScanListItem } from "@/lib/types";
import { Page } from "../shell/Page";
import { formatDuration, ScanStatusBadge, SourceGlyph } from "./vocab";

type StatusFilter = "all" | "active" | "succeeded" | "failed";

const STATUS_QUERY: Record<StatusFilter, string[] | undefined> = {
  all: undefined,
  active: ["queued", "running"],
  succeeded: ["succeeded"],
  failed: ["failed", "cancelled"],
};

export default function ScansPage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [system, setSystem] = useState<string | undefined>();
  const scans = useScans({ status: STATUS_QUERY[status], system });
  const systems = useSystems({ sort: "name" });
  const rows = scans.data ?? [];
  const neverScanned = scans.isSuccess && rows.length === 0 && status === "all" && !system;

  const columns: Column<ScanListItem>[] = [
    {
      key: "source",
      header: "Source",
      cell: (s) => (
        <div className="flex min-w-0 items-center gap-3">
          <SourceGlyph kind={s.source_kind} size={30} />
          <div className="min-w-0">
            <div className="truncate font-medium text-label">{s.source_name}</div>
            <div className="flex min-w-0 items-center gap-1.5 text-footnote text-label-3">
              <Chip className="shrink-0">{s.system_code}</Chip>
              <span className="truncate">{s.source_kind_label}</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (s) =>
        s.status === "running" && s.files_total > 0 ? (
          <div className="w-[140px]">
            <div className="mb-1 flex items-center justify-between text-footnote">
              <span className="font-medium text-label">Scanning</span>
              <span className="tabular text-label-3">{Math.round((s.files_done / s.files_total) * 100)}%</span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-fill">
              <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${(s.files_done / s.files_total) * 100}%` }} />
            </div>
          </div>
        ) : (
          <ScanStatusBadge status={s.status} />
        ),
    },
    { key: "files", header: "Files", numeric: true, hideBelow: "md", cell: (s) => (s.files_total ? formatInt(s.files_total) : "—") },
    {
      key: "artefacts",
      header: "Artefacts",
      numeric: true,
      cell: (s) =>
        s.status === "succeeded" ? (
          <span>
            {formatInt(s.artefacts)}
            {s.new_artefacts > 0 && <span className="ml-1.5 text-footnote text-label-3">+{formatInt(s.new_artefacts)} new</span>}
          </span>
        ) : (
          <span className="text-label-4">—</span>
        ),
    },
    { key: "duration", header: "Duration", numeric: true, hideBelow: "lg", cell: (s) => (s.duration_seconds != null ? formatDuration(s.duration_seconds) : <span className="text-label-4">—</span>) },
    {
      key: "when",
      header: "Started",
      hideBelow: "sm",
      cell: (s) => (
        <div className="text-footnote">
          <div className="text-label-2">{formatRelative(s.started_at ?? s.queued_at)}</div>
          <div className="truncate text-label-3">{s.requested_by ?? "FALCON"}</div>
        </div>
      ),
    },
  ];

  return (
    <Page title="Scans" subtitle="Every discovery run across your systems. Each scan runs in an isolated worker process, and its evidence joins the system’s inventory.">
      {neverScanned ? (
        <Card>
          <EmptyState
            icon={<Radar />}
            title="No scans yet"
            message="Open a system and add a source (a folder, repository, archive, container image or TLS endpoint) to run its first scan."
            action={<Button variant="filled" icon={<Server />} onClick={() => navigate("/systems")}>Choose a system</Button>}
          />
        </Card>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Segmented
              label="Scan status"
              value={status}
              onChange={setStatus}
              options={[
                { value: "all", label: "All" },
                { value: "active", label: "In progress" },
                { value: "succeeded", label: "Completed" },
                { value: "failed", label: "Failed" },
              ]}
            />
            {systems.data && systems.data.items.length > 1 && (
              <FacetMenu
                label={system ? (systems.data.items.find((s) => s.id === system)?.code ?? "System") : "System"}
                selected={system ? [system] : []}
                onChange={(v) => setSystem(v.filter((id) => id !== system)[0])}
                options={systems.data.items.map((s) => ({ value: s.id, label: `${s.code} · ${s.name}` }))}
              />
            )}
          </div>
          <Card padded={false} className={cn("overflow-hidden transition-opacity duration-200", scans.isPlaceholderData && "opacity-60")}>
            {scans.isPending ? (
              <div className="space-y-3 p-5">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : (
              <Table
                caption="Scans"
                columns={columns}
                rows={rows}
                rowKey={(s) => s.id}
                rowLabel={(s) => `Open the scan of ${s.source_name}`}
                onRowClick={(s) => navigate(`/scans/${s.id}`)}
                empty={<EmptyState compact icon={<Radar />} title="No matching scans" message="Try another status or system." />}
              />
            )}
          </Card>
        </>
      )}
    </Page>
  );
}
