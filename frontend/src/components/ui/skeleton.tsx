interface SkeletonProps {
  className?: string;
  width?: string;
  height?: string;
}

export function Skeleton({ className = "", width, height }: SkeletonProps) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-[var(--space-2)]" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height="14px"
          className={i === lines - 1 ? "w-3/4" : "w-full"}
        />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div
      className="bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-[var(--radius-lg)] p-[var(--space-6)]"
      aria-hidden="true"
    >
      <Skeleton height="20px" width="60%" className="mb-[var(--space-4)]" />
      <SkeletonText lines={3} />
    </div>
  );
}
