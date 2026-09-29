/**
 * Saving an export. The server writes the file, then:
 *  - in the desktop app it is already in the user's export folder, and the
 *    toast offers "Show in Folder";
 *  - in a browser the stored file is downloaded, under its own name.
 * Either way the export joins the history, and the toolbar's downloads button
 * acknowledges it the way Safari's does.
 */
import { toast } from "sonner";
import { api, download } from "./api";
import { queryClient } from "./queries";
import type { ExportLocation, ExportRecord, ExportRequest } from "./types";

type Listener = (e: ExportRecord) => void;
const listeners = new Set<Listener>();

/** Subscribe to finished exports (the toolbar button bounces). */
export function onExported(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function folderName(path: string): string {
  const parts = path.split(/[\\/]/).filter(Boolean);
  return parts.slice(-2).join(path.includes("\\") ? "\\" : "/") || path;
}

export async function revealExport(id: string): Promise<void> {
  try {
    await api.post(`/reports/exports/${id}/reveal`);
  } catch (e) {
    toast.error((e as Error).message);
  }
}

export async function downloadExport(e: ExportRecord): Promise<void> {
  try {
    await download(`/reports/exports/${e.id}/file`);
  } catch (err) {
    toast.error((err as Error).message);
  }
}

export async function saveExport(request: ExportRequest): Promise<ExportRecord> {
  const record = await api.post<ExportRecord>("/reports/exports", request);
  const cache = queryClient.getQueryData<{ items: ExportRecord[]; location: ExportLocation }>(["reports", "exports"]);
  if (cache) queryClient.setQueryData(["reports", "exports"], { ...cache, items: [record, ...cache.items.filter((x) => x.id !== record.id)] });
  void queryClient.invalidateQueries({ queryKey: ["reports", "exports"] });

  if (record.path) {
    toast.success(`${record.label} saved`, {
      description: `${record.filename} · in ${folderName(record.path.slice(0, record.path.length - record.filename.length))}`,
      action: { label: "Show in Folder", onClick: () => void revealExport(record.id) },
    });
  } else {
    await download(`/reports/exports/${record.id}/file`);
    toast.success(`${record.label} downloaded`, { description: record.filename });
  }
  listeners.forEach((l) => l(record));
  return record;
}
