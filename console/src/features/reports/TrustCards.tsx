import { FileUp, KeyRound, RefreshCw, ShieldCheck, ShieldX, Download } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { TextArea } from "@/design/components/Field";
import { Segmented } from "@/design/components/Segmented";
import { Confirm } from "@/design/components/Sheet";
import { Card, CardHeader, Chip, GroupedList, GroupedRow, Skeleton } from "@/design/components/Surface";
import { ease, spring } from "@/design/motion";
import { useCan } from "@/lib/access";
import { saveExport } from "@/lib/exports";
import { formatDate, formatDateTime, formatInt } from "@/lib/format";
import { useAttestationKey, useRotateKey, useVerifyEnvelope } from "@/lib/queries";
import type { Verification } from "@/lib/types";
import { CHECKS, CopyButton, groupHex } from "./vocab";

/* ------------------------------------------------------------------- key */

export function KeyCard() {
  const key = useAttestationKey();
  const rotate = useRotateKey();
  const canRotate = useCan("org.manage");
  const [confirm, setConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  const k = key.data;
  const openssl = "openssl pkeyutl -verify -pubin -inkey falcon-attestation.pub.pem -rawin -in pae.bin -sigfile signature.bin";

  const save = async () => {
    setSaving(true);
    try {
      await saveExport({ kind: "key" });
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader title="Signing key" subtitle="The organisation’s post-quantum attestation key. Share the public half with auditors and partners." />
      {!k ? (
        <Skeleton className="h-[220px] rounded-[14px]" />
      ) : (
        <>
          <div className="flex items-center gap-3.5">
            <span className="grid size-12 shrink-0 place-items-center rounded-[14px] bg-accent-tint text-accent">
              <KeyRound className="size-6" strokeWidth={1.8} />
            </span>
            <div className="min-w-0">
              <div className="text-headline text-label">{k.algorithm}</div>
              <div className="text-footnote text-label-3">{k.standard} · NIST security category {k.nist_category}</div>
            </div>
          </div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={k.key_id}
              initial={{ opacity: 0, filter: "blur(4px)" }}
              animate={{ opacity: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, filter: "blur(4px)" }}
              transition={{ duration: 0.35, ease: ease.out }}
              className="mt-4 flex items-center gap-2 rounded-[12px] bg-fill-2 px-3.5 py-3"
            >
              <span className="min-w-0 flex-1 break-all font-mono text-callout tracking-wide text-label">{k.fingerprint}</span>
              <CopyButton text={k.key_id} label="Copy key ID" />
            </motion.div>
          </AnimatePresence>
          <GroupedList className="mt-3">
            <GroupedRow label="Public key" value={`${formatInt(k.public_key_bytes)} bytes`} />
            <GroupedRow label="Signature" value={`${formatInt(k.signature_bytes)} bytes`} />
            <GroupedRow label="In use since" value={k.created_at ? formatDate(k.created_at) : "—"} />
            <GroupedRow label="Keys that can verify" value={formatInt(k.known_keys.length)} description={k.known_keys.length > 1 ? "Retired keys still verify older snapshots." : undefined} />
          </GroupedList>
          <div className="mt-3 rounded-[12px] bg-fill-2 p-3">
            <div className="mb-1.5 flex items-center justify-between gap-2 text-caption text-label-3">
              Verify independently with OpenSSL 3.5 or later
              <CopyButton text={openssl} label="Copy command" />
            </div>
            <code className="block break-all font-mono text-[11.5px] leading-[17px] text-label-2">{openssl}</code>
          </div>
          <div className="mt-auto flex flex-wrap gap-2 pt-4">
            <Button variant="bordered" icon={<Download />} loading={saving} onClick={save}>Public key (.pem)</Button>
            {canRotate && <Button variant="gray" icon={<RefreshCw />} onClick={() => setConfirm(true)}>Rotate…</Button>}
          </div>
          <Confirm
            open={confirm}
            onOpenChange={setConfirm}
            title="Rotate the signing key?"
            message="New snapshots will be signed with a new ML-DSA-65 key. Existing snapshots stay verifiable; partners will need the new public key."
            confirmLabel="Rotate key"
            onConfirm={() =>
              rotate.mutateAsync().then(
                () => toast.success("Signing key rotated"),
                (e: Error) => toast.error(e.message),
              )
            }
          />
        </>
      )}
    </Card>
  );
}

/* ---------------------------------------------------------------- verify */

export function VerifyCard() {
  const verify = useVerifyEnvelope();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<string | null>(null);
  const [customKey, setCustomKey] = useState(false);
  const [pem, setPem] = useState("");

  const check = async (f: File) => {
    setFile(f.name);
    let envelope: unknown;
    try {
      envelope = JSON.parse(await f.text());
    } catch {
      verify.reset();
      toast.error("That file is not JSON. Choose a .dsse.json attestation.");
      return;
    }
    verify.mutate({ envelope, public_key: customKey && pem.trim() ? pem.trim() : undefined }, { onError: (e) => toast.error(e.message) });
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) void check(f);
  };

  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader title="Verify an attestation" subtitle="Check any FALCON attestation: one exported here, one from a CI pipeline, or one a supplier sent you." />
      <button
        type="button"
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "hover-light group relative grid min-h-[132px] place-items-center rounded-[14px] border border-dashed px-4 py-5 text-center transition-[border-color,background-color,transform] duration-200 ease-out focus-visible:focus-ring",
          dragging ? "scale-[1.01] border-accent bg-accent-tint" : "border-[var(--separator-strong)] hover:border-accent/60 hover:bg-fill-2",
        )}
      >
        <span className="flex flex-col items-center gap-2">
          <motion.span animate={{ y: dragging ? -3 : 0 }} transition={spring.snappy} className="grid size-10 place-items-center rounded-full bg-accent-tint text-accent">
            <FileUp className="size-5" />
          </motion.span>
          <span className="text-callout font-medium text-label">{file ?? "Drop a .dsse.json file, or choose one"}</span>
          <span className="text-footnote text-label-3">Checked against this installation’s keys{customKey ? " or the key below" : ""}.</span>
        </span>
      </button>
      <input
        ref={input}
        type="file"
        accept=".json,application/json"
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void check(f);
          e.target.value = "";
        }}
      />
      <button type="button" onClick={() => setCustomKey((v) => !v)} className="mt-3 self-start rounded-[6px] text-footnote font-medium text-accent-ink hover:underline focus-visible:focus-ring">
        {customKey ? "Use this installation’s keys" : "Use someone else’s public key…"}
      </button>
      <AnimatePresence initial={false}>
        {customKey && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={spring.smooth} className="overflow-hidden">
            <TextArea className="mt-2 font-mono text-footnote" rows={4} placeholder="-----BEGIN PUBLIC KEY-----" value={pem} onChange={(e) => setPem(e.target.value)} aria-label="Public key (PEM)" />
          </motion.div>
        )}
      </AnimatePresence>
      <AnimatePresence mode="wait" initial={false}>
        {verify.isPending ? (
          <motion.div key="busy" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Skeleton className="mt-4 h-[120px] rounded-[14px]" />
          </motion.div>
        ) : verify.data ? (
          <motion.div key={file ?? "result"} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.3, ease: ease.out }}>
            <VerifyResult v={verify.data} />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Card>
  );
}

