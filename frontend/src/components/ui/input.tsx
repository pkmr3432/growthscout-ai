import { type InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, id, className = "", ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="flex flex-col gap-[var(--space-1)]">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[0.875rem] font-medium text-[var(--text-secondary)]"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          className={`
            h-10 px-3
            bg-[var(--bg-surface)] border border-[var(--bg-border)]
            rounded-[var(--radius-sm)]
            text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
            transition-colors duration-[var(--duration-fast)]
            hover:border-[var(--text-muted)]
            focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent
            disabled:opacity-50 disabled:pointer-events-none
            ${error ? "border-[var(--color-error)]" : ""}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p id={`${inputId}-error`} className="text-[0.75rem] text-[var(--color-error)]" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
