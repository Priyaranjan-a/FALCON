import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "../cn";
import { ActivityIndicator } from "./ActivityIndicator";

type Variant = "filled" | "tinted" | "gray" | "plain" | "destructive" | "destructive-tinted" | "bordered";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
  trailingIcon?: ReactNode;
  block?: boolean;
}

const variants: Record<Variant, string> = {
  filled: "bg-accent text-on-accent hover:bg-accent-hover active:brightness-95 shadow-[0_1px_1px_rgba(0,0,0,0.08)]",
  tinted: "bg-accent-tint text-accent-ink hover:bg-[var(--accent-tint-hover)]",
  gray: "bg-fill text-label hover:bg-fill-hover",
  plain: "bg-transparent text-accent-ink hover:bg-accent-tint",
  bordered: "bg-surface text-label shadow-[0_0_0_0.5px_var(--separator-strong),0_1px_2px_rgba(0,0,0,0.05)] hover:bg-surface-2",
  destructive: "bg-danger text-white hover:brightness-110 active:brightness-95",
  "destructive-tinted": "bg-danger-tint text-danger-ink hover:bg-[color-mix(in_srgb,var(--danger)_16%,transparent)]",
};

const sizes: Record<Size, string> = {
  sm: "h-7 px-2.5 gap-1.5 text-subhead rounded-[7px]",
  md: "h-8 px-3.5 gap-1.5 text-callout rounded-[9px]",
  lg: "h-11 px-5 gap-2 text-body font-semibold rounded-[12px]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "gray", size = "md", loading = false, icon, trailingIcon, block, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "hover-light relative inline-flex select-none items-center justify-center whitespace-nowrap font-medium",
        (variant === "filled" || variant === "destructive") && "hover-light-accent",
        "transition-[background-color,box-shadow,filter,transform,opacity] duration-150 ease-out",
        "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40",
        "focus-visible:focus-ring",
        variants[variant],
        sizes[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      <span className={cn("inline-flex items-center gap-[inherit]", loading && "invisible")}>
        {icon && <span className="-ml-0.5 inline-flex shrink-0 [&>svg]:size-[1.1em]">{icon}</span>}
        {children}
        {trailingIcon && <span className="-mr-0.5 inline-flex shrink-0 [&>svg]:size-[1.05em]">{trailingIcon}</span>}
      </span>
      {loading && (
        <span className="absolute inset-0 grid place-items-center">
          <ActivityIndicator size={size === "lg" ? 18 : 14} />
        </span>
      )}
    </button>
  );
});

export const IconButton = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: "sm" | "md" }>(
  function IconButton({ label, className, children, size = "md", type = "button", ...rest }, ref) {
    return (
      <button
        ref={ref}
        type={type}
        aria-label={label}
        title={label}
        className={cn(
          "hover-light inline-grid shrink-0 place-items-center rounded-[8px] text-label-2 transition-[background-color,color,transform] duration-150 [--hover-size:44px]",
          "hover:bg-fill hover:text-label active:scale-[0.94] disabled:opacity-40 focus-visible:focus-ring",
          size === "md" ? "size-8 [&>svg]:size-[18px]" : "size-7 [&>svg]:size-4",
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    );
  },
);
