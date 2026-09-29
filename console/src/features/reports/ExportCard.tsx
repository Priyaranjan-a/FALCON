import { ArrowDownToLine, Check } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";
import { cn } from "@/design/cn";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { Select } from "@/design/components/Controls";
import { Card, CardHeader, Chip, Skeleton } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { saveExport } from "@/lib/exports";
import { useReportFormats, useSystems } from "@/lib/queries";
import type { ReportFormat, ReportFormatId } from "@/lib/types";
import { FORMAT_META } from "./vocab";

type TileState = "idle" | "busy" | "done";

/** Every standard format, one press away, for the whole estate or one system. */
export function ExportCard() {
  const formats = useReportFormats();
  const systems = useSystems({ sort: "name" });
  const [scope, setScope] = useState("all");
  const [state, setState] = useState<Partial<Record<ReportFormatId, TileState>>>({});

  const run = async (format: ReportFormat) => {
    if (state[format.id] === "busy") return;
    setState((s) => ({ ...s, [format.id]: "busy" }));
    try {
      await saveExport({ format: format.id, system_id: scope === "all" ? null : scope });
      setState((s) => ({ ...s, [format.id]: "done" }));
      window.setTimeout(() => setState((s) => ({ ...s, [format.id]: "idle" })), 1800);
    } catch (e) {
      setState((s) => ({ ...s, [format.id]: "idle" }));
      toast.error((e as Error).message);
    }
  };

  const scopeOptions = [
    { value: "all", label: "All systems" },
    ...(systems.data?.items ?? []).map((s) => ({ value: s.id, label: `${s.name}`, description: s.code })),
  ];

  return (
    <Card>
      <CardHeader
        title="Export"
        subtitle="The inventory and its assessment in the formats other tools read. Every export is saved, listed below and recorded in the audit ledger."
        actions={<Select value={scope} onChange={setScope} options={scopeOptions} ariaLabel="Scope" className="w-[220px] max-sm:w-full" />}
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {formats.isPending
          ? Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-[118px] rounded-[14px]" />)
          : (formats.data ?? []).map((f) => <FormatTile key={f.id} format={f} state={state[f.id] ?? "idle"} onPress={() => run(f)} />)}
      </div>
    </Card>
  );
}

function FormatTile({ format, state, onPress }: { format: ReportFormat; state: TileState; onPress: () => void }) {
  const meta = FORMAT_META[format.id];
  const Icon = meta.icon;
  return (
    <button
      type="button"
      onClick={onPress}
      aria-busy={state === "busy" || undefined}
      className={cn(
        "hover-light hover-lift group relative flex min-h-[118px] flex-col rounded-[14px] p-4 text-left",
        "bg-[var(--fill-2)] shadow-[inset_0_0_0_0.5px_var(--separator)] transition-[background-color,box-shadow,transform] duration-200 ease-out",
        "hover:bg-[var(--surface)] hover:shadow-[inset_0_0_0_0.5px_var(--separator-strong),var(--shadow-glass-hover)] active:scale-[0.985] focus-visible:focus-ring",
      )}
    >
      <div className="flex items-start gap-3">
        <span className="relative grid size-10 shrink-0 place-items-center rounded-[11px] bg-accent-tint text-accent">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={state}
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={spring.snappy}
              className="flex"
            >
              {state === "busy" ? <ActivityIndicator size={18} /> : state === "done" ? <Check className="size-5 text-good" strokeWidth={2.6} /> : <Icon className="size-5" strokeWidth={1.8} />}
            </motion.span>
          </AnimatePresence>
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-headline text-label">{format.label}</span>
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-caption text-label-3">
            <span className="truncate">{meta.standard}</span>
            <Chip className="shrink-0">.{format.extension}</Chip>
          </div>
        </div>
        <ArrowDownToLine className="mt-1 size-4 shrink-0 text-label-3 opacity-0 transition-[opacity,transform] duration-200 group-hover:translate-y-0.5 group-hover:opacity-100" />
      </div>
      <p className="mt-2.5 line-clamp-2 text-footnote text-label-2">{format.summary}</p>
    </button>
  );
}
