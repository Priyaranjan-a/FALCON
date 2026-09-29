import { ArrowLeft, ArrowUpRight, ChevronRight, CircleAlert, Info } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Card, CardHeader, Chip, EmptyState, GroupedList, GroupedRow } from "@/design/components/Surface";
import { Tooltip } from "@/design/components/Menu";
import { ApiError } from "@/lib/api";
import { formatDate, formatInt, formatPercent, formatRelative } from "@/lib/format";
import { useArtefact } from "@/lib/queries";
import type { ArtefactDetail, Evidence } from "@/lib/types";
import { RecommendationCard } from "../migration/RecommendationCard";
import { ArtefactRiskCard } from "../risk/ArtefactRiskCard";
import { Page, PageSkeleton } from "../shell/Page";
import { describeArtefact, primitiveLabel } from "./describe";
import { CLASSICAL, ClassicalBadge, KindGlyph, KINDS, QUANTUM, QuantumBadge, relationLabel } from "./vocab";

export default function ArtefactPage() {
  const { artefactId = "" } = useParams();
  const navigate = useNavigate();
  const artefact = useArtefact(artefactId);

  if (artefact.isPending) return <PageSkeleton />;
  if (artefact.isError) {
    const missing = artefact.error instanceof ApiError && artefact.error.status === 404;
    return (
      <div className="grid min-h-[60vh] place-items-center">
        <EmptyState
          icon={<CircleAlert />}
          title={missing ? "This artefact is no longer in the inventory" : "The artefact couldn’t be loaded"}
          message={missing ? "Its source may have been removed, taking its evidence with it." : artefact.error.message}
          action={<Button variant="tinted" onClick={() => navigate("/inventory")}>Back to Inventory</Button>}
        />
      </div>
    );
  }

  const a = artefact.data;
  const meta = KINDS[a.kind];
  const assessed = a.kind !== "library" && a.kind !== "hardware";

  return (
    <Page
      eyebrow={
        <span className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => navigate(-1)} className="inline-flex items-center gap-1 rounded text-accent-ink hover:underline">
            <ArrowLeft className="size-3.5" /> Inventory
          </button>
          <span className="text-label-4">/</span>
          <span>{meta.singular}</span>
        </span>
      }
      title={
        <span className="flex items-center gap-3">
          <KindGlyph kind={a.kind} size={40} className="max-sm:hidden" />
          <span className="min-w-0 break-words">{a.name}</span>
        </span>
      }
      subtitle={a.catalogue?.description ?? describeArtefact(a)}
    >
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-4">
          {a.status === "resolved" && (
            <div className="flex items-start gap-3 rounded-[12px] bg-[var(--status-good-tint)] px-3.5 py-3 text-subhead text-label">
              <Info className="mt-px size-[18px] shrink-0 text-good" />
              <span>
                <strong className="font-semibold">Resolved.</strong> The latest scans of this system no longer find it. Its evidence is kept for the record.
              </span>
            </div>
          )}
          {assessed && <AssessmentCard a={a} />}
          {a.status === "active" && <ArtefactRiskCard artefactId={a.id} />}
          {a.status === "active" && <RecommendationCard artefactId={a.id} />}
          <KindPanel a={a} />
          <EvidenceCard evidence={a.evidence} total={a.occurrences} />
        </div>
        <aside className="space-y-4">
          <GroupedList header="Identity">
            {a.system && (
              <GroupedRow
                label="System"
                value={
                  <button type="button" onClick={() => navigate(`/systems/${a.system!.id}`)} className="inline-flex items-center gap-1.5 rounded text-accent-ink hover:underline">
                    <Chip>{a.system.code}</Chip>
                    <span className="truncate">{a.system.name}</span>
                  </button>
                }
              />
            )}
            <GroupedRow label="Class" value={meta.singular} />
            {a.family && <GroupedRow label="Family" value={familyLabel(a.family)} />}
            {a.primitive && assessed && <GroupedRow label="Primitive" value={primitiveLabel(a.primitive)} />}
            <GroupedRow label="Confidence" value={<Confidence value={a.confidence} />} />
            <GroupedRow label="Status" value={a.status === "active" ? "In use" : "Resolved"} />
          </GroupedList>
          <GroupedList>
            <GroupedRow label="First seen" value={formatDate(a.first_seen_at)} />
            <GroupedRow label="Last seen" value={formatRelative(a.last_seen_at)} />
            <GroupedRow label="Occurrences" value={formatInt(a.occurrences)} />
          </GroupedList>
          {a.links.length > 0 && <RelatedList a={a} />}
          <Fingerprint identity={a.identity} />
        </aside>
      </div>
    </Page>
  );
}

