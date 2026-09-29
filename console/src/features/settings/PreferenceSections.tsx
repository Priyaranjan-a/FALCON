import { Check, Keyboard, RotateCcw, Volume1, Volume2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Slider, Switch } from "@/design/components/Controls";
import { Banner, GroupedList, GroupedRow } from "@/design/components/Surface";
import { spring } from "@/design/motion";
import { ACCENTS, setAccent, setReducedTransparency, useAccent, useReducedTransparency } from "@/lib/appearance";
import {
  bindingFor,
  conflictFor,
  displayKeys,
  eventKeys,
  isChord,
  resetShortcuts,
  setBinding,
  setSingleKeyShortcuts,
  SHORTCUTS,
  useShortcutPrefs,
  type ShortcutDef,
  type ShortcutGroup,
} from "@/lib/shortcuts";
import { play, setSoundPrefs, useSoundPrefs, type SoundName } from "@/lib/sound";
import { ExportsPanel } from "../reports/ExportsPanel";
import { KeyCaps } from "../shell/Shortcuts";

function Title({ title, subtitle }: { title: string; subtitle?: ReactNode }) {
  return (
    <div>
      <h2 className="text-title-3 text-label">{title}</h2>
      {subtitle && <p className="mt-1 text-subhead text-label-2">{subtitle}</p>}
    </div>
  );
}

/* ------------------------------------------------------------- appearance */

/** Accent colour swatches, as in macOS System Settings. */
export function AccentAndTransparency() {
  const accent = useAccent();
  const reduced = useReducedTransparency();
  return (
    <>
      <div>
        <div className="mb-2.5 text-subhead font-medium text-label">Accent colour</div>
        <div className="flex flex-wrap gap-3.5" role="radiogroup" aria-label="Accent colour">
          {ACCENTS.map((a) => {
            const selected = accent === a.value;
            return (
              <button
                key={a.value}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={a.label}
                onClick={() => setAccent(a.value)}
                className="group flex w-12 flex-col items-center gap-1.5 rounded-[10px] outline-none"
              >
                <span
                  className={cn(
                    "grid size-7 place-items-center rounded-full transition-[transform,box-shadow] duration-200 group-hover:scale-110 group-active:scale-95 group-focus-visible:focus-ring",
                    selected && "shadow-[0_0_0_2px_var(--surface),0_0_0_4px_var(--label-3)]",
                  )}
                  style={{ background: `linear-gradient(180deg, color-mix(in srgb, ${a.swatch} 82%, white), ${a.swatch})` }}
                >
                  <AnimatePresence>
                    {selected && (
                      <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} transition={spring.snappy}>
                        <Check className="size-3.5 text-white" strokeWidth={3} />
                      </motion.span>
                    )}
                  </AnimatePresence>
                </span>
                <span className={cn("text-caption", selected ? "font-medium text-label" : "text-label-3")}>{a.label}</span>
              </button>
            );
          })}
        </div>
      </div>
      <GroupedList>
        <GroupedRow label="Reduce transparency" description="Solid surfaces instead of glass. Easier to read for some people, and lighter on older graphics hardware.">
          <Switch checked={reduced} onChange={setReducedTransparency} label="Reduce transparency" />
        </GroupedRow>
      </GroupedList>
    </>
  );
}

/* ----------------------------------------------------------------- sounds */

const PREVIEWS: { name: SoundName; label: string }[] = [
  { name: "tap", label: "Click" },
  { name: "toggleOn", label: "Switch" },
  { name: "success", label: "Done" },
  { name: "error", label: "Problem" },
  { name: "notify", label: "Scan finished" },
];

export function SoundSection() {
  const prefs = useSoundPrefs();
  return (
    <>
      <Title title="Sounds" subtitle="Quiet interface sounds, in the manner of macOS: a soft tap when you click, and a chime when something finishes or goes wrong. Stored on this device only." />
      <GroupedList>
        <GroupedRow label="Interface sounds" description="Keyboard actions stay silent.">
          <Switch checked={prefs.enabled} onChange={(on) => setSoundPrefs({ enabled: on })} label="Interface sounds" />
        </GroupedRow>
        <GroupedRow label="Volume">
          <div className="flex w-[240px] max-w-[50vw] items-center gap-2.5">
            <Volume1 className="size-4 shrink-0 text-label-3" />
            <Slider
              value={Math.round(prefs.volume * 100)}
              onChange={(v) => setSoundPrefs({ volume: v / 100 })}
              min={0}
              max={100}
              label="Volume"
              disabled={!prefs.enabled}
            />
            <Volume2 className="size-4 shrink-0 text-label-3" />
          </div>
        </GroupedRow>
      </GroupedList>
      <div>
        <div className="mb-2 text-subhead font-medium text-label">Preview</div>
        <div className="flex flex-wrap gap-2">
          {PREVIEWS.map((p) => (
            <Button key={p.name} size="sm" variant="bordered" disabled={!prefs.enabled} onClick={() => window.setTimeout(() => play(p.name), 60)}>
              {p.label}
            </Button>
          ))}
        </div>
      </div>
    </>
  );
}

