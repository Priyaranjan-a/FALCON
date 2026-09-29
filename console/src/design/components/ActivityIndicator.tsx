import { cn } from "../cn";

/** Twelve-spoke activity indicator, drawn in the current text colour. */
export function ActivityIndicator({ size = 16, className, label = "Loading" }: { size?: number; className?: string; label?: string }) {
  return (
    <span role="status" aria-label={label} className={cn("inline-block shrink-0", className)} style={{ width: size, height: size }}>
      <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
        {Array.from({ length: 12 }, (_, i) => (
          <rect
            key={i}
            x="11"
            y="1.5"
            width="2"
            height="6"
            rx="1"
            fill="currentColor"
            transform={`rotate(${i * 30} 12 12)`}
            style={{
              animation: "falcon-spoke 1s linear infinite",
              animationDelay: `${(i - 12) / 12}s`,
              opacity: 0.15,
            }}
          />
        ))}
      </svg>
    </span>
  );
}
