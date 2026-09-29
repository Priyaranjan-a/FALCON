import { ArrowUpRight, Network } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Card, CardHeader, Chip, EmptyState } from "@/design/components/Surface";
import { formatInt } from "@/lib/format";
import { useBlastGraph } from "@/lib/queries";
import type { BlastGraph, BlastNode } from "@/lib/types";
import { useMeasure } from "@/viz/core/useMeasure";
import { KindGlyph, KINDS } from "../discovery/vocab";
import { BANDS, RiskBadge } from "../risk/vocab";
import { Page, PageSkeleton } from "../shell/Page";

const ROW = 30;
const SYS_W = 210;
const NODE_W = 250;

export default function BlastRadiusPage() {
  const graph = useBlastGraph();
  if (graph.isPending) return <PageSkeleton />;
  const data = graph.data;
  return (
    <Page
      title="Blast Radius"
      subtitle="Which systems share each algorithm, library, certificate and key. When one breaks (or must be replaced) everything linked to it moves together, so shared cryptography is where migration pays off most."
      width="wide"
    >
      {!data || data.nodes.length === 0 ? (
        <Card>
          <EmptyState icon={<Network />} title="No shared cryptography yet" message="The graph appears once scanned systems share algorithms, libraries or certificates, or carry high risks." />
        </Card>
      ) : (
        <Explorer data={data} />
      )}
    </Page>
  );
}

