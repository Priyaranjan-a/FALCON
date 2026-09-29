import { ArrowDownToLine, Boxes, FileSignature, FileWarning, FolderOpen, FolderPen, KeyRound, RotateCcw, Search, X, type LucideIcon } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Tooltip } from "@/design/components/Menu";
import { EmptyState, Skeleton } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { hasNativeDialogs, pickFolder } from "@/lib/desktop";
import { downloadExport, revealExport } from "@/lib/exports";
import { formatRelative } from "@/lib/format";
import { useExportLocationMutations, useExports, useRemoveExport } from "@/lib/queries";
import type { ExportLocation, ExportRecord, ReportFormatId } from "@/lib/types";
import { FORMAT_META } from "./vocab";

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Shortens a long path in the middle, as Finder does: the drive and user, …, then the last folders. */
export function shortPath(path: string, max = 56): string {
  if (path.length <= max) return path;
  const sep = path.includes("\\") ? "\\" : "/";
  const parts = path.split(sep);
  const head = parts.slice(0, Math.min(3, parts.length - 2)).join(sep);
  let tail = parts[parts.length - 1];
  for (let i = parts.length - 2; i >= 3 && head.length + tail.length + parts[i].length + 3 <= max; i--) tail = parts[i] + sep + tail;
  return `${head}${sep}…${sep}${tail}`;
}

function iconFor(e: ExportRecord): LucideIcon {
  if (e.format in FORMAT_META) return FORMAT_META[e.format as ReportFormatId].icon;
  if (e.format === "snapshot-envelope") return FileSignature;
  if (e.format === "key-pem") return KeyRound;
  return Boxes;
}

/** Where exports go: the folder on this computer (desktop), or FALCON's library (server). */
export function ExportLocationBar({ location, compact }: { location: ExportLocation; compact?: boolean }) {
  const { choose, reset, open } = useExportLocationMutations();
  if (!location.desktop) {
    return (
      <div className="flex items-start gap-3 rounded-[12px] bg-fill-2 px-3.5 py-3">
        <ArrowDownToLine className="mt-0.5 size-[18px] shrink-0 text-accent" />
        <p className="text-footnote text-label-2">
          Exports download through your browser to its downloads folder. FALCON also keeps a copy of each one, so you can download
          it again from the list, byte for byte.
        </p>
      </div>
    );
  }
  const change = async () => {
    const picked = hasNativeDialogs() ? await pickFolder("Choose where FALCON saves exports") : window.prompt("Folder for exports", location.path);
    if (!picked) return;
    choose.mutate(picked, {
      onSuccess: (l) => toast.success("Export folder changed", { description: l.path }),
      onError: (e) => toast.error(e.message),
    });
  };
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-2 rounded-[12px] bg-fill-2 px-3.5 py-2.5", compact && "px-3 py-2")}>
      <FolderOpen className="size-[18px] shrink-0 text-accent" />
      <div className="min-w-0 flex-[1_1_220px]">
        <div className="text-caption text-label-3">Saving to{location.custom ? "" : " (default)"}</div>
        <div className="truncate font-mono text-footnote text-label" title={location.path}>
          {shortPath(location.path)}
        </div>
      </div>
      <div className="flex shrink-0 flex-wrap gap-1.5">
        <Button size="sm" variant="bordered" icon={<FolderOpen />} onClick={() => open.mutate(undefined, { onError: (e) => toast.error(e.message) })}>
          Open Folder
        </Button>
        <Button size="sm" variant="bordered" icon={<FolderPen />} loading={choose.isPending} onClick={change}>
          Change…
        </Button>
        {location.custom && (
          <Tooltip content={`Back to ${location.default}`}>
            <Button size="sm" variant="plain" icon={<RotateCcw />} onClick={() => reset.mutate()}>
              Use Default
            </Button>
          </Tooltip>
        )}
      </div>
    </div>
  );
}

/** Recent exports, newest first, with "Show in Folder" (desktop) or "Download" (browser). */
export function ExportList({ items, desktop, limit, dense }: { items: ExportRecord[]; desktop: boolean; limit?: number; dense?: boolean }) {
  const remove = useRemoveExport();
  const shown = limit ? items.slice(0, limit) : items;
  if (shown.length === 0) {
    return (
      <EmptyState
        compact
        icon={<ArrowDownToLine />}
        title="No exports yet"
        message={desktop ? "Files you export appear here, with a shortcut to show them in their folder." : "Files you export appear here, ready to download again."}
      />
    );
  }
  return (
    <ul className={cn("-mx-1 space-y-0.5", !dense && "max-h-[420px] overflow-y-auto px-1")}>
      <AnimatePresence initial={false}>
        {shown.map((e) => {
          const Icon = iconFor(e);
          return (
            <motion.li
              key={e.id}
              layout
              initial={{ opacity: 0, y: -6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, transition: { duration: 0.18 } }}
              transition={spring.smooth}
              className="group relative flex items-center gap-3 rounded-[10px] px-2 py-2 transition-colors hover:bg-fill-2"
            >
              <span className={cn("grid size-9 shrink-0 place-items-center rounded-[10px]", e.available ? "bg-accent-tint text-accent" : "bg-fill text-label-3")}>
                {e.available ? <Icon className="size-[18px]" strokeWidth={1.8} /> : <FileWarning className="size-[18px]" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className={cn("block truncate text-subhead font-medium", e.available ? "text-label" : "text-label-3 line-through")}>{e.filename}</span>
                <span className="block truncate text-caption text-label-3">
                  {e.available ? `${formatSize(e.size)} · ${e.label} · ${formatRelative(e.created_at)}` : "Moved or deleted since it was saved"}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-0.5">
                {e.available &&
                  (desktop ? (
                    <Tooltip content="Show in Folder">
                      <button type="button" aria-label={`Show ${e.filename} in its folder`} onClick={() => void revealExport(e.id)} className="hover-light grid size-8 place-items-center rounded-[8px] text-accent transition-colors hover:bg-accent-tint focus-visible:focus-ring">
                        <Search className="size-4" />
                      </button>
                    </Tooltip>
                  ) : (
                    <Tooltip content="Download again">
                      <button type="button" aria-label={`Download ${e.filename}`} onClick={() => void downloadExport(e)} className="hover-light grid size-8 place-items-center rounded-[8px] text-accent transition-colors hover:bg-accent-tint focus-visible:focus-ring">
                        <ArrowDownToLine className="size-4" />
                      </button>
                    </Tooltip>
                  ))}
                <Tooltip content={desktop ? "Remove from list (the file stays)" : "Remove"}>
                  <button type="button" aria-label={`Remove ${e.filename} from the list`} onClick={() => remove.mutate(e.id)} className="hover-light grid size-8 place-items-center rounded-[8px] text-label-3 opacity-0 transition-[opacity,background-color] hover:bg-fill hover:text-label focus-visible:opacity-100 focus-visible:focus-ring group-hover:opacity-100 max-md:opacity-100">
                    <X className="size-4" />
                  </button>
                </Tooltip>
              </span>
            </motion.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}

/** The location and the history together, for Reports and Settings. */
export function ExportsPanel({ limit }: { limit?: number }) {
  const exports = useExports();
  if (exports.isPending) return <Skeleton className="h-[180px] rounded-[14px]" />;
  if (!exports.data) return null;
  return (
    <div className="space-y-3">
      <ExportLocationBar location={exports.data.location} />
      <ExportList items={exports.data.items} desktop={exports.data.location.desktop} limit={limit} />
    </div>
  );
}
