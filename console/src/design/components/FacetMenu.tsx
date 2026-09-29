import { ChevronDown } from "lucide-react";
import { cn } from "../cn";
import { Menu, MenuCheckItem, MenuContent, MenuItem, MenuSeparator, MenuTrigger } from "./Menu";

/** A filter pill that opens a checklist; tinted with a count while anything is selected. */
export function FacetMenu({ label, options, selected, onChange }: { label: string; options: { value: string; label: string }[]; selected: string[]; onChange: (values: string[]) => void }) {
  return (
    <Menu>
      <MenuTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-subhead font-medium transition-colors focus-visible:focus-ring",
            selected.length ? "bg-accent-tint text-accent-ink" : "bg-fill-2 text-label-2 hover:bg-fill hover:text-label",
          )}
        >
          {label}
          {selected.length > 0 && <span className="grid h-4 min-w-4 place-items-center rounded-full bg-accent px-1 text-[10px] font-bold text-on-accent">{selected.length}</span>}
          <ChevronDown className="size-3.5 opacity-70" />
        </button>
      </MenuTrigger>
      <MenuContent align="start">
        {options.map((o) => (
          <MenuCheckItem key={o.value} checked={selected.includes(o.value)} onChange={(checked) => onChange(checked ? [...selected, o.value] : selected.filter((v) => v !== o.value))}>
            {o.label}
          </MenuCheckItem>
        ))}
        {selected.length > 0 && (
          <>
            <MenuSeparator />
            <MenuItem onSelect={() => onChange([])}>Clear</MenuItem>
          </>
        )}
      </MenuContent>
    </Menu>
  );
}
