import { Sparkles } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/design/components/Button";
import { Select, Slider } from "@/design/components/Controls";
import { TextArea, TextField } from "@/design/components/Field";
import { Segmented } from "@/design/components/Segmented";
import { Sheet, SheetSection } from "@/design/components/Sheet";
import { Banner } from "@/design/components/Surface";
import { ApiError } from "@/lib/api";
import { formatPercent, formatYears } from "@/lib/format";
import { mosca } from "@/lib/horizon";
import { useCreateSystem, useUpdateSystem, useVocabulary } from "@/lib/queries";
import type { Classification, Criticality, Environment, Exposure, Lifecycle, SystemInput, SystemKind, SystemRecord } from "@/lib/types";
import { MoscaChart, STATUS_META } from "@/viz/charts/MoscaChart";
import { useOrganisationModel } from "../horizon/useThreatModel";

const EMPTY: SystemInput = {
  code: "",
  name: "",
  description: null,
  kind: "application",
  lifecycle: "active",
  environment: "production",
  exposure: "internal",
  criticality: "moderate",
  data_classification: "confidential",
  data_shelf_life_years: 7,
  migration_years: 2,
  owner: null,
  team: null,
  tags: [],
};

function suggestCode(name: string): string {
  const words = name.toUpperCase().replace(/[^A-Z0-9 ]/g, " ").split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  if (words.length === 1) return words[0].slice(0, 8);
  return words.slice(0, 3).map((w) => w.slice(0, words.length > 2 ? 3 : 4)).join("-").slice(0, 24);
}

function toInput(s: SystemRecord): SystemInput {
  return {
    code: s.code,
    name: s.name,
    description: s.description,
    kind: s.kind,
    lifecycle: s.lifecycle,
    environment: s.environment,
    exposure: s.exposure,
    criticality: s.criticality,
    data_classification: s.data_classification,
    data_shelf_life_years: s.data_shelf_life_years,
    migration_years: s.migration_years,
    owner: s.owner,
    team: s.team,
    tags: s.tags,
  };
}

interface SystemSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  system?: SystemRecord;
  onSaved?: (system: SystemRecord) => void;
}

