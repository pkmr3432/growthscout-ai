import type { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "warning" | "error" | "info";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const badgeStyles: Record<BadgeVariant, string> = {
  default: "bg-[var(--bg-elevated)] text-[var(--text-secondary)]",
  success: "bg-[var(--color-success-muted)] text-[var(--color-success)]",
  warning: "bg-[var(--color-warning-muted)] text-[var(--color-warning)]",
  error: "bg-[var(--color-error-muted)] text-[var(--color-error)]",
  info: "bg-[var(--color-info-muted)] text-[var(--color-info)]",
};

export function Badge({ children, variant = "default", className = "" }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center
        px-2 py-0.5
        text-[0.75rem] font-medium leading-[1.4]
        rounded-[var(--radius-full)]
        ${badgeStyles[variant]}
        ${className}
      `}
    >
      {children}
    </span>
  );
}
