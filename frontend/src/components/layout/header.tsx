"use client";

import { Menu, Search, User } from "lucide-react";
import { Breadcrumbs } from "./breadcrumbs";
import { ThemeToggle } from "./theme-toggle";

interface HeaderProps {
  onMobileMenuOpen: () => void;
}

export function Header({ onMobileMenuOpen }: HeaderProps) {
  return (
    <header
      className="
        h-[var(--header-height)]
        border-b border-[var(--bg-border)]
        bg-[var(--bg-surface)]
        sticky top-0 z-[100]
        flex items-center justify-between
        px-[var(--space-4)]
        gap-[var(--space-4)]
      "
    >
      {/* Left: Mobile burger + Breadcrumbs */}
      <div className="flex items-center gap-[var(--space-3)]">
        <button
          onClick={onMobileMenuOpen}
          className="
            lg:hidden
            p-[var(--space-2)]
            rounded-[var(--radius-md)]
            text-[var(--text-secondary)]
            hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
            transition-colors duration-[var(--duration-fast)]
            cursor-pointer
          "
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" aria-hidden="true" />
        </button>
        <Breadcrumbs />
      </div>

      {/* Right: Global search + Theme + User */}
      <div className="flex items-center gap-[var(--space-1)]">
        {/* Global Search Placeholder */}
        <button
          className="
            hidden sm:flex items-center gap-[var(--space-2)]
            px-[var(--space-3)] py-[var(--space-2)]
            bg-[var(--bg-base)] border border-[var(--bg-border)]
            rounded-[var(--radius-md)]
            text-[0.8125rem] text-[var(--text-muted)]
            hover:border-[var(--text-muted)]
            transition-colors duration-[var(--duration-fast)]
            cursor-pointer
            min-w-[200px]
          "
          aria-label="Search"
        >
          <Search className="w-4 h-4" aria-hidden="true" />
          <span>Search...</span>
          <kbd className="ml-auto text-[0.6875rem] text-[var(--text-muted)] bg-[var(--bg-surface)] px-1.5 py-0.5 rounded-[var(--radius-sm)] border border-[var(--bg-border)]">
            ⌘/
          </kbd>
        </button>

        <ThemeToggle />

        {/* User Menu Placeholder */}
        <button
          className="
            p-[var(--space-2)]
            rounded-[var(--radius-md)]
            text-[var(--text-secondary)]
            hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
            transition-colors duration-[var(--duration-fast)]
            cursor-pointer
          "
          aria-label="User menu"
        >
          <User className="w-5 h-5" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