function Explorer({ data }: { data: BlastGraph }) {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string>(data.nodes[0].id);
  const [hover, setHover] = useState<{ kind: "node" | "system"; id: string } | null>(null);
  const [ref, { width }] = useMeasure<HTMLDivElement>();
  const nodes = data.nodes;
  const systems = data.systems;
  const height = Math.max(nodes.length, systems.length) * ROW + 16;
  const sysY = useMemo(() => {
    const offset = (height - systems.length * ROW) / 2;
    return new Map(systems.map((s, i) => [s.id, offset + i * ROW + ROW / 2]));
  }, [systems, height]);
  const nodeY = useMemo(() => {
    const offset = (height - nodes.length * ROW) / 2;
    return new Map(nodes.map((n, i) => [n.id, offset + i * ROW + ROW / 2]));
  }, [nodes, height]);
  const focus = hover ?? { kind: "node" as const, id: selected };
  const lit = (link: { system: string; node: string }) => (focus.kind === "node" ? link.node === focus.id : link.system === focus.id);
  const litSystems = new Set(data.links.filter(lit).map((l) => l.system));
  const litNodes = new Set(data.links.filter(lit).map((l) => l.node));
  const x1 = SYS_W;
  const x2 = Math.max(SYS_W + 120, width - NODE_W);
  const node = nodes.find((n) => n.id === selected)!;

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card>
        <CardHeader title="Shared cryptography" subtitle="Systems on the left; algorithms, libraries, certificates and keys on the right, ordered by how much they would take with them." />
        <div ref={ref} className="relative w-full select-none" style={{ height }} onPointerLeave={() => setHover(null)}>
          {width > 0 && (
            <svg width={width} height={height} className="absolute inset-0" aria-hidden>
              {data.links.map((l) => {
                const y1 = sysY.get(l.system) ?? 0;
                const y2 = nodeY.get(l.node) ?? 0;
                const on = lit(l);
                const mid = (x1 + x2) / 2;
                return (
                  <path
                    key={`${l.system}-${l.node}`}
                    d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
                    fill="none"
                    strokeWidth={Math.min(5, 1 + Math.log2(1 + l.artefacts))}
                    strokeLinecap="round"
                    className="transition-[opacity,stroke] duration-300"
                    style={{ stroke: on ? BANDS[l.band].color : "var(--separator-strong)", opacity: on ? 0.95 : 0.5 }}
                  />
                );
              })}
            </svg>
          )}
          {systems.map((s) => (
            <button
              key={s.id}
              type="button"
              onPointerEnter={() => setHover({ kind: "system", id: s.id })}
              onClick={() => navigate(`/systems/${s.id}`)}
              className={cn(
                "hover-light absolute left-0 flex h-[26px] items-center gap-2 rounded-full pl-1 pr-3 text-left transition-opacity duration-300",
                litSystems.has(s.id) || focus.id === s.id ? "opacity-100" : "opacity-45",
              )}
              style={{ top: (sysY.get(s.id) ?? 0) - 13, width: SYS_W - 8 }}
            >
              <Chip className="shrink-0">{s.code}</Chip>
              <span className="truncate text-subhead text-label">{s.name}</span>
            </button>
          ))}
          {nodes.map((n) => (
            <button
              key={n.id}
              type="button"
              onPointerEnter={() => setHover({ kind: "node", id: n.id })}
              onClick={() => setSelected(n.id)}
              className={cn(
                "hover-light absolute flex h-[26px] items-center gap-2 rounded-full pl-1 pr-3 text-left transition-[opacity,box-shadow] duration-300",
                litNodes.has(n.id) || focus.id === n.id ? "opacity-100" : "opacity-45",
                selected === n.id && "bg-fill shadow-[0_0_0_1.5px_var(--label)]",
              )}
              style={{ top: (nodeY.get(n.id) ?? 0) - 13, left: x2 + 6, width: NODE_W - 10 }}
            >
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: BANDS[n.band].color }} />
              <KindGlyph kind={n.kind} size={20} />
              <span className="truncate text-subhead text-label">{n.label}</span>
              <span className="ml-auto shrink-0 text-caption tabular text-label-3">{n.systems.length}</span>
            </button>
          ))}
        </div>
      </Card>
      <Card className="self-start">
        <div className="flex items-center gap-3">
          <KindGlyph kind={node.kind} size={40} />
          <div className="min-w-0">
            <div className="text-caption text-label-3">{KINDS[node.kind].singular}</div>
            <div className="truncate text-title-3 text-label">{node.label}</div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-3">
          <Figure label="Systems" value={formatInt(node.systems.length)} />
          <Figure label="Artefacts" value={formatInt(node.artefacts)} />
          <Figure label="Mission-critical" value={formatInt(node.mission_critical)} />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <RiskBadge band={node.band} score={node.score} />
          {node.hndl > 0 && <span className="text-footnote font-medium text-label">{node.hndl} harvestable</span>}
        </div>
        <p className="mt-4 text-subhead text-label-2">{explain(node)}</p>
        <div className="mb-1.5 mt-5 text-footnote font-semibold text-label-2">Affected systems</div>
        <ul className="space-y-1">
          {node.systems.map((sid) => {
            const s = systems.find((x) => x.id === sid)!;
            const link = data.links.find((l) => l.system === sid && l.node === node.id);
            return (
              <li key={sid}>
                <button type="button" onClick={() => navigate(`/systems/${sid}`)} className="hover-light flex w-full items-center gap-2 rounded-[10px] px-2 py-1.5 text-left transition-colors hover:bg-fill-2">
                  <Chip>{s.code}</Chip>
                  <span className="min-w-0 flex-1 truncate text-subhead text-label">{s.name}</span>
                  <span className="text-caption tabular text-label-3">{link?.artefacts} artefact{link?.artefacts === 1 ? "" : "s"}</span>
                </button>
              </li>
            );
          })}
        </ul>
        <Button variant="tinted" block className="mt-4" trailingIcon={<ArrowUpRight />} onClick={() => navigate(`/inventory/${node.sample}`)}>
          Open an example
        </Button>
      </Card>
    </div>
  );
}

function explain(n: BlastNode): string {
  const reach = `${n.systems.length} system${n.systems.length === 1 ? "" : "s"}`;
  if (n.kind === "algorithm") return `If ${n.label} is broken or disallowed, ${reach} must change at once: ${formatInt(n.artefacts)} places in total. Migrate the shared pattern once (a library, a configuration template) rather than system by system.`;
  if (n.kind === "library") return `${n.label} ships in ${reach}. Upgrading it once enables post-quantum cryptography everywhere it is used, and a flaw in it reaches all of them.`;
  if (n.kind === "certificate") return `The same certificate is deployed in ${reach}. Re-issuing it is one change with ${reach} to redeploy.`;
  if (n.kind === "key") return `The same key is used in ${reach}. A compromise of it is a compromise of every one; replace it with separate keys.`;
  return `Used by ${reach}.`;
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[12px] bg-fill-2 px-3 py-2">
      <div className="text-caption text-label-3">{label}</div>
      <div className="text-headline tabular text-label">{value}</div>
    </div>
  );
}
