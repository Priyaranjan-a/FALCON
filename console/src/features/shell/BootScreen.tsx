import { motion, useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";
import { Button } from "@/design/components/Button";
import { Flyer, type Point } from "@/design/components/Falcon";
import { LogoMark } from "@/design/components/Logo";

/**
 * Shown while FALCON establishes who you are. If that takes longer than
 * 400 ms, a falcon circles the logo, so a fast start never flashes anything.
 */
export function BootScreen({ error, onRetry }: { error?: Error | null; onRetry?: () => void }) {
  const [slow, setSlow] = useState(false);
  const reduce = useReducedMotion();
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 400);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="grid h-dvh place-items-center bg-bg">
      <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }} className="flex flex-col items-center">
        <div style={{ animation: error ? undefined : "falcon-breathe 2.4s ease-in-out infinite" }}>
          <LogoMark size={64} />
        </div>
        <div className="mt-6 flex h-10 flex-col items-center">
          {error ? (
            <>
              <p className="text-subhead text-label-2">{error.message}</p>
              {onRetry && (
                <Button variant="tinted" size="sm" className="mt-3" onClick={onRetry}>
                  Try again
                </Button>
              )}
            </>
          ) : (
            slow && (
              <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-footnote text-label-3" role="status">
                Starting FALCON…
              </motion.p>
            )
          )}
        </div>
      </motion.div>
      {slow && !error && !reduce && <Flyer path={orbit} size={36} />}
    </div>
  );
}

/** A tilted ellipse around the logo, with a gentle rise and fall. */
function orbit(t: number, w: number, h: number): Point {
  const a = t * 1.5;
  return { x: w / 2 + 104 * Math.cos(a), y: h / 2 - 22 + 40 * Math.sin(a) + 6 * Math.sin(a * 2) };
}
