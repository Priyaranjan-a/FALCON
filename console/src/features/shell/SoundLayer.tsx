import { useEffect } from "react";
import { play } from "@/lib/sound";

const INTERACTIVE = [
  "button", "a[href]", "summary", "select", "[cmdk-item]",
  '[role="button"]', '[role="tab"]', '[role="menuitem"]', '[role="menuitemradio"]', '[role="menuitemcheckbox"]',
  '[role="option"]', '[role="switch"]', '[role="checkbox"]', '[role="radio"]', '[role="slider"]',
].join(",");

/**
 * Plays interface sounds for the whole console without touching any
 * component: a soft tap when something clickable is pressed, a rising or
 * falling pair for switches, and a chime when a success or error
 * notification appears. Keyboard activation stays silent, as on macOS.
 */
export function SoundLayer() {
  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      if (e.button !== 0 || !(e.target instanceof Element)) return;
      const el = e.target.closest(INTERACTIVE);
      if (!el || el.matches(':disabled, [aria-disabled="true"], [data-disabled]')) return;
      if (el.getAttribute("role") === "switch") play(el.getAttribute("aria-checked") === "true" ? "toggleOff" : "toggleOn");
      else play("tap");
    };
    document.addEventListener("pointerdown", onDown, { capture: true, passive: true });

    const heard = new WeakSet<Element>();
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        record.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) return;
          const toast = node.matches("[data-sonner-toast]") ? node : node.querySelector("[data-sonner-toast]");
          if (!toast || heard.has(toast)) return;
          heard.add(toast);
          const type = toast.getAttribute("data-type");
          if (type === "success") play("success");
          else if (type === "error") play("error");
        });
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      document.removeEventListener("pointerdown", onDown, { capture: true });
      observer.disconnect();
    };
  }, []);
  return null;
}
