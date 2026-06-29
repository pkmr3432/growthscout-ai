"use client";

import Link from "next/link";
import { ChevronRight, Home } from "lucide-react";
import { usePathname } from "next/navigation";
import { useMemo } from "react";

const labelMap: Record<string, string> = {
  "": "Dashboard",
  discovery: "Discovery",
  sessions: "Sessions",
  reports: "Reports",
  metrics: "Metrics",
  developer: "Developer Hub",
  settings: "Settings",
};

export function Breadcrumbs() {
  const pathname = usePathname();

  const crumbs = useMemo(() => {
    const segments = pathname.split("/").filter(Boolean);
    if (segments.length === 0) return [];

    return segments.map((seg, i) => ({
      label: labelMap[seg] ?? seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      href: "/" + segments.slice(0, i + 1).join("/"),
      isLast: i === segments.length - 1,
    }));
  }, [pathname]);

  if (crumbs.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-[var(--space-1)] text-[0.8125rem]">
        <li>
          <Link
            href="/"
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors duration-[var(--duration-fast)]"
            aria-label="Home"
          >
            <Home className="w-4 h-4" aria-hidden="true" />
          </Link>
        </li>
        {crumbs.map((crumb) => (
          <li key={crumb.href} className="flex items-center gap-[var(--space-1)]">
            <ChevronRight className="w-3.5 h-3.5 text-[var(--text-muted)]" aria-hidden="true" />
            {crumb.isLast ? (
              <span className="text-[var(--text-primary)] font-medium" aria-current="page">
                {crumb.label}
              </span>
            ) : (
              <Link
                href={crumb.href}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors duration-[var(--duration-fast)]"
              >
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
