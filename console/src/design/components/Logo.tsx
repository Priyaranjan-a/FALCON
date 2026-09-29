import { useId } from "react";
import { cn } from "../cn";

/**
 * The FALCON mark: three descending blades narrowing to a point, the stoop
 * of a diving falcon, and discovery narrowing to focus, on a graphite tile.
 */
export function LogoMark({ size = 28, className }: { size?: number; className?: string }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={cn("shrink-0", className)} aria-hidden>
      <defs>
        <linearGradient id={`${id}t`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3a3a3f" />
          <stop offset="1" stopColor="#141416" />
        </linearGradient>
        <linearGradient id={`${id}g`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#b9d4ff" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="14.5" fill={`url(#${id}t)`} />
      <rect width="64" height="64" rx="14.5" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
      <g fill={`url(#${id}g)`}>
        <path d="M13 15.5h38l-6.2 9.5H19.2z" />
        <path d="M20.6 29.5h22.8l-5.6 8.6H26.2z" />
        <path d="M27.6 42.6h8.8L32 49.4z" />
      </g>
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return <span className={cn("font-display text-[15px] font-semibold tracking-[0.14em] text-label", className)}>FALCON</span>;
}
