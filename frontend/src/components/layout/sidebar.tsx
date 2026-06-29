"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  Search,
  FolderKanban,
  FileBarChart,
  Activity,
  Code2,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

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

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={`
        hidden lg:flex flex-col
        bg-[var(--bg-surface)] border-r border-[var(--bg-border)]
        h-screen sticky top-0
        transition-[width] duration-[var(--duration-medium)] ease-[var(--ease-default)]
        ${collapsed ? "w-[var(--sidebar-collapsed)]" : "w-[var(--sidebar-width)]"}
      `}
      aria-label="Primary navigation"
    >
      {/* Brand */}
      <div className="h-[var(--header-height)] flex items-center px-[var(--space-4)] border-b border-[var(--bg-border)]">
        <Link href="/" className="flex items-center gap-[var(--space-2)] overflow-hidden">
          <Sparkles className="w-7 h-7 text-[var(--color-primary)] shrink-0" aria-hidden="true" />
          {!collapsed && (
            <span className="text-[1rem] font-bold text-[var(--text-primary)] whitespace-nowrap">
              GrowthScout AI
            </span>
          )}
        </Link>
      </div>

      {/* Nav Items */}
      <nav className="flex-1 py-[var(--space-4)] px-[var(--space-2)] overflow-y-auto">
        <ul className="flex flex-col gap-[var(--space-1)]" role="list">
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={`
                    flex items-center gap-[var(--space-3)]
                    px-[var(--space-3)] py-[var(--space-2)]
                    rounded-[var(--radius-md)]
                    text-[0.875rem] font-medium
                    transition-colors duration-[var(--duration-fast)]
                    ${isActive
                      ? "bg-[var(--color-primary-muted)] text-[var(--color-primary)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                    }
                    ${collapsed ? "justify-center" : ""}
                  `}
                  title={collapsed ? item.label : undefined}
                >
                  <item.icon className="w-5 h-5 shrink-0" aria-hidden="true" />
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Collapse Toggle */}
      <div className="p-[var(--space-2)] border-t border-[var(--bg-border)]">
        <button
          onClick={onToggle}
          className="
            w-full flex items-center justify-center
            p-[var(--space-2)]
            rounded-[var(--radius-md)]
            text-[var(--text-muted)]
            hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
            transition-colors duration-[var(--duration-fast)]
            cursor-pointer
          "
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
        </button>
      </div>
    </aside>
  );
}
