import { ChevronLeft, FolderOpen, Upload } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Switch } from "@/design/components/Controls";
import { TextArea, TextField } from "@/design/components/Field";
import { Sheet } from "@/design/components/Sheet";
import { useQueryClient } from "@tanstack/react-query";
import { useCan } from "@/lib/access";
import { ApiError, upload } from "@/lib/api";
import { hasNativeDialogs, pickFile, pickFolder } from "@/lib/desktop";
import { formatInt } from "@/lib/format";
import { invalidateDiscovery, useCapabilities, useCreateSource, type NewSource } from "@/lib/queries";
import type { ScanBrief, Source, SourceKind } from "@/lib/types";
import { formatBytes, SOURCE_KINDS, SourceGlyph } from "./vocab";

const ORDER: SourceKind[] = ["directory", "archive", "git", "image-archive", "image-registry", "endpoint"];
const ARCHIVE_ACCEPT = ".zip,.jar,.war,.ear,.tar,.tgz,.gz,.bz2,.xz,.txz,.tbz2";
const IMAGE_ACCEPT = ".tar,.tgz,.gz";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  system: { id: string; name: string };
}

export function AddSourceSheet({ open, onOpenChange, system }: Props) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const caps = useCapabilities();
  const canScan = useCan("scans.run");
  const create = useCreateSource(system.id);
  const native = hasNativeDialogs();

  const [kind, setKind] = useState<SourceKind | null>(null);
  const [locator, setLocator] = useState("");
  const [name, setName] = useState("");
  const [ref, setRef] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [scanNow, setScanNow] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    if (open) return;
    const t = window.setTimeout(() => {
      setKind(null);
      setLocator("");
      setName("");
      setRef("");
      setFile(null);
      setScanNow(true);
      setError(null);
      setProgress(null);
    }, 200);
    return () => window.clearTimeout(t);
  }, [open]);

  const choose = (next: SourceKind) => {
    setKind(next);
    setLocator("");
    setFile(null);
    setError(null);
  };

  const isUpload = (kind === "archive" || kind === "image-archive") && !locator;
  const busy = create.isPending || progress !== null;
  const maxMb = caps.data?.upload_max_mb ?? 2048;
  const ready = kind !== null && (isUpload ? !!file && file.size <= maxMb * 1024 * 1024 : locator.trim().length > 0);

  const done = (result: { source: Source; scan: ScanBrief | null }) => {
    onOpenChange(false);
    if (result.scan) {
      toast.success(`Scanning ${result.source.name}`);
      navigate(`/scans/${result.scan.id}`);
    } else {
      toast.success(`${result.source.name} added to ${system.name}`);
    }
  };

  const submit = async () => {
    if (!kind || !ready) return;
    setError(null);
    try {
      if (isUpload && file) {
        const form = new FormData();
        form.append("kind", kind);
        if (name.trim()) form.append("name", name.trim());
        form.append("file", file);
        abort.current = new AbortController();
        setProgress(0);
        const result = await upload<{ source: Source; scan: ScanBrief }>(`/systems/${system.id}/sources/upload`, form, { onProgress: setProgress, signal: abort.current.signal });
        await invalidateDiscovery(client);
        done(result);
      } else {
        const body: NewSource = {
          kind: kind as NewSource["kind"],
          locator: locator.trim(),
          name: name.trim() || undefined,
          options: kind === "git" && ref.trim() ? { ref: ref.trim() } : {},
          scan_now: canScan && scanNow,
        };
        done(await create.mutateAsync(body));
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof ApiError ? e : new ApiError(0, "unknown", "Error", (e as Error).message));
    } finally {
      setProgress(null);
      abort.current = null;
    }
  };

  const meta = kind ? SOURCE_KINDS[kind] : null;
  const available = new Map(caps.data?.source_kinds.map((k) => [k.kind, k]) ?? []);
  const fieldError = error?.field("locator");

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) abort.current?.abort();
        onOpenChange(next);
      }}
      modalLock={busy}
      width={600}
      title={meta ? `Add ${meta.label.toLowerCase()}` : "Add a source"}
      description={meta ? meta.summary : `Choose what FALCON should scan for ${system.name}.`}
      footer={
        kind && (
          <>
            {canScan && !isUpload && (
              <label className="mr-auto flex items-center gap-2 text-subhead text-label-2">
                <Switch checked={scanNow} onChange={setScanNow} label="Scan now" size="sm" />
                Scan now
              </label>
            )}
            <Button
              variant="gray"
              onClick={() => {
                abort.current?.abort();
                onOpenChange(false);
              }}
            >
              Cancel
            </Button>
            <Button variant="filled" onClick={submit} disabled={!ready} loading={busy}>
              {isUpload ? "Upload and scan" : canScan && scanNow ? "Add and scan" : "Add source"}
            </Button>
          </>
        )
      }
    >
      <AnimatePresence mode="wait" initial={false}>
        {!kind ? (
          <motion.div key="kinds" initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.16 }}>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {ORDER.map((k) => {
                const info = available.get(k);
                const disabled = info ? !info.available : false;
                return (
                  <button
                    key={k}
                    type="button"
                    disabled={disabled}
                    onClick={() => choose(k)}
                    className={cn(
                      "hover-light flex items-start gap-3 rounded-[14px] bg-fill-2 p-3.5 text-left transition-[background-color,transform] duration-150 focus-visible:focus-ring",
                      disabled ? "cursor-not-allowed opacity-50" : "hover:bg-fill active:scale-[0.99]",
                    )}
                  >
                    <SourceGlyph kind={k} size={36} />
                    <span className="min-w-0">
                      <span className="block text-callout font-semibold text-label">{SOURCE_KINDS[k].label}</span>
                      <span className="mt-0.5 block text-footnote text-label-2">{disabled && info?.reason ? info.reason : SOURCE_KINDS[k].summary}</span>
                    </span>
                  </button>
                );
              })}
            </div>
            {caps.data && (
              <p className="mt-4 text-footnote text-label-3">
                Engine {caps.data.engine_version} · knowledge base {caps.data.knowledge.algorithms}. Sources are scanned in an isolated process; secrets are never stored.
              </p>
            )}
          </motion.div>
        ) : (
          <motion.div
            key={kind}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 12 }}
            transition={{ duration: 0.16 }}
            className="space-y-4"
          >
            <button type="button" onClick={() => setKind(null)} disabled={busy} className="-ml-1 inline-flex items-center gap-0.5 rounded text-subhead text-accent-ink hover:underline disabled:opacity-40">
              <ChevronLeft className="size-4" /> All source types
            </button>

            {kind === "directory" && (
              <TextField
                label="Folder"
                placeholder={SOURCE_KINDS.directory.placeholder}
                value={locator}
                onChange={(e) => setLocator(e.target.value)}
                error={fieldError}
                spellCheck={false}
                autoFocus={!native}
                className={cn("font-mono text-footnote", native && "pr-[104px]")}
                hint={
                  caps.data && !caps.data.any_folder && caps.data.scan_roots.length
                    ? `Must be inside an allowed scan root: ${caps.data.scan_roots.join(", ")}`
                    : "The folder is read in place; nothing is copied or changed."
                }
                trailing={
                  native && (
                    <Button
                      size="sm"
                      variant="gray"
                      icon={<FolderOpen />}
                      onClick={async () => {
                        const picked = await pickFolder();
                        if (picked) setLocator(picked);
                      }}
                    >
                      Choose…
                    </Button>
                  )
                }
              />
            )}

            {(kind === "archive" || kind === "image-archive") && (
              <FilePicker
                kind={kind}
                file={file}
                path={locator}
                onFile={(f) => {
                  setFile(f);
                  setLocator("");
                }}
                onPath={(p) => {
                  setLocator(p);
                  setFile(null);
                }}
                native={native}
                maxMb={maxMb}
                progress={progress}
                error={fieldError ?? (error && !fieldError ? error.message : undefined)}
              />
            )}

            {kind === "git" && (
              <div className="grid gap-4 sm:grid-cols-[1fr_180px]">
                <TextField
                  label="Repository URL"
                  placeholder={SOURCE_KINDS.git.placeholder}
                  value={locator}
                  onChange={(e) => setLocator(e.target.value)}
                  error={fieldError}
                  spellCheck={false}
                  autoFocus
                  hint="Cloned shallowly; hooks, prompts and submodules are disabled."
                />
                <TextField label="Branch or tag" optional placeholder="main" value={ref} onChange={(e) => setRef(e.target.value)} error={error?.field("ref")} spellCheck={false} />
              </div>
            )}

            {kind === "image-registry" && (
              <TextField
                label="Image"
                placeholder={SOURCE_KINDS["image-registry"].placeholder}
                value={locator}
                onChange={(e) => setLocator(e.target.value)}
                error={fieldError}
                spellCheck={false}
                autoFocus
                hint="Registry, repository and tag or digest. Public images need no sign-in; FALCON uses its configured registry credentials otherwise."
              />
            )}

            {kind === "endpoint" && (
              <TextArea
                label="Endpoints"
                rows={4}
                placeholder={SOURCE_KINDS.endpoint.placeholder}
                value={locator}
                onChange={(e) => setLocator(e.target.value)}
                error={fieldError}
                spellCheck={false}
                autoFocus
                className="font-mono text-footnote"
                hint="One per line: a host name, host:port, IP address or https:// URL. FALCON only performs TLS handshakes; no data is sent."
              />
            )}

            <TextField label="Name" optional placeholder={suggestName(kind, locator, file)} value={name} onChange={(e) => setName(e.target.value)} error={error?.field("name")} />

            {error && !fieldError && kind !== "archive" && kind !== "image-archive" && <p className="text-footnote text-danger-ink">{error.message}</p>}
          </motion.div>
        )}
      </AnimatePresence>
    </Sheet>
  );
}

