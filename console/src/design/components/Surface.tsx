import { AlertTriangle, CircleCheck, Info, OctagonAlert } from "lucide-react";
import type { CSSProperties, HTMLAttributes, ReactNode } from "react";
import { cn } from "../cn";
import { initials } from "@/lib/format";

/* -------------------------------------------------------------------- Card */

export function Card({ className, children, padded = true, ...rest }: HTMLAttributes<HTMLDivElement> & { padded?: boolean }) {
  return (
    <div className={cn("glass rounded-[18px]", padded && "p-5", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, actions, className }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    // On a narrow card the actions wrap under the title instead of squeezing it into a column.
    <div className={cn("mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-3", className)}>
      <div className="min-w-0 flex-[1_1_280px]">
        <h2 className="text-headline text-label">{title}</h2>
        {subtitle && <p className="mt-0.5 text-subhead text-label-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex max-w-full shrink-0 flex-wrap items-center gap-1.5">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------- Badge */

type Tone = "neutral" | "accent" | "good" | "warning" | "serious" | "critical";

const tones: Record<Tone, { bg: string; dot: string }> = {
  neutral: { bg: "bg-fill-2", dot: "bg-label-3" },
  accent: { bg: "bg-accent-tint", dot: "bg-accent" },
  good: { bg: "bg-[var(--status-good-tint)]", dot: "bg-good" },
  warning: { bg: "bg-[var(--status-warning-tint)]", dot: "bg-warning" },
  serious: { bg: "bg-[var(--status-serious-tint)]", dot: "bg-serious" },
  critical: { bg: "bg-[var(--status-critical-tint)]", dot: "bg-critical" },
};

/** Status is never colour alone: a dot or icon pairs with a text label in ink. */
export function Badge({ tone = "neutral", children, icon, dot = true, className }: { tone?: Tone; children: ReactNode; icon?: ReactNode; dot?: boolean; className?: string }) {
  return (
    <span className={cn("inline-flex h-[22px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2 text-footnote font-medium text-label", tones[tone].bg, className)}>
      {icon ? <span className="flex [&>svg]:size-3.5">{icon}</span> : dot ? <span className={cn("size-1.5 rounded-full", tones[tone].dot)} /> : null}
      {children}
    </span>
  );
}

export function Chip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex h-[20px] items-center rounded-[5px] bg-fill-2 px-1.5 font-mono text-[11px] font-medium tracking-tight text-label-2", className)}>
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- Skeleton */

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return (
    <div aria-hidden className={cn("relative overflow-hidden rounded-[8px] bg-[var(--skeleton)]", className)} style={style}>
      <div
        className="absolute inset-0"
        style={{
          background: "linear-gradient(90deg, transparent, var(--skeleton-shine), transparent)",
          animation: "falcon-shimmer 1.6s cubic-bezier(0.4, 0, 0.2, 1) infinite",
        }}
      />
    </div>
  );
}

/* -------------------------------------------------------------- EmptyState */

export function EmptyState({ icon, title, message, action, className, compact }: { icon: ReactNode; title: ReactNode; message: ReactNode; action?: ReactNode; className?: string; compact?: boolean }) {
  return (
    <div className={cn("flex flex-col items-center text-center", compact ? "py-8" : "py-14", className)}>
      <div className="mb-4 grid size-12 place-items-center rounded-[14px] bg-fill-2 text-label-3 [&>svg]:size-6">{icon}</div>
      <h3 className="text-headline text-label">{title}</h3>
      <p className="mt-1 max-w-[380px] text-subhead text-label-2">{message}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ Avatar */

export function Avatar({ name, size = 28, className }: { name: string; size?: number; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("inline-grid shrink-0 place-items-center rounded-full font-semibold text-white", className)}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.4),
        background: "linear-gradient(180deg, #a5abb8 0%, #858994 100%)",
        letterSpacing: "0.01em",
      }}
    >
      {initials(name)}
    </span>
  );
}

/* --------------------------------------------------------------------- Kbd */

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] bg-fill-2 px-1 font-sans text-[11px] font-medium text-label-3 shadow-[inset_0_-0.5px_0_var(--separator-strong)]">
      {children}
    </kbd>
  );
}

/* ------------------------------------------------------------ Grouped list */

/** Inset grouped list, as in System Settings: rows separated by inset hairlines. */
export function GroupedList({ children, className, header, footer }: { children: ReactNode; className?: string; header?: ReactNode; footer?: ReactNode }) {
  return (
    <div className={className}>
      {header && <h3 className="mb-1.5 px-1 text-subhead font-semibold text-label-2">{header}</h3>}
      <div className="glass overflow-hidden rounded-[14px]">{children}</div>
      {footer && <p className="mt-1.5 px-1 text-footnote text-label-3">{footer}</p>}
    </div>
  );
}

export function GroupedRow({ label, value, children, icon, className, description }: { label?: ReactNode; value?: ReactNode; children?: ReactNode; icon?: ReactNode; className?: string; description?: ReactNode }) {
  return (
    <div className={cn("relative flex min-h-11 items-center gap-3 px-4 py-2.5 [&+&]:before:absolute [&+&]:before:inset-x-4 [&+&]:before:top-0 [&+&]:before:h-px [&+&]:before:bg-separator", className)}>
      {icon && <span className="flex text-label-2 [&>svg]:size-[18px]">{icon}</span>}
      {label !== undefined && (
        <div className="min-w-0 flex-1">
          <div className="text-callout text-label">{label}</div>
          {description && <div className="text-footnote text-label-3">{description}</div>}
        </div>
      )}
      {value !== undefined && <div className="min-w-0 text-right text-callout text-label-2">{value}</div>}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ Banner */

const bannerIcon = { info: Info, success: CircleCheck, warning: AlertTriangle, critical: OctagonAlert };
const bannerTone = {
  info: "bg-accent-tint [&_svg]:text-accent",
  success: "bg-[var(--status-good-tint)] [&_svg]:text-good",
  warning: "bg-[var(--status-warning-tint)] [&_svg]:text-[var(--status-warning)]",
  critical: "bg-[var(--status-critical-tint)] [&_svg]:text-critical",
};

export function Banner({ tone = "info", title, children, action, className }: { tone?: keyof typeof bannerIcon; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  const Icon = bannerIcon[tone];
  return (
    <div role={tone === "critical" ? "alert" : "status"} className={cn("flex items-start gap-3 rounded-[12px] px-3.5 py-3", bannerTone[tone], className)}>
      <Icon className="mt-px size-[18px] shrink-0" />
      <div className="min-w-0 flex-1 text-subhead text-label">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className={cn(title && "mt-0.5 text-label-2")}>{children}</div>}
      </div>
      {action}
    </div>
  );
}
