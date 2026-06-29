import Link from "next/link";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4 text-center">
      <div className="flex items-center gap-[var(--space-2)] mb-[var(--space-6)]">
        <Sparkles className="w-10 h-10 text-[var(--color-primary)] animate-pulse" />
        <span className="text-[1.5rem] font-bold">GrowthScout AI</span>
      </div>
      <h1 className="text-[3rem] font-extrabold tracking-tight mb-[var(--space-2)]">404</h1>
      <h2 className="text-[1.25rem] font-semibold text-[var(--text-secondary)] mb-[var(--space-4)]">
        Page Not Found
      </h2>
      <p className="text-[0.875rem] text-[var(--text-muted)] max-w-md mb-[var(--space-6)]">
        The workspace route you are looking for does not exist or has been moved. Check the URL or return to the main dashboard.
      </p>
      <Link href="/">
        <Button variant="primary">Return to Dashboard</Button>
      </Link>
    </div>
  );
}
