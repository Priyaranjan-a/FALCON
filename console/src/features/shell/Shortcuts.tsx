import { Keyboard } from "lucide-react";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { cn } from "@/design/cn";
import { Button } from "@/design/components/Button";
import { Sheet } from "@/design/components/Sheet";
import { bindingFor, displayKeys, eventKeys, isChord, SHORTCUTS, useShortcutPrefs, type ShortcutGroup } from "@/lib/shortcuts";

/** Key caps for a binding: ⌘ K, or G then R. */
export function KeyCaps({ keys, className, muted }: { keys: string; className?: string; muted?: boolean }) {
  const parts = displayKeys(keys);
  if (!parts.length) return <span className={cn("text-footnote text-label-4", className)}>Off</span>;
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      {parts.map((p, i) =>
        p === "then" ? (
          <span key={i} className="text-caption text-label-3">then</span>
        ) : (
          <kbd
            key={i}
            className={cn(
              "inline-grid h-[22px] min-w-[22px] place-items-center rounded-[6px] px-1.5 font-sans text-footnote font-medium",
              "bg-[var(--surface)] shadow-[inset_0_-1px_0_var(--separator-strong),0_0_0_0.5px_var(--separator-strong),0_1px_1px_rgba(0,0,0,0.05)]",
              muted ? "text-label-3" : "text-label",
            )}
          >
            {p}
          </kbd>
        ),
      )}
    </span>
  );
}

function typingIn(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName) || !!target.closest('[role="combobox"], [cmdk-input]');
}

/**
 * One keydown listener for every shortcut. Chords (⌘/Ctrl combinations) work
 * everywhere; plain keys and sequences never fire while typing, while a
 * dialog is open, or when single-key shortcuts are switched off.
 */
export function useShortcutDispatcher(actions: Record<string, () => void>) {
  const prefs = useShortcutPrefs();
  const latest = useRef(actions);
  latest.current = actions;

  useEffect(() => {
    let pending: string | null = null;
    let timer = 0;
    const bindings = SHORTCUTS.map((s) => [s.id, bindingFor(s.id, prefs)] as const).filter(([, k]) => k);
    const fire = (id: string, e: KeyboardEvent) => {
      const action = latest.current[id];
      if (!action) return false;
      e.preventDefault();
      action();
      return true;
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.isComposing || e.repeat) return;
      const keys = eventKeys(e);
      if (!keys) return;
      const chord = bindings.find(([, k]) => isChord(k) && k === keys);
      if (chord) {
        pending = null;
        fire(chord[0], e);
        return;
      }
      if (!prefs.singleKey || typingIn(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector('[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"], [role="menu"]')) return;
      if (pending) {
        const sequence = `${pending} ${keys}`;
        pending = null;
        window.clearTimeout(timer);
        const hit = bindings.find(([, k]) => k === sequence);
        if (hit && fire(hit[0], e)) return;
      }
      const single = bindings.find(([, k]) => k === keys);
      if (single && fire(single[0], e)) return;
      if (bindings.some(([, k]) => k.startsWith(`${keys} `))) {
        pending = keys;
        window.clearTimeout(timer);
        timer = window.setTimeout(() => (pending = null), 1200);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(timer);
    };
  }, [prefs]);
}

const GROUPS: ShortcutGroup[] = ["General", "Navigate", "Appearance"];

/** The ? overlay: every shortcut, as currently bound. */
export function ShortcutsSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const prefs = useShortcutPrefs();
  const navigate = useNavigate();
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title="Keyboard shortcuts"
      description={prefs.singleKey ? "Letter shortcuts work anywhere except while you type in a field." : "Single-key shortcuts are off. Turn them on in Settings."}
      width={640}
      footer={
        <Button
          variant="gray"
          icon={<Keyboard />}
          onClick={() => {
            onOpenChange(false);
            navigate("/settings?section=keyboard");
          }}
        >
          Customise…
        </Button>
      }
    >
      <div className="grid gap-x-8 gap-y-5 pb-2 sm:grid-cols-2">
        {GROUPS.map((group) => (
          <section key={group} className={cn(group === "Navigate" && "sm:row-span-2")}>
            <h3 className="mb-1.5 text-caption font-semibold uppercase tracking-wide text-label-3">{group}</h3>
            <ul>
              {SHORTCUTS.filter((s) => s.group === group).map((s) => {
                const keys = bindingFor(s.id, prefs);
                const off = !keys || (!prefs.singleKey && !isChord(keys));
                return (
                  <li key={s.id} className="flex items-center justify-between gap-3 py-1.5 [&+&]:hairline-t">
                    <span className={cn("text-subhead", off ? "text-label-3" : "text-label")}>{s.label}</span>
                    <KeyCaps keys={off ? "" : keys} />
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </Sheet>
  );
}
