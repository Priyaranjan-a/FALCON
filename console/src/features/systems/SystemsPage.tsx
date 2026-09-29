import { ArrowDownWideNarrow, Plus, Search, Server, X } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { TextField } from "@/design/components/Field";
import { FacetMenu } from "@/design/components/FacetMenu";
import { Menu, MenuContent, MenuLabel, MenuRadioGroup, MenuTrigger } from "@/design/components/Menu";
import { Segmented } from "@/design/components/Segmented";
import { Card, Chip, EmptyState, Skeleton } from "@/design/components/Surface";
import { Table, type Column } from "@/design/components/Table";
import { useCan } from "@/lib/access";
import { formatInt, formatPercent, formatRelative } from "@/lib/format";
import { useSystems, useSystemsSummary, useVocabulary, type SystemFilters } from "@/lib/queries";
import type { MoscaStatus, SystemRecord, Vocabulary } from "@/lib/types";
import { Page } from "../shell/Page";
import { CriticalityBars, MiniMosca, MoscaBadge } from "./parts";
import { SystemSheet } from "./SystemSheet";

type Facet = "kind" | "criticality" | "exposure" | "classification";

const FACETS: { key: Facet; label: string; vocab: keyof Vocabulary }[] = [
  { key: "kind", label: "Kind", vocab: "kinds" },
  { key: "criticality", label: "Criticality", vocab: "criticality" },
  { key: "exposure", label: "Exposure", vocab: "exposure" },
  { key: "classification", label: "Data", vocab: "classification" },
];

const SORTS = [
  { value: "exposure", label: "Most exposed" },
  { value: "criticality", label: "Most critical" },
  { value: "name", label: "Name" },
  { value: "code", label: "Code" },
  { value: "updated", label: "Recently updated" },
];

