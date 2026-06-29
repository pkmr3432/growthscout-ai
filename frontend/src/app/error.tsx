"use client";

import { useEffect } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorBoundary({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log error to console/observability platform
    console.error("App boundary caught runtime exception:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div className="p-[var(--space-4)] bg-[var(--color-error-muted)] text-[var(--color-error)] rounded-full mb-[var(--space-4)]">
        <AlertTriangle className="w-10 h-10" />
      </div>
      <h1 className="text-[1.5rem] font-bold tracking-tight mb-[var(--space-2)]">
        Something went wrong
      </h1>
      <p className="text-[0.875rem] text-[var(--text-secondary)] max-w-md mb-[var(--space-6)]">
        An unexpected error occurred while rendering the application shell. {"Let's"} try reloading or resetting the view context.
      </p>
      {error.digest && (
        <code className="block text-[0.75rem] text-[var(--text-muted)] bg-[var(--bg-surface)] px-2 py-1 rounded border border-[var(--bg-border)] mb-[var(--space-6)] font-mono">
          Digest: {error.digest}
        </code>
      )}
      <div className="flex items-center gap-[var(--space-3)]">
        <Button variant="primary" onClick={reset}>
          Reset View
        </Button>
        <Button variant="secondary" onClick={() => window.location.reload()}>
          Reload Page
        </Button>
      </div>
    </div>
  );
}