function suggestName(kind: SourceKind, locator: string, file: File | null): string {
  if (file) return file.name;
  const value = locator.trim();
  if (!value) return "Named after the source";
  if (kind === "endpoint") return value.split(/\s+/)[0];
  return value.replace(/[\\/]+$/, "").split(/[\\/]/).pop()?.replace(/\.git$/, "") || value;
}

function FilePicker({
  kind,
  file,
  path,
  onFile,
  onPath,
  native,
  maxMb,
  progress,
  error,
}: {
  kind: "archive" | "image-archive";
  file: File | null;
  path: string;
  onFile: (f: File) => void;
  onPath: (p: string) => void;
  native: boolean;
  maxMb: number;
  progress: number | null;
  error?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const accept = kind === "archive" ? ARCHIVE_ACCEPT : IMAGE_ACCEPT;
  const tooLarge = file ? file.size > maxMb * 1024 * 1024 : false;

  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => progress === null && input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={cn(
          "flex min-h-[148px] cursor-pointer flex-col items-center justify-center rounded-[16px] px-6 py-6 text-center transition-colors focus-visible:focus-ring",
          "shadow-[inset_0_0_0_1.5px_var(--separator-strong)] [background-image:none]",
          over ? "bg-accent-tint shadow-[inset_0_0_0_1.5px_var(--accent)]" : "bg-surface-2 hover:bg-fill-2",
        )}
        style={{ borderRadius: 16 }}
      >
        <input ref={input} type="file" accept={accept} className="hidden" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
        {file || path ? (
          <>
            <SourceGlyph kind={kind} size={40} />
            <div className="mt-3 max-w-full truncate text-callout font-semibold text-label">{file ? file.name : path.split(/[\\/]/).pop()}</div>
            <div className="max-w-full truncate text-footnote text-label-3">{file ? formatBytes(file.size) : path}</div>
            {progress !== null ? (
              <div className="mt-4 w-full max-w-[280px]">
                <div className="h-1.5 overflow-hidden rounded-full bg-fill">
                  <div className="h-full rounded-full bg-accent transition-[width] duration-200" style={{ width: `${Math.round(progress * 100)}%` }} />
                </div>
                <div className="mt-1.5 text-caption tabular text-label-3">{progress < 1 ? `Uploading · ${Math.round(progress * 100)}%` : "Preparing the scan…"}</div>
              </div>
            ) : (
              <div className="mt-2 text-footnote text-accent-ink">Choose a different file</div>
            )}
          </>
        ) : (
          <>
            <span className="grid size-10 place-items-center rounded-full bg-fill text-label-2">
              <Upload className="size-5" />
            </span>
            <div className="mt-3 text-callout font-medium text-label">{kind === "archive" ? "Drop a .zip, .jar or .tar archive" : "Drop an image saved with docker save"}</div>
            <div className="text-footnote text-label-3">or click to choose · up to {formatInt(maxMb)} MB</div>
          </>
        )}
      </div>
      {native && progress === null && (
        <Button
          variant="plain"
          size="sm"
          icon={<FolderOpen />}
          onClick={async () => {
            const picked = await pickFile(kind === "archive" ? "Choose an archive to scan" : "Choose a saved container image", [
              { name: kind === "archive" ? "Archives" : "Image tarballs", extensions: accept.split(",").map((x) => x.replace(/^\./, "")) },
            ]);
            if (picked) onPath(picked);
          }}
        >
          Scan a file in place instead of uploading
        </Button>
      )}
      {tooLarge && <p className="text-footnote text-danger-ink">This file is larger than the {formatInt(maxMb)} MB upload limit.</p>}
      {error && <p className="text-footnote text-danger-ink">{error}</p>}
    </div>
  );
}
