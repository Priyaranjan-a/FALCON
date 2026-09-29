import { LayoutGroup, motion } from "motion/react";
import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "../cn";
import { spring } from "../motion";

export interface SegmentedOption<T extends string> {
  value: T;
  label: ReactNode;
  disabled?: boolean;
}

interface SegmentedProps<T extends string> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  size?: "sm" | "md";
  block?: boolean;
  className?: string;
}

/** Segmented control. The selection thumb glides between segments on a spring. */
export function Segmented<T extends string>({ options, value, onChange, label, size = "md", block, className }: SegmentedProps<T>) {
  const group = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (event: KeyboardEvent, index: number) => {
    const delta = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!delta) return;
    event.preventDefault();
    for (let step = 1; step <= options.length; step++) {
      const next = (index + delta * step + options.length) % options.length;
      if (!options[next].disabled) {
        onChange(options[next].value);
        refs.current[next]?.focus();
        return;
      }
    }
  };

  return (
    <LayoutGroup id={group}>
      <div
        role="radiogroup"
        aria-label={label}
        className={cn(
          "relative inline-flex rounded-[9px] bg-fill p-[2px]",
          size === "sm" ? "h-7" : "h-8",
          block && "flex w-full",
          className,
        )}
      >
        {options.map((option, index) => {
          const selected = option.value === value;
          return (
            <button
              key={option.value}
              ref={(el) => {
                refs.current[index] = el;
              }}
              type="button"
              role="radio"
              aria-checked={selected}
              tabIndex={selected ? 0 : -1}
              disabled={option.disabled}
              onClick={() => onChange(option.value)}
              onKeyDown={(e) => move(e, index)}
              className={cn(
                "relative isolate flex items-center justify-center whitespace-nowrap rounded-[7px] font-medium",
                block ? "min-w-0 flex-1" : "shrink-0",
                "transition-colors duration-150 disabled:opacity-40 focus-visible:focus-ring",
                size === "sm" ? "px-2.5 text-footnote" : "px-3.5 text-subhead",
                selected ? "text-label" : "text-label-2 hover:text-label",
              )}
            >
              {selected && (
                <motion.span
                  layoutId="thumb"
                  transition={spring.snappy}
                  className="absolute inset-0 -z-10 rounded-[7px] bg-[var(--segment-thumb)] shadow-thumb"
                />
              )}
              <span className={cn(block && "truncate")}>{option.label}</span>
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
}
