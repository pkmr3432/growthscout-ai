"use client";

import { Clock, Trash2 } from "lucide-react";

export interface SearchHistoryItem {
  id: string;
  niche: string;
  location: string;
  maxLeads: number;
  timestamp: string;
}

interface SearchHistoryProps {
  items: SearchHistoryItem[];
  onSelect: (item: SearchHistoryItem) => void;
  onClearOne: (id: string) => void;
  onClearAll: () => void;
}

export function SearchHistory({ items, onSelect, onClearOne, onClearAll }: SearchHistoryProps) {
  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-[var(--space-3)]">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.875rem] font-semibold text-[var(--text-secondary)] flex items-center gap-1.5">
          <Clock className="w-4 h-4 text-[var(--text-muted)]" />
          Recent Searches
        </h3>
        <button
          onClick={onClearAll}
          className="text-[0.75rem] text-[var(--color-error)] hover:underline cursor-pointer"
        >
          Clear All
        </button>
      </div>

      <ul className="flex flex-col gap-[var(--space-2)]" role="list">
        {items.map((item) => (
          <li
            key={item.id}
            className="
              flex items-center justify-between
              p-[var(--space-3)]
              bg-[var(--bg-surface)] border border-[var(--bg-border)]
              rounded-[var(--radius-md)]
              hover:border-[var(--text-muted)]
              transition-colors duration-[var(--duration-fast)]
            "
          >
            <button
              onClick={() => onSelect(item)}
              className="flex-1 text-left flex flex-col sm:flex-row sm:items-center gap-[var(--space-2)] cursor-pointer"
            >
              <span className="font-semibold text-[0.875rem]">
                {item.niche.charAt(0).toUpperCase() + item.niche.slice(1)}
              </span>
              <span className="text-[var(--text-secondary)] text-[0.8125rem]">
                in {item.location} (Max: {item.maxLeads})
              </span>
            </button>
            <button
              onClick={() => onClearOne(item.id)}
              className="
                p-[var(--space-1)]
                text-[var(--text-muted)] hover:text-[var(--color-error)]
                rounded-[var(--radius-sm)]
                hover:bg-[var(--bg-hover)]
                transition-colors duration-[var(--duration-fast)]
                cursor-pointer
              "
              aria-label={`Remove search for ${item.niche} in ${item.location}`}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
