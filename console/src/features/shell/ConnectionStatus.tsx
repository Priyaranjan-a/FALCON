import { CircleCheck, WifiOff } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { ActivityIndicator } from "@/design/components/ActivityIndicator";
import { spring } from "@/design/motion";
import { ApiError } from "@/lib/api";
import { queryClient } from "@/lib/queries";

/**
 * Says so when FALCON cannot be reached (the network dropped, or the engine
 * stopped), keeps retrying quietly, and refreshes everything the moment it is
 * back, then gets out of the way.
 */
export function ConnectionStatus() {
  const [state, setState] = useState<"ok" | "lost" | "back">(() => (navigator.onLine ? "ok" : "lost"));
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const lose = () => stateRef.current !== "lost" && setState("lost");
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      if (event.type === "updated" && event.action.type === "error" && event.action.error instanceof ApiError && event.action.error.status === 0) lose();
    });
    window.addEventListener("offline", lose);
    return () => {
      unsubscribe();
      window.removeEventListener("offline", lose);
    };
  }, []);

  useEffect(() => {
    if (state === "lost") {
      const probe = window.setInterval(async () => {
        try {
          const r = await fetch("/api/v1/setup", { cache: "no-store" });
          if (r.ok) {
            setState("back");
            void queryClient.refetchQueries({ type: "active" });
          }
        } catch {
          /* still unreachable */
        }
      }, 2500);
      return () => window.clearInterval(probe);
    }
    if (state === "back") {
      const t = window.setTimeout(() => setState("ok"), 2200);
      return () => window.clearTimeout(t);
    }
  }, [state]);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-[60px] z-[65] flex justify-center px-4" role="status" aria-live="polite">
      <AnimatePresence>
        {state !== "ok" && (
          <motion.div
            key={state}
            initial={{ opacity: 0, y: -12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={spring.smooth}
            className="glass-strong pointer-events-auto flex items-center gap-2.5 rounded-full py-2 pl-3 pr-4 text-subhead"
          >
            {state === "lost" ? (
              <>
                <WifiOff className="size-4 text-critical" />
                <span className="font-medium text-label">FALCON can’t be reached</span>
                <span className="text-label-3">Reconnecting</span>
                <ActivityIndicator size={14} />
              </>
            ) : (
              <>
                <CircleCheck className="size-4 text-good" />
                <span className="font-medium text-label">Connected again</span>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