function VerifyResult({ v }: { v: Verification }) {
  return (
    <div className={cn("mt-4 rounded-[14px] p-4", v.valid ? "bg-[var(--status-good-tint)]" : "bg-[var(--status-critical-tint)]")}>
      <div className="flex items-center gap-2.5">
        <motion.span initial={{ scale: 0.5, rotate: -12 }} animate={{ scale: 1, rotate: 0 }} transition={spring.snappy}>
          {v.valid ? <ShieldCheck className="size-6 text-good" /> : <ShieldX className="size-6 text-critical" />}
        </motion.span>
        <div className="min-w-0">
          <div className="text-headline text-label">{v.valid ? "Authentic and unaltered" : "Verification failed"}</div>
          <div className="line-clamp-2 text-footnote text-label-2">
            {v.valid
              ? `${v.organisation ?? "Unknown organisation"} · ${v.scope ?? ""} · ${formatInt(v.artefacts ?? 0)} artefacts · signed ${v.timestamp ? formatDateTime(v.timestamp) : ""}`
              : v.checks.find((c) => !c.ok)?.detail}
          </div>
        </div>
      </div>
      <ul className="mt-3 flex flex-wrap gap-1.5">
        {v.checks.map((c, i) => (
          <motion.li
            key={c.check}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ ...spring.snappy, delay: 0.06 * i }}
            title={c.detail}
          >
            <Chip className={cn("h-[22px] gap-1 px-2 font-sans text-caption", c.ok ? "bg-[var(--surface)] text-label" : "bg-[var(--surface)] text-critical")}>
              {c.ok ? "✓" : "✕"} {CHECKS[c.check]}
            </Chip>
          </motion.li>
        ))}
      </ul>
      {v.subject && <div className="mt-2.5 font-mono text-caption text-label-3">sha256 {groupHex(v.subject.sha256, 16)}</div>}
    </div>
  );
}