export function SystemSheet({ open, onOpenChange, system, onSaved }: SystemSheetProps) {
  const vocabulary = useVocabulary().data;
  const { model } = useOrganisationModel();
  const create = useCreateSystem();
  const update = useUpdateSystem(system?.id ?? "");
  const [form, setForm] = useState<SystemInput>(EMPTY);
  const [codeTouched, setCodeTouched] = useState(false);
  const [tagsText, setTagsText] = useState("");
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (!open) return;
    const initial = system ? toInput(system) : EMPTY;
    setForm(initial);
    setTagsText(initial.tags.join(", "));
    setCodeTouched(!!system);
    setError(null);
  }, [open, system]);

  const set = <K extends keyof SystemInput>(key: K, value: SystemInput[K]) => setForm((f) => ({ ...f, [key]: value }));

  const preview = useMemo(() => (model ? mosca(model, form.data_shelf_life_years, form.migration_years) : null), [model, form.data_shelf_life_years, form.migration_years]);
  const suggestedX = vocabulary?.classification[form.data_classification].shelf_life_years;
  const suggestedY = vocabulary?.kinds[form.kind].migration_years;
  const pending = create.isPending || update.isPending;
  const valid = form.name.trim().length >= 2 && /^[A-Z0-9][A-Z0-9-]{1,23}$/.test(form.code);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setError(null);
    const tags = tagsText.split(",").map((t) => t.trim()).filter(Boolean);
    const payload: SystemInput = { ...form, tags, owner: form.owner?.trim() || null, team: form.team?.trim() || null, description: form.description?.trim() || null };
    try {
      let saved: SystemRecord;
      if (system) {
        const original = toInput(system);
        const changes = Object.fromEntries(
          Object.entries(payload).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(original[k as keyof SystemInput])),
        ) as Partial<SystemInput>;
        saved = Object.keys(changes).length ? await update.mutateAsync(changes) : system;
        toast.success(`${saved.name} updated`);
      } else {
        saved = await create.mutateAsync(payload);
        toast.success(`${saved.name} registered`, { description: `${STATUS_META[saved.mosca.status].label} under the current threat model.` });
      }
      onOpenChange(false);
      onSaved?.(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err : null);
    }
  };

  const options = <T extends string>(entries: Record<T, { label: string; summary?: string }> | undefined) =>
    entries ? (Object.entries(entries) as [T, { label: string; summary?: string }][]).map(([value, v]) => ({ value, label: v.label, description: v.summary })) : [];

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      width={680}
      modalLock={pending}
      title={system ? `Edit ${system.name}` : "Register a system"}
      description="An application, product or piece of infrastructure whose cryptography FALCON should assess."
      footer={
        <>
          <Button variant="gray" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button variant="filled" type="submit" form="system-form" loading={pending} disabled={!valid}>
            {system ? "Save changes" : "Register system"}
          </Button>
        </>
      }
    >
      <form id="system-form" onSubmit={submit} noValidate>
        {error && (
          <Banner tone="critical" className="mb-2">
            {error.message}
          </Banner>
        )}
        <SheetSection title="Identity">
          <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
            <TextField
              label="Name"
              value={form.name}
              autoFocus
              placeholder="Payments gateway"
              error={error?.field("name")}
              onChange={(e) => {
                const name = e.target.value;
                setForm((f) => ({ ...f, name, code: codeTouched ? f.code : suggestCode(name) }));
              }}
            />
            <TextField
              label="Code"
              value={form.code}
              placeholder="PAY-GW"
              className="font-mono uppercase"
              error={error?.field("code") ?? (form.code && !/^[A-Z0-9][A-Z0-9-]{1,23}$/.test(form.code) ? "Letters, digits and hyphens" : undefined)}
              onChange={(e) => {
                setCodeTouched(true);
                set("code", e.target.value.toUpperCase().replace(/\s+/g, "-"));
              }}
            />
          </div>
          <TextArea label="Description" optional rows={2} value={form.description ?? ""} onChange={(e) => set("description", e.target.value)} placeholder="What the system does and who depends on it" />
          <div className="grid gap-3 sm:grid-cols-3">
            <Select label="Kind" value={form.kind} onChange={(v: SystemKind) => set("kind", v)} options={options(vocabulary?.kinds)} />
            <Select label="Lifecycle" value={form.lifecycle} onChange={(v: Lifecycle) => set("lifecycle", v)} options={options(vocabulary?.lifecycle)} />
            <Select label="Environment" value={form.environment} onChange={(v: Environment) => set("environment", v)} options={options(vocabulary?.environment)} />
          </div>
        </SheetSection>

        <SheetSection title="Business context" description="How much the organisation depends on this system, and what its data is worth.">
          <div className="space-y-1.5">
            <div className="text-subhead font-medium text-label-2">Business criticality</div>
            <Segmented
              label="Business criticality"
              block
              value={form.criticality}
              onChange={(v: Criticality) => set("criticality", v)}
              options={(["low", "moderate", "high", "critical"] as Criticality[]).map((c) => ({ value: c, label: vocabulary?.criticality[c].label ?? c }))}
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Select label="Data classification" value={form.data_classification} onChange={(v: Classification) => set("data_classification", v)} options={options(vocabulary?.classification)} />
            <Select label="Exposure" value={form.exposure} onChange={(v: Exposure) => set("exposure", v)} options={options(vocabulary?.exposure)} />
          </div>
        </SheetSection>

        <SheetSection title="Mosca’s inequality" description="If X + Y exceeds Z, data protected today can be decrypted by a quantum adversary while it still matters.">
          <YearsControl
            label="Data shelf-life (X)"
            help="How long this system’s data must stay confidential."
            value={form.data_shelf_life_years}
            min={0}
            max={50}
            step={1}
            onChange={(v) => set("data_shelf_life_years", v)}
            suggestion={suggestedX}
            suggestionLabel={vocabulary ? `Typical for ${vocabulary.classification[form.data_classification].label.toLowerCase()} data` : undefined}
          />
          <YearsControl
            label="Migration time (Y)"
            help="How long moving this system to post-quantum cryptography will take."
            value={form.migration_years}
            min={0.5}
            max={12}
            step={0.5}
            onChange={(v) => set("migration_years", v)}
            suggestion={suggestedY}
            suggestionLabel={vocabulary ? `Typical for ${vocabulary.kinds[form.kind].label.toLowerCase()} systems` : undefined}
          />
          {preview && model && (
            <div className="rounded-[14px] bg-surface-2 p-4">
              <MoscaChart
                ariaLabel="Mosca preview for this system"
                rows={[{ id: "preview", code: form.code || "NEW", name: form.name || "This system", x: preview.x, y: preview.y, status: preview.status, probability: preview.probability }]}
                z={preview.z}
                labelWidth={150}
              />
              <p className="text-footnote text-label-2">
                {preview.status === "exposed" ? (
                  <>Exposed by <strong className="font-semibold text-label">{formatYears(preview.exposure_years)}</strong>. </>
                ) : (
                  <>Inside the horizon with <strong className="font-semibold text-label">{formatYears(-preview.exposure_years)}</strong> to spare. </>
                )}
                There is a {formatPercent(preview.probability)} chance a CRQC exists before this data expires.
              </p>
            </div>
          )}
        </SheetSection>

        <SheetSection title="Ownership">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Business owner" optional value={form.owner ?? ""} onChange={(e) => set("owner", e.target.value)} placeholder="Head of Payments" />
            <TextField label="Team" optional value={form.team ?? ""} onChange={(e) => set("team", e.target.value)} placeholder="Platform Engineering" />
          </div>
          <TextField label="Tags" optional value={tagsText} onChange={(e) => setTagsText(e.target.value)} placeholder="payments, pci, tier-1" hint="Separate tags with commas." error={error?.field("tags")} />
        </SheetSection>
      </form>
    </Sheet>
  );
}

function YearsControl({
  label,
  help,
  value,
  min,
  max,
  step,
  onChange,
  suggestion,
  suggestionLabel,
}: {
  label: string;
  help: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  suggestion?: number;
  suggestionLabel?: string;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <div>
          <div className="text-subhead font-medium text-label-2">{label}</div>
          <div className="text-footnote text-label-3">{help}</div>
        </div>
        <div className="shrink-0 text-headline tabular text-label">{formatYears(value)}</div>
      </div>
      <Slider label={label} value={value} min={min} max={max} step={step} onChange={onChange} className="mt-1" />
      {suggestion !== undefined && suggestion !== value && (
        <button type="button" onClick={() => onChange(suggestion)} className="mt-0.5 inline-flex items-center gap-1 rounded text-footnote font-medium text-accent-ink hover:underline">
          <Sparkles className="size-3" /> {suggestionLabel}: use {formatYears(suggestion)}
        </button>
      )}
    </div>
  );
}