export default function SystemsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const canWrite = useCan("systems.write");
  const vocabulary = useVocabulary().data;
  const summary = useSystemsSummary();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | MoscaStatus>("all");
  const [facets, setFacets] = useState<Record<Facet, string[]>>({ kind: [], criticality: [], exposure: [], classification: [] });
  const [sort, setSort] = useState("exposure");
  const [sheetOpen, setSheetOpen] = useState(false);
  const deferredQ = useDeferredValue(q);

  useEffect(() => {
    if (params.get("register") === "1" && canWrite) {
      setSheetOpen(true);
      params.delete("register");
      setParams(params, { replace: true });
    }
  }, [params, setParams, canWrite]);

  const filters: SystemFilters = useMemo(
    () => ({ q: deferredQ.trim() || undefined, ...facets, status: status === "all" ? undefined : [status], sort }),
    [deferredQ, facets, status, sort],
  );
  const systems = useSystems(filters);
  const items = systems.data?.items ?? [];
  const maxYears = Math.max(10, ...items.map((s) => s.mosca.x + s.mosca.y), ...(items[0] ? [items[0].mosca.z * 1.3] : []));
  const activeFacetCount = Object.values(facets).reduce((n, v) => n + v.length, 0);
  const noSystemsAtAll = summary.data?.total === 0;

  const columns: Column<SystemRecord>[] = [
    {
      key: "system",
      header: "System",
      sortValue: (s) => s.name.toLowerCase(),
      cell: (s) => (
        <div className="flex min-w-0 items-center gap-3">
          <Chip className="shrink-0">{s.code}</Chip>
          <div className="min-w-0">
            <div className="truncate font-medium text-label">{s.name}</div>
            <div className="truncate text-footnote text-label-3">{[s.owner, s.team].filter(Boolean).join(" · ") || "No owner assigned"}</div>
          </div>
        </div>
      ),
    },
    { key: "kind", header: "Kind", hideBelow: "lg", sortValue: (s) => s.kind, cell: (s) => <span className="text-subhead text-label-2">{vocabulary?.kinds[s.kind].label}</span> },
    {
      key: "criticality",
      header: "Criticality",
      hideBelow: "md",
      sortValue: (s) => vocabulary?.criticality[s.criticality].rank ?? 0,
      cell: (s) => <CriticalityBars value={s.criticality} vocabulary={vocabulary} />,
    },
    {
      key: "data",
      header: "Data",
      hideBelow: "lg",
      sortValue: (s) => vocabulary?.classification[s.data_classification].rank ?? 0,
      cell: (s) => <span className="text-subhead text-label-2">{vocabulary?.classification[s.data_classification].label}</span>,
    },
    { key: "mosca", header: "X + Y vs Z", hideBelow: "sm", cell: (s) => <MiniMosca mosca={s.mosca} max={maxYears} /> },
    {
      key: "crypto",
      header: "Cryptography",
      hideBelow: "lg",
      sortValue: (s) => s.inventory?.vulnerable ?? -1,
      cell: (s) =>
        s.inventory?.last_scan_at ? (
          <div className="text-footnote leading-tight">
            <div className="tabular text-label">{formatInt(s.inventory.artefacts)} artefacts</div>
            <div className="tabular text-label-3">{s.inventory.vulnerable ? `${formatInt(s.inventory.vulnerable)} quantum-vulnerable` : "None vulnerable"}</div>
          </div>
        ) : (
          <span className="text-footnote text-label-4">Not scanned</span>
        ),
    },
    { key: "probability", header: "CRQC first", numeric: true, hideBelow: "md", sortValue: (s) => s.mosca.probability, cell: (s) => formatPercent(s.mosca.probability) },
    { key: "status", header: "Status", sortValue: (s) => s.mosca.exposure_years, cell: (s) => <MoscaBadge status={s.mosca.status} /> },
    { key: "updated", header: "Updated", hideBelow: "lg", sortValue: (s) => s.updated_at, cell: (s) => <span className="text-footnote text-label-3">{formatRelative(s.updated_at)}</span> },
  ];

  const counts = summary.data?.mosca;

  return (
    <Page
      title="Systems"
      subtitle="The applications, products and infrastructure whose cryptography FALCON assesses, ranked by quantum exposure under your threat model."
      actions={
        canWrite && (
          <Button variant="filled" icon={<Plus />} onClick={() => setSheetOpen(true)}>
            Register system
          </Button>
        )
      }
    >
      {noSystemsAtAll ? (
        <Card>
          <EmptyState
            icon={<Server />}
            title="No systems registered yet"
            message="Register the systems you depend on. FALCON will place each one against your planning horizon and show which data is already exposed."
            action={canWrite && <Button variant="filled" icon={<Plus />} onClick={() => setSheetOpen(true)}>Register your first system</Button>}
          />
        </Card>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <TextField
              aria-label="Search systems"
              placeholder="Search name, code, owner or tag"
              leading={<Search />}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              containerClassName="w-[280px] max-sm:w-full"
              trailing={
                q && (
                  <button type="button" aria-label="Clear search" onClick={() => setQ("")} className="grid size-6 place-items-center rounded-full text-label-3 hover:text-label-2">
                    <X className="size-3.5" />
                  </button>
                )
              }
            />
            <Segmented
              label="Mosca status"
              value={status}
              onChange={setStatus}
              options={[
                { value: "all", label: `All${summary.data ? ` ${summary.data.active}` : ""}` },
                { value: "exposed", label: `Exposed${counts ? ` ${counts.exposed}` : ""}` },
                { value: "watch", label: `Watch${counts ? ` ${counts.watch}` : ""}` },
                { value: "clear", label: `Clear${counts ? ` ${counts.clear}` : ""}` },
              ]}
            />
            {vocabulary &&
              FACETS.map((facet) => (
                <FacetMenu
                  key={facet.key}
                  label={facet.label}
                  selected={facets[facet.key]}
                  options={Object.entries(vocabulary[facet.vocab]).map(([value, v]) => ({ value, label: v.label }))}
                  onChange={(values) => setFacets((f) => ({ ...f, [facet.key]: values }))}
                />
              ))}
            {activeFacetCount > 0 && (
              <Button variant="plain" size="sm" onClick={() => setFacets({ kind: [], criticality: [], exposure: [], classification: [] })}>
                Clear filters
              </Button>
            )}
            <div className="ml-auto">
              <Menu>
                <MenuTrigger asChild>
                  <Button variant="gray" size="md" icon={<ArrowDownWideNarrow />}>
                    {SORTS.find((s) => s.value === sort)?.label}
                  </Button>
                </MenuTrigger>
                <MenuContent>
                  <MenuLabel>Sort by</MenuLabel>
                  <MenuRadioGroup value={sort} onChange={setSort} options={SORTS} />
                </MenuContent>
              </Menu>
            </div>
          </div>

          <Card padded={false} className={cn("overflow-hidden transition-opacity duration-200", systems.isPlaceholderData && "opacity-60")}>
            {systems.isPending ? (
              <div className="space-y-3 p-5">
                {[0, 1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : (
              <Table
                caption="Registered systems"
                columns={columns}
                rows={items}
                rowKey={(s) => s.id}
                rowLabel={(s) => `Open ${s.name}`}
                onRowClick={(s) => navigate(`/systems/${s.id}`)}
                empty={<EmptyState compact icon={<Search />} title="No matching systems" message="Try a different search or clear the filters." />}
              />
            )}
          </Card>
          {systems.data && items.length > 0 && (
            <p className="mt-3 px-1 text-footnote text-label-3">
              {items.length} of {summary.data?.total ?? items.length} systems
            </p>
          )}
        </>
      )}
      <SystemSheet open={sheetOpen} onOpenChange={setSheetOpen} onSaved={(s) => navigate(`/systems/${s.id}`)} />
    </Page>
  );
}