/* --------------------------------------------------------------- keyboard */

type Recording = { id: string; first?: string } | null;
type Pending = { def: ShortcutDef; keys: string; conflict: ShortcutDef } | null;

export function KeyboardSection() {
  const prefs = useShortcutPrefs();
  const [recording, setRecording] = useState<Recording>(null);
  const [pending, setPending] = useState<Pending>(null);
  const timer = useRef(0);

  const commit = (def: ShortcutDef, keys: string) => {
    setRecording(null);
    const conflict = conflictFor(def.id, keys);
    if (conflict) setPending({ def, keys, conflict });
    else {
      setBinding(def.id, keys);
      play("success");
    }
  };

  // While recording, every key press is captured here and nowhere else.
  useEffect(() => {
    if (!recording) return;
    const def = SHORTCUTS.find((s) => s.id === recording.id)!;
    const onKey = (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (e.key === "Escape") {
        window.clearTimeout(timer.current);
        setRecording(null);
        return;
      }
      if ((e.key === "Backspace" || e.key === "Delete") && !recording.first) {
        commit(def, "");
        return;
      }
      const keys = eventKeys(e);
      if (!keys) return;
      window.clearTimeout(timer.current);
      if (isChord(keys) || keys.startsWith("Shift+")) {
        commit(def, keys);
      } else if (recording.first) {
        commit(def, `${recording.first} ${keys}`);
      } else {
        // A plain key: wait briefly for a second one ("G", then "R").
        setRecording({ id: def.id, first: keys });
        timer.current = window.setTimeout(() => commit(def, keys), 900);
      }
    };
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
    // commit is stable in behaviour; re-subscribing on every render would drop key presses.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recording]);

  const groups: ShortcutGroup[] = ["General", "Navigate", "Appearance"];
  const customised = Object.keys(prefs.bindings).length > 0;

  return (
    <>
      <Title
        title="Keyboard"
        subtitle="Change any shortcut: choose Change, then press the new keys. Plain letters can be a sequence, such as G then R. Stored on this device only."
      />
      <GroupedList>
        <GroupedRow label="Single-key shortcuts" description="Letters, sequences, / and ?. Turn off if they get in the way of a screen reader or other assistive technology.">
          <Switch checked={prefs.singleKey} onChange={setSingleKeyShortcuts} label="Single-key shortcuts" />
        </GroupedRow>
      </GroupedList>

      <AnimatePresence>
        {pending && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} transition={spring.smooth} className="overflow-hidden">
            <Banner
              tone="warning"
              title={`${displayKeys(pending.keys).join(" ")} is already used for “${pending.conflict.label}”.`}
              action={
                <div className="flex gap-1.5">
                  <Button size="sm" variant="gray" onClick={() => setPending(null)}>
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    variant="filled"
                    onClick={() => {
                      setBinding(pending.conflict.id, "");
                      setBinding(pending.def.id, pending.keys);
                      setPending(null);
                      play("success");
                    }}
                  >
                    Use for {pending.def.label}
                  </Button>
                </div>
              }
            >
              “{pending.conflict.label}” will have no shortcut.
            </Banner>
          </motion.div>
        )}
      </AnimatePresence>

      {groups.map((group) => (
        <div key={group}>
          <div className="mb-1.5 px-1 text-caption font-semibold uppercase tracking-wide text-label-3">{group}</div>
          <GroupedList>
            {SHORTCUTS.filter((s) => s.group === group).map((s) => {
              const keys = bindingFor(s.id, prefs);
              const active = recording?.id === s.id;
              const off = !keys || (!prefs.singleKey && !isChord(keys));
              return (
                <GroupedRow key={s.id} label={s.label}>
                  <div className="flex items-center gap-2">
                    {active ? (
                      <motion.span
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="flex h-[26px] items-center gap-1.5 rounded-[8px] bg-accent-tint px-2.5 text-footnote font-medium text-accent-ink"
                      >
                        <Keyboard className="size-3.5" style={{ animation: "falcon-breathe 1.2s ease-in-out infinite" }} />
                        {recording?.first ? <>{recording.first} then…</> : "Press keys · Esc to cancel · ⌫ to turn off"}
                      </motion.span>
                    ) : (
                      <KeyCaps keys={off ? "" : keys} className={keys !== s.keys ? "[&_kbd]:text-accent-ink" : undefined} />
                    )}
                    <Button size="sm" variant="plain" onClick={() => setRecording(active ? null : { id: s.id })}>
                      {active ? "Cancel" : "Change"}
                    </Button>
                  </div>
                </GroupedRow>
              );
            })}
          </GroupedList>
        </div>
      ))}
      <div>
        <Button variant="gray" icon={<RotateCcw />} disabled={!customised} onClick={resetShortcuts}>
          Restore Defaults
        </Button>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------- exports */

export function ExportsSection() {
  return (
    <>
      <Title title="Exports & downloads" subtitle="Where exported reports, CBOMs, attestations and keys are saved, and everything exported so far." />
      <ExportsPanel limit={10} />
    </>
  );
}
