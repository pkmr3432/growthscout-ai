import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { Button } from "./button";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  className?: string;
}

export function EmptyState({ icon, title, description, action, className = "" }: EmptyStateProps) {
  return (
    <div
      className={`
        flex flex-col items-center justify-center
        py-[var(--space-12)] px-[var(--space-8)]
        text-center
        ${className}
      `}
    >
      <div className="text-[var(--text-muted)] mb-[var(--space-4)]">
        {icon ?? <Inbox className="w-12 h-12" strokeWidth={1.5} aria-hidden="true" />}
      </div>
      <h3 className="text-[1.125rem] font-semibold text-[var(--text-primary)] mb-[var(--space-2)]">
        {title}
      </h3>
      {description && (
        <p className="text-[0.875rem] text-[var(--text-secondary)] max-w-sm mb-[var(--space-6)]">
          {description}
        </p>
      )}
      {action && (
        <Button variant="primary" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
