import type { ReactNode } from "react";
import { cn } from "@/design/cn";
import { Card } from "@/design/components/Surface";
import { useTweenedNumber } from "../core/useTween";

/** A number that counts to its value; proportional figures at display sizes. */
export function AnimatedNumber({ value, format = (n) => Math.round(n).toString(), className }: { value: number; format?: (n: number) => string; className?: string }) {
  const shown = useTweenedNumber(value, { duration: 700 });
  return (
    <span className={className} aria-label={format(value)}>
      <span aria-hidden>{format(shown)}</span>
    </span>
  );
}

interface StatProps {
  label: ReactNode;
  value: number;
  format?: (n: number) => string;
  detail?: ReactNode;
  icon?: ReactNode;
  accessory?: ReactNode;
  className?: string;
}

/** Stat tile: label, value, one line of context. The number is the chart. */
export function Stat({ label, value, format, detail, icon, accessory, className }: StatProps) {
  return (
    <Card className={cn("flex min-h-[132px] flex-col", className)}>
      <div className="flex items-center gap-2 text-subhead font-medium text-label-2">
        {icon && <span className="flex text-label-3 [&>svg]:size-4">{icon}</span>}
        {label}
      </div>
      <div className="mt-auto flex items-end justify-between gap-3 pt-4">
        <div className="min-w-0">
          <AnimatedNumber value={value} format={format} className="block text-title-1 text-label" />
          {detail && (
            <div className="mt-1 truncate text-footnote text-label-3" title={typeof detail === "string" ? detail : undefined}>
              {detail}
            </div>
          )}
        </div>
        {accessory}
      </div>
    </Card>
  );
}
