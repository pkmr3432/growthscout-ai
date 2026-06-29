"use client";

import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "@/components/providers/theme-provider";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const cycle = () => {
    const order: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
    const idx = order.indexOf(theme as "light" | "dark" | "system");
    setTheme(order[(idx + 1) % order.length]);
  };

  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  const label = theme === "system" ? "System theme" : `${theme.charAt(0).toUpperCase() + theme.slice(1)} mode`;

  return (
    <button
      onClick={cycle}
      className="
        p-[var(--space-2)]
        rounded-[var(--radius-md)]
        text-[var(--text-secondary)]
        hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
        transition-colors duration-[var(--duration-fast)]
        cursor-pointer
      "
      aria-label={`Theme: ${label}. Click to change.`}
      title={label}
    >
      <Icon className="w-5 h-5" aria-hidden="true" />
    </button>
  );
}
