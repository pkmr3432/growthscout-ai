import type { ReactNode } from "react";

interface PageContainerProps {
  children: ReactNode;
  className?: string;
}

export function PageContainer({ children, className = "" }: PageContainerProps) {
  return (
    <div
      className={`
        w-full max-w-[var(--max-content-width)]
        mx-auto
        px-[var(--space-6)]
        py-[var(--space-6)]
        ${className}
      `}
    >
      {children}
    </div>
  );
}

interface SectionHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export function SectionHeader({ title, description, actions, className = "" }: SectionHeaderProps) {
  return (
    <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-[var(--space-4)] mb-[var(--space-6)] ${className}`}>
      <div>
        <h1 className="text-[1.5rem] font-bold text-[var(--text-primary)] leading-[1.3]">
          {title}
        </h1>
        {description && (
          <p className="text-[0.875rem] text-[var(--text-secondary)] mt-[var(--space-1)]">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-[var(--space-2)]">{actions}</div>}
    </div>
  );
}
