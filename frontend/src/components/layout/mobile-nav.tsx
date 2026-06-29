"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { X, LayoutDashboard, Search, FolderKanban, FileBarChart, Activity, Code2, Settings, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef } from "react";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Discovery", href: "/discovery", icon: Search },
  { label: "Sessions", href: "/sessions", icon: FolderKanban },
  { label: "Reports", href: "/reports", icon: FileBarChart },
  { label: "Metrics", href: "/metrics", icon: Activity },
  { label: "Developer Hub", href: "/developer", icon: Code2 },
  { label: "Settings", href: "/settings", icon: Settings },
];

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

export function MobileNav({ open, onClose }: MobileNavProps) {
  const pathname = usePathname();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      closeRef.current?.focus();
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (open) window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Close drawer on route change
  useEffect(() => { onClose(); }, [pathname, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[1000] lg:hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <nav
        className="
          absolute left-0 top-0 bottom-0
          w-[280px] max-w-[80vw]
          bg-[var(--bg-surface)] border-r border-[var(--bg-border)]
          shadow-[var(--shadow-high)]
          flex flex-col
          animate-in slide-in-from-left
        "
        aria-label="Mobile navigation"
      >
        {/* Drawer Header */}
        <div className="h-[var(--header-height)] flex items-center justify-between px-[var(--space-4)] border-b border-[var(--bg-border)]">
          <Link href="/" className="flex items-center gap-[var(--space-2)]" onClick={onClose}>
            <Sparkles className="w-7 h-7 text-[var(--color-primary)]" aria-hidden="true" />
            <span className="text-[1rem] font-bold text-[var(--text-primary)]">GrowthScout AI</span>
          </Link>
          <button
            ref={closeRef}
            onClick={onClose}
            className="p-[var(--space-2)] rounded-[var(--radius-md)] text-[var(--text-muted)] hover:bg-[var(--bg-hover)] cursor-pointer"
            aria-label="Close navigation"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Nav Items */}
        <ul className="flex-1 py-[var(--space-4)] px-[var(--space-2)] overflow-y-auto" role="list">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onClose}
                  aria-current={isActive ? "page" : undefined}
                  className={`
                    flex items-center gap-[var(--space-3)]
                    px-[var(--space-3)] py-[var(--space-3)]
                    rounded-[var(--radius-md)]
                    text-[0.9375rem] font-medium
                    transition-colors duration-[var(--duration-fast)]
                    ${isActive
                      ? "bg-[var(--color-primary-muted)] text-[var(--color-primary)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                    }
                  `}
                >
                  <item.icon className="w-5 h-5 shrink-0" aria-hidden="true" />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
