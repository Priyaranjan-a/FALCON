import { Check } from "lucide-react";
import { DropdownMenu, Tooltip as RadixTooltip } from "radix-ui";
import type { ReactNode } from "react";
import { cn } from "../cn";

/* -------------------------------------------------------------------- Menu */

export const Menu = DropdownMenu.Root;
export const MenuTrigger = DropdownMenu.Trigger;

export function MenuContent({ children, align = "end", className, width }: { children: ReactNode; align?: "start" | "center" | "end"; className?: string; width?: number }) {
  return (
    <DropdownMenu.Portal>
      <DropdownMenu.Content
        align={align}
        sideOffset={6}
        collisionPadding={12}
        style={{ minWidth: width ?? 200 }}
        className={cn(
          "z-50 rounded-[11px] bg-elevated p-[5px] text-callout text-label shadow-pop vibrancy outline-none",
          "origin-[var(--radix-dropdown-menu-content-transform-origin)] data-[state=open]:animate-[falcon-pop_140ms_cubic-bezier(0.22,1,0.36,1)]",
          className,
        )}
      >
        {children}
      </DropdownMenu.Content>
    </DropdownMenu.Portal>
  );
}

const itemClass = cn(
  "relative flex h-7 cursor-pointer select-none items-center gap-2 rounded-[6px] px-2 outline-none",
  "data-[highlighted]:bg-accent data-[highlighted]:text-on-accent data-[disabled]:opacity-40",
  "[&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-label-2 data-[highlighted]:[&>svg]:text-on-accent",
);

export function MenuItem({ children, onSelect, destructive, disabled, icon, shortcut }: { children: ReactNode; onSelect?: () => void; destructive?: boolean; disabled?: boolean; icon?: ReactNode; shortcut?: string }) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      disabled={disabled}
      className={cn(itemClass, destructive && "text-danger-ink data-[highlighted]:bg-danger data-[highlighted]:text-white")}
    >
      {icon}
      <span className="flex-1 truncate">{children}</span>
      {shortcut && <span className="text-footnote tracking-wide opacity-60">{shortcut}</span>}
    </DropdownMenu.Item>
  );
}

export function MenuCheckItem({ children, checked, onChange }: { children: ReactNode; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <DropdownMenu.CheckboxItem
      checked={checked}
      onCheckedChange={onChange}
      onSelect={(e) => e.preventDefault()}
      className={cn(itemClass, "pl-7")}
    >
      <DropdownMenu.ItemIndicator className="absolute left-2 flex">
        <Check className="size-3.5" strokeWidth={2.75} />
      </DropdownMenu.ItemIndicator>
      <span className="flex-1 truncate">{children}</span>
    </DropdownMenu.CheckboxItem>
  );
}

export function MenuRadioGroup<T extends string>({ value, onChange, options }: { value: T; onChange: (value: T) => void; options: { value: T; label: ReactNode }[] }) {
  return (
    <DropdownMenu.RadioGroup value={value} onValueChange={(v) => onChange(v as T)}>
      {options.map((o) => (
        <DropdownMenu.RadioItem key={o.value} value={o.value} className={cn(itemClass, "pl-7")}>
          <DropdownMenu.ItemIndicator className="absolute left-2 flex">
            <Check className="size-3.5" strokeWidth={2.75} />
          </DropdownMenu.ItemIndicator>
          {o.label}
        </DropdownMenu.RadioItem>
      ))}
    </DropdownMenu.RadioGroup>
  );
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <DropdownMenu.Label className="px-2 pb-1 pt-1.5 text-footnote font-semibold text-label-3">{children}</DropdownMenu.Label>;
}

export function MenuSeparator() {
  return <DropdownMenu.Separator className="mx-2 my-[5px] h-px bg-separator" />;
}

/* ----------------------------------------------------------------- Tooltip */

export const TooltipProvider = RadixTooltip.Provider;

export function Tooltip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          sideOffset={6}
          collisionPadding={10}
          className="z-[60] max-w-[260px] rounded-[7px] bg-elevated px-2 py-1 text-footnote text-label shadow-pop vibrancy data-[state=delayed-open]:animate-[falcon-fade_120ms_ease-out]"
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
