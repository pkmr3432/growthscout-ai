import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: boolean;
}

export function Card({ children, className = "", padding = true }: CardProps) {
  return (
    <div
      className={`
        bg-[var(--bg-surface)] border border-[var(--bg-border)]
        rounded-[var(--radius-lg)] shadow-[var(--shadow-low)]
        ${padding ? "p-[var(--space-6)]" : ""}
        ${className}
      `}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`pb-[var(--space-4)] border-b border-[var(--bg-border)] mb-[var(--space-4)] ${className}`}>
      {children}
    </div>
  );
}

export function CardTitle({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <h3 className={`text-[1.125rem] font-semibold text-[var(--text-primary)] ${className}`}>
      {children}
    </h3>
  );
}
