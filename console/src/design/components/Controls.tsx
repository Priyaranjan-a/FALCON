import { Check, ChevronsUpDown } from "lucide-react";
import { Checkbox as RadixCheckbox, Select as RadixSelect, Slider as RadixSlider, Switch as RadixSwitch } from "radix-ui";
import { useId, type ReactNode } from "react";
import { cn } from "../cn";
import { FieldShell } from "./Field";

/* ------------------------------------------------------------------ Select */

export interface SelectOption<T extends string> {
  value: T;
  label: ReactNode;
  description?: ReactNode;
}

interface SelectProps<T extends string> {
  value: T | undefined;
  onChange: (value: T) => void;
  options: SelectOption<T>[];
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  ariaLabel?: string;
}

/** Pop-up button in the macOS manner: the menu opens over the current value. */
export function Select<T extends string>({ value, onChange, options, label, hint, error, placeholder, disabled, className, ariaLabel }: SelectProps<T>) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} htmlFor={id} className={className}>
      <RadixSelect.Root value={value} onValueChange={(v) => onChange(v as T)} disabled={disabled}>
        <RadixSelect.Trigger
          id={id}
          aria-label={ariaLabel}
          aria-invalid={error ? true : undefined}
          className={cn(
            "flex h-9 w-full min-w-0 items-center justify-between gap-2 rounded-[10px] bg-field pl-3 pr-2 text-left text-callout text-label",
            "shadow-[inset_0_0_0_0.5px_var(--field-border),0_0.5px_1px_rgba(0,0,0,0.04)] transition-shadow",
            "hover:shadow-[inset_0_0_0_0.5px_var(--separator-strong)] focus:outline-none focus-visible:focus-ring",
            "data-[placeholder]:text-label-4 disabled:opacity-50",
          )}
        >
          <span className="truncate">
            <RadixSelect.Value placeholder={placeholder} />
          </span>
          <RadixSelect.Icon className="grid size-5 shrink-0 place-items-center rounded-[5px] bg-accent text-on-accent">
            <ChevronsUpDown className="size-3" strokeWidth={2.5} />
          </RadixSelect.Icon>
        </RadixSelect.Trigger>
        <RadixSelect.Portal>
          <RadixSelect.Content
            position="item-aligned"
            className="z-50 overflow-hidden rounded-[10px] bg-elevated p-1 text-callout shadow-pop vibrancy data-[state=open]:animate-[falcon-pop_140ms_ease-out]"
          >
            <RadixSelect.Viewport>
              {options.map((option) => (
                <RadixSelect.Item
                  key={option.value}
                  value={option.value}
                  className={cn(
                    "relative flex min-h-7 cursor-pointer select-none flex-col justify-center rounded-[6px] py-1 pl-7 pr-3 text-label outline-none",
                    "data-[highlighted]:bg-accent data-[highlighted]:text-on-accent",
                  )}
                >
                  <RadixSelect.ItemIndicator className="absolute left-2 top-1/2 -translate-y-1/2">
                    <Check className="size-3.5" strokeWidth={2.75} />
                  </RadixSelect.ItemIndicator>
                  <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
                  {option.description && <span className="text-footnote opacity-70">{option.description}</span>}
                </RadixSelect.Item>
              ))}
            </RadixSelect.Viewport>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
    </FieldShell>
  );
}

/* ------------------------------------------------------------------ Switch */

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  size?: "sm" | "md";
}

export function Switch({ checked, onChange, label, disabled, size = "md" }: SwitchProps) {
  const md = size === "md";
  return (
    <RadixSwitch.Root
      checked={checked}
      onCheckedChange={onChange}
      disabled={disabled}
      aria-label={label}
      className={cn(
        "relative inline-flex shrink-0 items-center rounded-full bg-fill-hover p-[2px] transition-colors duration-200",
        "data-[state=checked]:bg-accent disabled:opacity-40 focus-visible:focus-ring",
        md ? "h-[22px] w-[38px]" : "h-[18px] w-[30px]",
      )}
    >
      <RadixSwitch.Thumb
        className={cn(
          "block rounded-full bg-white shadow-thumb transition-transform duration-200 ease-[cubic-bezier(0.3,1.3,0.5,1)]",
          md ? "size-[18px] data-[state=checked]:translate-x-4" : "size-[14px] data-[state=checked]:translate-x-3",
        )}
      />
    </RadixSwitch.Root>
  );
}

/* ------------------------------------------------------------------ Slider */

interface SliderProps {
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  label: string;
  disabled?: boolean;
  className?: string;
  ticks?: number[];
}

export function Slider({ value, onChange, min, max, step = 1, label, disabled, className, ticks }: SliderProps) {
  return (
    <RadixSlider.Root
      value={[value]}
      onValueChange={([v]) => onChange(v)}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      aria-label={label}
      className={cn("relative flex h-6 w-full touch-none select-none items-center", disabled && "opacity-40", className)}
    >
      <RadixSlider.Track className="relative h-1 grow overflow-hidden rounded-full bg-fill-hover">
        <RadixSlider.Range className="absolute h-full rounded-full bg-accent" />
      </RadixSlider.Track>
      {ticks?.map((t) => (
        <span
          key={t}
          aria-hidden
          className="pointer-events-none absolute top-[calc(50%+6px)] h-1 w-px bg-label-4"
          style={{ left: `calc(${((t - min) / (max - min)) * 100}% + ${10 - ((t - min) / (max - min)) * 20}px)` }}
        />
      ))}
      <RadixSlider.Thumb className="block size-5 rounded-full bg-white shadow-thumb transition-transform duration-150 hover:scale-105 active:scale-95 focus-visible:focus-ring" />
    </RadixSlider.Root>
  );
}

/* ---------------------------------------------------------------- Checkbox */

interface CheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export function Checkbox({ checked, onChange, label, description, disabled }: CheckboxProps) {
  const id = useId();
  return (
    <div className="flex items-start gap-2.5">
      <RadixCheckbox.Root
        id={id}
        checked={checked}
        onCheckedChange={(v) => onChange(v === true)}
        disabled={disabled}
        className={cn(
          "mt-0.5 grid size-4 shrink-0 place-items-center rounded-[4.5px] bg-field shadow-[inset_0_0_0_0.5px_var(--separator-strong)]",
          "transition-colors data-[state=checked]:bg-accent data-[state=checked]:shadow-none focus-visible:focus-ring disabled:opacity-40",
        )}
      >
        <RadixCheckbox.Indicator>
          <Check className="size-3 text-on-accent" strokeWidth={3.25} />
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
      <label htmlFor={id} className="flex flex-col">
        <span className="text-callout text-label">{label}</span>
        {description && <span className="text-footnote text-label-3">{description}</span>}
      </label>
    </div>
  );
}
