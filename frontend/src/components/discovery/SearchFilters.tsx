"use client";

import { Filter, RotateCcw } from "lucide-react";

export interface FilterState {
  scoreRange: "all" | "high" | "medium" | "low";
  hasWebsite: "all" | "yes" | "no";
  searchTerm: string;
}

interface SearchFiltersProps {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  onReset: () => void;
  totalResults: number;
  filteredResults: number;
}

export function SearchFilters({
  filters,
  onChange,
  onReset,
  totalResults,
  filteredResults,
}: SearchFiltersProps) {
  return (
    <div
      className="
        p-[var(--space-4)]
        bg-[var(--bg-surface)] border border-[var(--bg-border)]
        rounded-[var(--radius-lg)]
        flex flex-col gap-[var(--space-4)]
      "
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[var(--text-secondary)]" />
          <h3 className="text-[0.875rem] font-semibold">Filter Results</h3>
        </div>
        <button
          onClick={onReset}
          className="
            text-[0.75rem] text-[var(--text-muted)] hover:text-[var(--text-primary)]
            flex items-center gap-1 cursor-pointer
          "
        >
          <RotateCcw className="w-3 h-3" />
          Reset Filters
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-[var(--space-4)]">
        {/* Search Input */}
        <div className="flex flex-col gap-[var(--space-1)]">
          <label className="text-[0.75rem] font-semibold text-[var(--text-secondary)]">
            Search Business Name
          </label>
          <input
            type="text"
            value={filters.searchTerm}
            onChange={(e) => onChange({ ...filters, searchTerm: e.target.value })}
            placeholder="Type name..."
            className="
              h-9 px-2 text-[0.875rem]
              bg-[var(--bg-base)] border border-[var(--bg-border)]
              rounded-[var(--radius-sm)] text-[var(--text-primary)]
              focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]
            "
          />
        </div>

        {/* Opportunity Score Filter */}
        <div className="flex flex-col gap-[var(--space-1)]">
          <label className="text-[0.75rem] font-semibold text-[var(--text-secondary)]">
            Opportunity Score
          </label>
          <select
            value={filters.scoreRange}
            onChange={(e) => onChange({ ...filters, scoreRange: e.target.value as "all" | "high" | "medium" | "low" })}
            className="
              h-9 px-2 text-[0.875rem]
              bg-[var(--bg-base)] border border-[var(--bg-border)]
              rounded-[var(--radius-sm)] text-[var(--text-primary)]
              focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]
            "
          >
            <option value="all">All Scores</option>
            <option value="high">High Opportunity (80+)</option>
            <option value="medium">Medium Opportunity (60-79)</option>
            <option value="low">Low Opportunity (&lt;60)</option>
          </select>
        </div>

        {/* Has Website Filter */}
        <div className="flex flex-col gap-[var(--space-1)]">
          <label className="text-[0.75rem] font-semibold text-[var(--text-secondary)]">
            Digital Presence (Website)
          </label>
          <select
            value={filters.hasWebsite}
            onChange={(e) => onChange({ ...filters, hasWebsite: e.target.value as "all" | "yes" | "no" })}
            className="
              h-9 px-2 text-[0.875rem]
              bg-[var(--bg-base)] border border-[var(--bg-border)]
              rounded-[var(--radius-sm)] text-[var(--text-primary)]
              focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]
            "
          >
            <option value="all">All Leads</option>
            <option value="yes">Has Website</option>
            <option value="no">Lacks Website</option>
          </select>
        </div>
      </div>

      <div className="text-[0.75rem] text-[var(--text-muted)] border-t border-[var(--bg-border)] pt-[var(--space-2)]">
        Showing {filteredResults} of {totalResults} discovered businesses
      </div>
    </div>
  );
}
