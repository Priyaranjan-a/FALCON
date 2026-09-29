import { Check } from "lucide-react";
import { motion, useAnimationControls } from "motion/react";
import { useCallback, type ReactNode } from "react";
import { cn } from "@/design/cn";
import { LogoMark } from "@/design/components/Logo";
import type { PasswordCheck } from "@/lib/password";

/** Quiet full-screen canvas for the pre-sign-in flows. */
export function AuthLayout({ children, footer, wide }: { children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  return (
    <div className="relative flex min-h-dvh flex-col items-center overflow-y-auto bg-bg px-4">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-x-0 top-0 h-[60vh]"
        style={{ background: "radial-gradient(60% 50% at 50% 0%, var(--accent-tint) 0%, transparent 70%)" }}
      />
      <div className={cn("relative flex w-full flex-1 flex-col justify-center py-12", wide ? "max-w-[720px]" : "max-w-[400px]")}>{children}</div>
      <footer className="relative pb-6 text-caption text-label-3">
        {footer ?? "FALCON · Post-quantum cryptographic discovery and migration intelligence"}
      </footer>
    </div>
  );
}

export function AuthHeader({ title, subtitle }: { title: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col items-center text-center">
      <LogoMark size={56} className="mb-5 drop-shadow-[0_8px_16px_rgba(0,0,0,0.18)]" />
      <h1 className="text-title-1 text-label">{title}</h1>
      {subtitle && <p className="mt-2 max-w-[340px] text-body text-label-2">{subtitle}</p>}
    </div>
  );
}

/** The macOS "wrong password" shake. */
export function useShake() {
  const controls = useAnimationControls();
  const shake = useCallback(() => {
    controls.start({ x: [0, -10, 9, -7, 5, -2, 0], transition: { duration: 0.45, ease: "easeOut" } });
  }, [controls]);
  return { controls, shake, Shaker: motion.div };
}

export function PasswordChecklist({ checks }: { checks: PasswordCheck[] }) {
  return (
    <ul className="space-y-1" aria-label="Password requirements">
      {checks.map((c) => (
        <li key={c.key} className={cn("flex items-center gap-2 text-footnote transition-colors", c.met ? "text-label-2" : "text-label-3")}>
          <span
            className={cn(
              "grid size-3.5 place-items-center rounded-full transition-[background-color,transform] duration-200",
              c.met ? "scale-100 bg-good" : "scale-90 bg-fill",
            )}
          >
            {c.met && <Check className="size-2.5 text-white" strokeWidth={3.5} />}
          </span>
          {c.label}
          <span className="sr-only">{c.met ? "(met)" : "(not met)"}</span>
        </li>
      ))}
    </ul>
  );
}
