import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode, type TextareaHTMLAttributes } from "react";
import { cn } from "../cn";

interface FieldShellProps {
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  htmlFor: string;
  className?: string;
  children: ReactNode;
  optional?: boolean;
}

/** Label, control, then hint or error, stacked with consistent rhythm. */
export function FieldShell({ label, hint, error, htmlFor, className, children, optional }: FieldShellProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={htmlFor} className="flex items-baseline justify-between text-subhead font-medium text-label-2">
          <span>{label}</span>
          {optional && <span className="text-footnote font-normal text-label-3">Optional</span>}
        </label>
      )}
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-footnote text-danger-ink">
          {error}
        </p>
      ) : hint ? (
        <p id={`${htmlFor}-hint`} className="text-footnote text-label-3">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

const controlBase = cn(
  "w-full min-w-0 rounded-[10px] bg-field text-callout text-label placeholder:text-label-4",
  "shadow-[inset_0_0_0_0.5px_var(--field-border),0_0.5px_1px_rgba(0,0,0,0.04)]",
  "transition-[box-shadow,background-color] duration-150",
  "hover:shadow-[inset_0_0_0_0.5px_var(--separator-strong),0_0.5px_1px_rgba(0,0,0,0.04)]",
  "focus:outline-none focus:shadow-[inset_0_0_0_1px_var(--accent),0_0_0_3.5px_var(--focus-ring)]",
  "disabled:opacity-50",
  "aria-[invalid=true]:shadow-[inset_0_0_0_1px_var(--danger),0_0_0_3px_var(--danger-tint)]",
);

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  leading?: ReactNode;
  trailing?: ReactNode;
  optional?: boolean;
  controlSize?: "md" | "lg";
  containerClassName?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, hint, error, leading, trailing, optional, controlSize = "md", className, containerClassName, id, ...rest },
  ref,
) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <FieldShell label={label} hint={hint} error={error} htmlFor={inputId} className={containerClassName} optional={optional}>
      <div className="relative flex items-center">
        {leading && <span className="pointer-events-none absolute left-2.5 flex text-label-3 [&>svg]:size-4">{leading}</span>}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          className={cn(
            controlBase,
            controlSize === "lg" ? "h-11 px-3.5 text-body" : "h-9 px-3",
            leading && "pl-8",
            trailing && "pr-10",
            className,
          )}
          {...rest}
        />
        {trailing && <span className="absolute right-1.5 flex">{trailing}</span>}
      </div>
    </FieldShell>
  );
});

export const SecureField = forwardRef<HTMLInputElement, Omit<TextFieldProps, "type" | "trailing">>(function SecureField(props, ref) {
  const [visible, setVisible] = useState(false);
  return (
    <TextField
      ref={ref}
      type={visible ? "text" : "password"}
      spellCheck={false}
      autoCapitalize="off"
      trailing={
        <button
          type="button"
          tabIndex={-1}
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          className="grid size-7 place-items-center rounded-md text-label-3 hover:text-label-2"
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      }
      {...props}
    />
  );
});

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  optional?: boolean;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { label, hint, error, optional, className, id, rows = 3, ...rest },
  ref,
) {
  const generated = useId();
  const inputId = id ?? generated;
  return (
    <FieldShell label={label} hint={hint} error={error} htmlFor={inputId} optional={optional}>
      <textarea
        ref={ref}
        id={inputId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        className={cn(controlBase, "resize-none px-3 py-2 leading-5", className)}
        {...rest}
      />
    </FieldShell>
  );
});
