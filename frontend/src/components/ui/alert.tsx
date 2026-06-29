import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Info, AlertTriangle } from "lucide-react";

type AlertVariant = "info" | "success" | "warning" | "error";

interface AlertProps {
  children: ReactNode;
  variant?: AlertVariant;
  title?: string;
  className?: string;
}

const alertConfig: Record<AlertVariant, { bg: string; border: string; icon: typeof Info }> = {
  info: { bg: "bg-[var(--color-info-muted)]", border: "border-[var(--color-info)]", icon: Info },
  success: { bg: "bg-[var(--color-success-muted)]", border: "border-[var(--color-success)]", icon: CheckCircle2 },
  warning: { bg: "bg-[var(--color-warning-muted)]", border: "border-[var(--color-warning)]", icon: AlertTriangle },
  error: { bg: "bg-[var(--color-error-muted)]", border: "border-[var(--color-error)]", icon: AlertCircle },
};

export function Alert({ children, variant = "info", title, className = "" }: AlertProps) {
  const config = alertConfig[variant];
  const Icon = config.icon;

  return (
    <div
      role="alert"
      className={`
        flex gap-[var(--space-3)] p-[var(--space-4)]
        ${config.bg} border-l-4 ${config.border}
        rounded-[var(--radius-md)]
        ${className}
      `}
    >
      <Icon className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex flex-col gap-[var(--space-1)]">
        {title && <p className="text-[0.875rem] font-semibold">{title}</p>}
        <div className="text-[0.875rem]">{children}</div>
      </div>
    </div>
  );
}
