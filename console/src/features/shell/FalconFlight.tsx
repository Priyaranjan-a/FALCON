import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { FalconBird, Flyer, type Point } from "@/design/components/Falcon";
import { usePageLoading } from "@/lib/loading";

const SHOW_AFTER = 280; // fast loads never show the falcon
const MIN_VISIBLE = 900; // once it is flying, it completes a graceful pass

/**
 * FALCON's loading indicator: while a page or its data loads, a small falcon
 * flies figure-eights over the whole platform, then peels away and leaves
 * when everything has arrived.
 */
export function FalconFlight() {
  const fetching = useIsFetching({ predicate: (q) => q.state.status === "pending" && q.state.fetchStatus === "fetching" });
  const mutating = useIsMutating();
  const pageLoading = usePageLoading();
  const busy = fetching > 0 || mutating > 0 || pageLoading;
  const reduce = useReducedMotion();

  const [phase, setPhase] = useState<"idle" | "flying" | "leaving">("idle");
  const shownAt = useRef(0);
  const flight = useRef(0); // new key per flight, so each one starts fresh

  useEffect(() => {
    if (busy && phase === "idle") {
      const t = window.setTimeout(() => {
        flight.current += 1;
        shownAt.current = performance.now();
        setPhase("flying");
      }, SHOW_AFTER);
      return () => window.clearTimeout(t);
    }
    if (!busy && phase === "flying") {
      const wait = Math.max(0, MIN_VISIBLE - (performance.now() - shownAt.current));
      const t = window.setTimeout(() => setPhase("leaving"), wait);
      return () => window.clearTimeout(t);
    }
    if (busy && phase === "leaving") setPhase("flying");
  }, [busy, phase]);

  if (phase === "idle") return null;

  if (reduce) {
    return (
      <div className="pointer-events-none fixed left-1/2 top-3 z-[70] -translate-x-1/2" role="status" aria-label="Loading">
        <div className="glass-strong rounded-full px-3 py-1.5" style={{ animation: "falcon-breathe 1.6s ease-in-out infinite" }}>
          <FalconBird size={30} className="[&_.falcon-wing]:![animation:none]" />
        </div>
      </div>
    );
  }

  return (
    <>
      <span className="sr-only" role="status">
        Loading
      </span>
      <Flyer
        key={flight.current}
        className="z-[70]"
        path={roam}
        enterFrom={(_w, h) => ({ x: -60, y: h * 0.3 })}
        leaving={phase === "leaving"}
        onGone={() => setPhase("idle")}
        size={64}
      />
    </>
  );
}

/**
 * A lazy figure-eight across the whole window, with a slow drift and a little
 * bob so no two passes look the same.
 */
function roam(t: number, w: number, h: number): Point {
  const margin = 70;
  const ax = Math.max(80, w / 2 - margin);
  const ay = Math.max(60, h * 0.26);
  const phase = t * 0.52 - Math.PI / 2; // starts at the left edge
  const x = w / 2 + ax * Math.sin(phase);
  const y = h * 0.42 + ay * Math.sin(2 * phase) * 0.9 + Math.sin(t * 2.3) * 6 + Math.sin(t * 0.21) * h * 0.06;
  return { x, y };
}