/* ------------------------------------------------------------- pipelines */

const PIPELINES = {
  github: {
    label: "GitHub Actions",
    code: `name: Cryptography
on: [push, pull_request]
jobs:
  falcon:
    runs-on: ubuntu-latest
    permissions: { contents: read, security-events: write }
    steps:
      - uses: actions/checkout@v4
      - name: Discover and assess cryptography
        run: |
          docker run --rm -v "$PWD:/work" -w /work "$FALCON_IMAGE" \\
            scan . --format sarif --output falcon.sarif --fail-on high
        env: { FALCON_IMAGE: \${{ vars.FALCON_IMAGE }} }
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with: { sarif_file: falcon.sarif, category: falcon }`,
  },
  gitlab: {
    label: "GitLab CI",
    code: `falcon:
  image: $FALCON_IMAGE
  stage: test
  script:
    # A signed CBOM for the release record (FALCON_SIGNING_KEY is a file variable).
    - falcon scan . --format cyclonedx --output cbom.cdx.json --sign-key "$FALCON_SIGNING_KEY"
    # Fail the pipeline on harvest-now-decrypt-later exposure.
    - falcon scan . --format sarif --output falcon.sarif --fail-on hndl
  artifacts:
    when: always
    paths: [cbom.cdx.json, cbom.cdx.json.dsse.json, falcon.sarif]`,
  },
  cli: {
    label: "Command line",
    code: `# Scan a folder, archive, container image or repository; print the riskiest findings.
falcon scan ./payments-service

# Gate a build: exit 1 when anything reaches high risk.
falcon scan app.tar --format sarif --output falcon.sarif --fail-on high

# Sign a CBOM with an ML-DSA-65 key, then verify it anywhere.
falcon keygen --out keys
falcon scan . --format cyclonedx -o cbom.cdx.json --sign-key keys/attestation-mldsa65.pem
falcon verify cbom.cdx.json.dsse.json --key keys/falcon-attestation.pub.pem`,
  },
} as const;

export function PipelinesCard() {
  const [tab, setTab] = useState<keyof typeof PIPELINES>("github");
  const p = PIPELINES[tab];
  return (
    <Card>
      <CardHeader
        title="In the pipeline"
        subtitle="The same engine, risk model and recommendations run offline in CI: annotate pull requests, gate releases, and sign a CBOM for every build."
        actions={<Segmented label="Pipeline" size="sm" value={tab} onChange={setTab} options={Object.entries(PIPELINES).map(([value, v]) => ({ value: value as keyof typeof PIPELINES, label: v.label }))} />}
      />
      <div className="relative overflow-hidden rounded-[12px] bg-[var(--code-bg,#1d1d1f)]">
        <span className="absolute right-2 top-2 z-10">
          <CopyButton text={p.code} label="Copy" className="text-white/70 hover:bg-white/10 hover:text-white" />
        </span>
        <AnimatePresence mode="wait" initial={false}>
          <motion.pre
            key={tab}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -2, transition: { duration: 0.1 } }}
            transition={{ duration: 0.26, ease: ease.out }}
            className="overflow-x-auto p-4 pr-12 font-mono text-[12px] leading-[19px] text-[#f5f5f7]"
          >
            {p.code}
          </motion.pre>
        </AnimatePresence>
      </div>
    </Card>
  );
}