function Confidence({ value }: { value: number }) {
  const bars = value >= 0.95 ? 4 : value >= 0.85 ? 3 : value >= 0.7 ? 2 : 1;
  return (
    <Tooltip content={`${formatPercent(value, 0)}: how certain the detector is that this is real cryptography in use`}>
      <span className="inline-flex items-center gap-2">
        <span aria-hidden className="flex h-3 items-end gap-[2px]">
          {[1, 2, 3, 4].map((i) => (
            <span key={i} className={cn("w-[3px] rounded-[1px]", i <= bars ? "bg-label-2" : "bg-fill-hover")} style={{ height: 3 + i * 2.25 }} />
          ))}
        </span>
        <span className="tabular">{formatPercent(value, 0)}</span>
      </span>
    </Tooltip>
  );
}

/* ------------------------------------------------------------ assessment */

function AssessmentCard({ a }: { a: ArtefactDetail }) {
  const s = a.assessment;
  const quantum = a.quantum ?? s.quantum ?? "unknown";
  const classical = a.classical ?? s.classical ?? "unknown";
  const hasBits = typeof s.classical_bits === "number";
  return (
    <Card>
      <CardHeader title="Assessment" subtitle="How this artefact holds up today and against a cryptographically relevant quantum computer." />
      <div className="grid gap-3 sm:grid-cols-2">
        <Verdict heading="Against a quantum adversary" badge={<QuantumBadge value={quantum} />} text={QUANTUM[quantum].summary} />
        <Verdict heading="Today" badge={<ClassicalBadge value={classical} />} text={CLASSICAL[classical].summary} />
      </div>
      {hasBits && <StrengthScale classical={s.classical_bits ?? 0} quantum={s.quantum_bits ?? 0} category={s.nist_category ?? null} />}
      {!!s.reasons?.length && (
        <ul className="mt-5 space-y-2">
          {s.reasons.map((reason) => (
            <li key={reason} className="flex gap-2.5 text-subhead text-label-2">
              <span aria-hidden className="mt-[7px] size-1.5 shrink-0 rounded-full bg-label-4" />
              {reason}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Verdict({ heading, badge, text: body }: { heading: string; badge: ReactNode; text: string }) {
  return (
    <div className="rounded-[14px] bg-surface-2 p-4">
      <div className="mb-2 text-footnote font-medium text-label-3">{heading}</div>
      {badge}
      <p className="mt-2 text-footnote text-label-2">{body}</p>
    </div>
  );
}

const SCALE_MAX = 256;
const THRESHOLDS = [
  { bits: 112, label: "Minimum today" },
  { bits: 128, label: "Long-term target" },
];

/** Security strength in bits on one shared axis: classical and post-quantum, with the thresholds that matter. */
function StrengthScale({ classical, quantum, category }: { classical: number; quantum: number; category: number | null }) {
  const pct = (bits: number) => `${(Math.min(bits, SCALE_MAX) / SCALE_MAX) * 100}%`;
  const rows = [
    { label: "Classical attacker", bits: classical, floor: "Below 80 bits" },
    { label: "Quantum attacker", bits: quantum, floor: "0 bits · broken" },
  ];
  return (
    <div className="mt-6" role="img" aria-label={`Security strength: ${classical} bits classically, ${quantum} bits against a quantum computer`}>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-footnote font-semibold text-label-2">Security strength</span>
        {category && <span className="text-footnote text-label-3">NIST PQC category {category}</span>}
      </div>
      <div className="relative space-y-3 pb-6">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[170px_1fr] items-center gap-3 max-sm:grid-cols-[120px_1fr]">
            <span className="truncate text-subhead text-label">{row.label}</span>
            <div className="relative h-5">
              <div className="absolute inset-y-[6px] left-0 right-0 rounded-full bg-fill-2" />
              {row.bits > 0 ? (
                <div
                  className="absolute inset-y-[6px] left-0 rounded-r-[4px] transition-[width] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"
                  style={{ width: pct(row.bits), background: row.bits >= 128 ? "var(--status-good)" : row.bits >= 112 ? "var(--series-1)" : "var(--status-critical)" }}
                />
              ) : null}
              <span
                className="absolute top-1/2 -translate-y-1/2 whitespace-nowrap pl-2 text-footnote font-semibold tabular text-label"
                style={{ left: row.bits > 0 ? pct(row.bits) : 0 }}
              >
                {row.bits > 0 ? `${row.bits} bits` : row.floor}
              </span>
            </div>
          </div>
        ))}
        <div className="pointer-events-none absolute inset-y-0 left-[182px] right-0 max-sm:left-[132px]">
          {THRESHOLDS.map((t) => (
            <div key={t.bits} className="absolute bottom-0 top-0" style={{ left: pct(t.bits) }}>
              <div className="absolute bottom-5 top-0 w-px bg-separator-strong" />
              <div className={cn("absolute bottom-0 whitespace-nowrap text-caption text-label-3", t.bits === 128 ? "left-1" : "right-1")}>
                {t.bits} · {t.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ kind panel */

type Row = [string, ReactNode];
const text = (v: unknown): string | null => (typeof v === "string" && v ? v : typeof v === "number" ? String(v) : null);
const yesNo = (v: unknown) => (v ? "Yes" : "No");

function KindPanel({ a }: { a: ArtefactDetail }) {
  const p = a.properties;
  if (a.kind === "certificate") return <CertificatePanel a={a} />;
  let title = "";
  let rows: Row[] = [];
  let note: string | null = null;
  switch (a.kind) {
    case "algorithm": {
      title = "Algorithm";
      const id = a.identity as Record<string, string | undefined>;
      rows = [
        ["Algorithm", id.algorithm],
        ["Parameter", id.parameter],
        ["Mode", id.mode],
        ["Padding", id.padding],
        ["Hash", id.hash],
        ["Standard", a.catalogue?.standard],
        ["Used as", text(p.setting) ?? text(p.library)],
      ].filter(([, v]) => v) as Row[];
      break;
    }
    case "key":
      title = "Key";
      rows = [
        ["Algorithm", text(p.key_algorithm)],
        ["Format", text(p.format)],
        ["Private", yesNo(p.private)],
        ["Encrypted at rest", p.private ? yesNo(p.encrypted) : null],
        ["Comment", text(p.comment)],
      ].filter(([, v]) => v) as Row[];
      note = p.private && !p.encrypted ? "An unencrypted private key sits in the scanned source. FALCON recorded where it is, never the key itself." : null;
      break;
    case "protocol":
      title = "Protocol";
      rows = [
        ["Protocol", text((a.identity as Record<string, unknown>).protocol)],
        ["Version", text((a.identity as Record<string, unknown>).version)],
        ["Hybrid key exchange", (a.identity as Record<string, unknown>).hybrid ? "Yes" : "No"],
        ["Configured by", text(p.setting)],
        ["Policy", text(p.policy)],
        ["Implementation", text(p.library)],
      ].filter(([, v]) => v) as Row[];
      break;
    case "library": {
      title = "Library";
      const pqc = (p.pqc ?? {}) as { status?: string; since?: string; note?: string; capable?: boolean | null };
      const eol = p.eol as { branch: string; date: string; reached: boolean } | undefined;
      rows = [
        ["Package", text(p.package)],
        ["Ecosystem", text(p.ecosystem)],
        ["Declared version", text(p.declared_version)],
        ["Post-quantum support", pqcSupport(pqc)],
        ["End of life", eol ? `${eol.branch} · ${eol.reached ? "ended" : "ends"} ${formatDate(eol.date)}` : null],
        ["Category", text(p.category)],
      ].filter(([, v]) => v) as Row[];
      note = [pqc.note, text(p.note)].filter(Boolean).join(" ") || null;
      break;
    }
    case "hardware":
      title = "Hardware module";
      rows = [
        ["Vendor", text(p.vendor)],
        ["Type", text(p.type)?.toUpperCase()],
        ["Interface", text(p.interface)],
        ["Model", text(p.hsm_type) ?? text(p.model)],
        ["Module", text((a.identity as Record<string, unknown>).module)],
      ].filter(([, v]) => v) as Row[];
      break;
    case "cloud_service":
      title = "Cloud service";
      rows = [
        ["Provider", text(p.provider)?.toUpperCase()],
        ["Service", text(p.service)?.toUpperCase()],
        ["Resource", text((a.identity as Record<string, unknown>).resource)],
        ["Key specification", text(p.key_spec)],
        ["Key usage", text(p.key_usage)?.replace(/_/g, " ").toLowerCase()],
        ["Automatic rotation", p.rotation === undefined ? null : yesNo(p.rotation)],
        ["Multi-region", p.multi_region === undefined ? null : yesNo(p.multi_region)],
      ].filter(([, v]) => v) as Row[];
      break;
  }
  if (!rows.length && !note) return null;
  return (
    <Card>
      <CardHeader title={title} />
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-footnote text-label-3">{label}</dt>
            <dd className="truncate text-callout text-label" title={typeof value === "string" ? value : undefined}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
      {note && <p className="mt-4 rounded-[10px] bg-surface-2 px-3 py-2.5 text-footnote text-label-2">{note}</p>}
    </Card>
  );
}

function pqcSupport(pqc: { status?: string; since?: string; capable?: boolean | null }): string {
  if (pqc.status === "native") return pqc.capable === false ? `Built in from ${pqc.since} (this version predates it)` : pqc.since ? `Built in from ${pqc.since}` : "Built in";
  if (pqc.status === "partial") return "Partial";
  if (pqc.status === "none") return "None";
  if (pqc.status === "advisory") return "Advisory only";
  return "Unknown";
}

function CertificatePanel({ a }: { a: ArtefactDetail }) {
  const p = a.properties;
  const notBefore = text(p.not_before);
  const notAfter = text(p.not_after);
  const dns = (p.dns_names as string[] | undefined) ?? [];
  const rows: Row[] = (
    [
      ["Subject", text(p.subject)],
      ["Issuer", p.self_signed ? "Self-signed" : text(p.issuer)],
      ["Public key", text(p.key_algorithm)],
      ["Signature", text(p.signature_algorithm)],
      ["Serial number", text(p.serial) ? <span className="font-mono text-footnote">{text(p.serial)}</span> : null],
      ["Certificate authority", p.is_ca ? "Yes" : "No"],
    ] as Row[]
  ).filter(([, v]) => v);
  return (
    <Card>
      <CardHeader title="Certificate" />
      {notBefore && notAfter && <Validity from={notBefore} to={notAfter} />}
      <dl className="mt-5 grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-footnote text-label-3">{label}</dt>
            <dd className="truncate text-callout text-label" title={typeof value === "string" ? value : undefined}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
      {dns.length > 0 && (
        <div className="mt-4">
          <div className="mb-1.5 text-footnote text-label-3">Subject alternative names</div>
          <div className="flex flex-wrap gap-1.5">
            {dns.map((d) => (
              <Chip key={d}>{d}</Chip>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

/** The validity window on a time axis with today marked. */
function Validity({ from, to }: { from: string; to: string }) {
  const start = new Date(from).getTime();
  const end = new Date(to).getTime();
  const now = Date.now();
  const lo = Math.min(start, now);
  const hi = Math.max(end, now);
  const span = hi - lo || 1;
  const x = (t: number) => `${((t - lo) / span) * 100}%`;
  const expired = now > end;
  const days = Math.round((end - now) / 86_400_000);
  const soon = !expired && days <= 90;
  return (
    <div role="img" aria-label={`Valid from ${formatDate(from)} to ${formatDate(to)}; ${expired ? `expired ${-days} days ago` : `${days} days remaining`}`}>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <span className="text-subhead font-medium text-label">{expired ? `Expired ${formatInt(-days)} days ago` : `${formatInt(days)} days remaining`}</span>
        <span className="text-footnote text-label-3">
          {formatDate(from)} – {formatDate(to)}
        </span>
      </div>
      <div className="relative h-7">
        <div className="absolute inset-x-0 top-3 h-1.5 rounded-full bg-fill-2" />
        <div
          className="absolute top-3 h-1.5 rounded-[3px]"
          style={{ left: x(start), width: `calc(${x(end)} - ${x(start)})`, background: expired ? "var(--status-critical)" : soon ? "var(--status-warning)" : "var(--status-good)" }}
        />
        <div className="absolute top-0 h-7 w-px bg-label" style={{ left: x(now) }} />
        <div className={cn("absolute -top-0.5 text-caption font-semibold text-label", now - lo > span * 0.85 ? "-translate-x-full pr-1.5" : "pl-1.5")} style={{ left: x(now) }}>
          Today
        </div>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- evidence */

function EvidenceCard({ evidence, total }: { evidence: Evidence[]; total: number }) {
  const [expanded, setExpanded] = useState(false);
  const shown = expanded ? evidence : evidence.slice(0, 6);
  return (
    <Card padded={false}>
      <div className="px-5 pt-5">
        <CardHeader title="Evidence" subtitle={`Where FALCON found it${total > 1 ? `: ${formatInt(total)} occurrences in the latest scans` : ""}. Secrets in snippets are masked.`} />
      </div>
      <ul>
        {shown.map((e) => (
          <EvidenceItem key={e.id} e={e} />
        ))}
      </ul>
      {evidence.length > shown.length && (
        <div className="px-5 py-3 hairline-t">
          <Button variant="plain" size="sm" onClick={() => setExpanded(true)}>
            Show all {formatInt(evidence.length)}
          </Button>
        </div>
      )}
    </Card>
  );
}

function EvidenceItem({ e }: { e: Evidence }) {
  return (
    <li className="px-5 py-4 hairline-t">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="min-w-0 break-all font-mono text-footnote font-medium text-label">
          {e.path}
          {e.line ? <span className="text-label-3">:{e.line}</span> : null}
        </span>
        <span className="ml-auto flex shrink-0 items-center gap-2 text-caption text-label-3">
          <Chip>{e.rule}</Chip>
          <span>{e.source}</span>
        </span>
      </div>
      {e.via && (
        <div className="mb-2 flex items-center gap-1 text-footnote text-label-3">
          <ChevronRight className="size-3" /> {VIA[e.via] ?? `Found through a related artefact (${relationLabel(e.via, "in").toLowerCase()})`}
        </div>
      )}
      {e.snippet?.length ? <Snippet lines={e.snippet} focus={e.line} /> : null}
    </li>
  );
}

function Snippet({ lines, focus }: { lines: [number, string][]; focus: number | null }) {
  const width = String(lines[lines.length - 1][0]).length;
  // Strings pulled from binaries have no line numbers: show them without a gutter.
  const numbered = focus !== null || lines.some(([n]) => n > 0);
  return (
    <pre className="overflow-x-auto rounded-[10px] bg-surface-2 py-2 font-mono text-[12px] leading-[20px] text-label-2">
      {lines.map(([n, line], i) => (
        <div key={`${n}-${i}`} className={cn("flex min-w-max pr-4", !numbered && "pl-3", numbered && n === focus && "bg-accent-tint text-label shadow-[inset_2px_0_0_var(--accent)]")}>
          {numbered && (
            <span className="select-none pl-3 pr-4 text-right text-label-4" style={{ width: `calc(${width}ch + 1.75rem)` }}>
              {n}
            </span>
          )}
          <code className="whitespace-pre">{line || " "}</code>
        </div>
      ))}
    </pre>
  );
}

/** How evidence reached an artefact when it was found inside another one. */
const VIA: Record<string, string> = {
  "certifies-key": "Found in the certificate that carries this key",
  "signed-with": "Found as the signature algorithm of a certificate",
  "uses-algorithm": "Found as the algorithm of a key",
  "protects-with": "Found as the key algorithm of a cloud key",
  negotiates: "Found in a protocol configuration that negotiates it",
};

const PROVIDERS: Record<string, string> = { aws: "AWS", gcp: "Google Cloud", azure: "Azure" };

/** "aws:kms" → "AWS KMS"; algorithm families pass through. */
function familyLabel(family: string): string {
  const [provider, service] = family.split(":");
  return service ? `${PROVIDERS[provider] ?? provider.toUpperCase()} ${service.replace(/[-_]/g, " ").toUpperCase()}` : family;
}

/* ---------------------------------------------------------------- related */

function RelatedList({ a }: { a: ArtefactDetail }) {
  const navigate = useNavigate();
  return (
    <GroupedList header="Related">
      {a.links.map((link) => (
        <button
          key={`${link.direction}-${link.relation}-${link.artefact.id}`}
          type="button"
          onClick={() => navigate(`/inventory/${link.artefact.id}`)}
          className="group relative flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-fill-2 focus-visible:focus-ring [&+&]:before:absolute [&+&]:before:inset-x-4 [&+&]:before:top-0 [&+&]:before:h-px [&+&]:before:bg-separator"
        >
          <KindGlyph kind={link.artefact.kind} size={28} />
          <span className="min-w-0 flex-1">
            <span className="block text-caption text-label-3">{relationLabel(link.relation, link.direction)}</span>
            <span className="block truncate text-callout text-label">{link.artefact.name}</span>
          </span>
          {link.artefact.quantum && link.artefact.kind !== "library" && <QuantumBadge value={link.artefact.quantum} short />}
          <ArrowUpRight className="size-4 shrink-0 text-label-4 group-hover:text-label-3" />
        </button>
      ))}
    </GroupedList>
  );
}

function Fingerprint({ identity }: { identity: Record<string, unknown> }) {
  const hashes = Object.entries(identity).filter(([k, v]) => typeof v === "string" && /sha256|fingerprint/i.test(k));
  if (!hashes.length) return null;
  return (
    <GroupedList header="Fingerprint" footer="Stable across scans: the same certificate or key keeps one identity and its history.">
      {hashes.map(([k, v]) => (
        <div key={k} className="px-4 py-2.5">
          <div className="text-caption text-label-3">{k.replace(/_/g, " ").toUpperCase()}</div>
          <div className="break-all font-mono text-[11.5px] leading-[17px] text-label-2">{String(v)}</div>
        </div>
      ))}
    </GroupedList>
  );
}
