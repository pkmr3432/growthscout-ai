"use client";

import { ExternalLink, Play, Globe } from "lucide-react";
import { OpportunityBadge } from "@/components/ui/opportunity-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { LeadProfile } from "@/utils/api-client";

interface ResultsTableProps {
  items: LeadProfile[];
  onActionClick: (lead: LeadProfile) => void;
  sortField: "name" | "score";
  sortOrder: "asc" | "desc";
  onSort: (field: "name" | "score") => void;
}

export function ResultsTable({ items, onActionClick, sortField, sortOrder, onSort }: ResultsTableProps) {
  const getSortIndicator = (field: "name" | "score") => {
    if (sortField !== field) return null;
    return sortOrder === "asc" ? " ▲" : " ▼";
  };

  return (
    <div className="w-full overflow-x-auto bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-[var(--radius-lg)]">
      <table className="w-full border-collapse text-left text-[0.875rem]">
        <thead>
          <tr className="bg-[var(--bg-elevated)] border-b border-[var(--bg-border)]">
            <th className="p-[var(--space-4)] font-semibold text-[var(--text-secondary)] uppercase tracking-wider text-[0.75rem]">
              <button
                onClick={() => onSort("name")}
                className="hover:text-[var(--text-primary)] cursor-pointer inline-flex items-center"
              >
                Business Info {getSortIndicator("name")}
              </button>
            </th>
            <th className="p-[var(--space-4)] font-semibold text-[var(--text-secondary)] uppercase tracking-wider text-[0.75rem]">
              <button
                onClick={() => onSort("score")}
                className="hover:text-[var(--text-primary)] cursor-pointer inline-flex items-center"
              >
                Opportunity Index {getSortIndicator("score")}
              </button>
            </th>
            <th className="p-[var(--space-4)] font-semibold text-[var(--text-secondary)] uppercase tracking-wider text-[0.75rem]">
              Identified Issues
            </th>
            <th className="p-[var(--space-4)] font-semibold text-[var(--text-secondary)] uppercase tracking-wider text-[0.75rem] text-right">
              Action
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--bg-border)]">
          {items.map((lead) => (
            <tr key={lead.id} className="hover:bg-[var(--bg-hover)] transition-colors">
              {/* Business Name, Address, Website */}
              <td className="p-[var(--space-4)] max-w-sm">
                <div className="font-semibold text-[var(--text-primary)]">{lead.name}</div>
                <div className="text-[0.8125rem] text-[var(--text-secondary)] mt-0.5">{lead.address}</div>
                <div className="mt-[var(--space-2)] flex items-center gap-[var(--space-2)]">
                  {lead.website ? (
                    <a
                      href={lead.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="
                        inline-flex items-center gap-1
                        text-[0.75rem] text-[var(--color-primary)] hover:underline
                      "
                    >
                      <Globe className="w-3.5 h-3.5" />
                      {lead.website.replace("https://www.", "")}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : (
                    <Badge variant="warning" className="text-[0.6875rem]">
                      No Website Detected
                    </Badge>
                  )}
                </div>
              </td>

              {/* Opportunity Score */}
              <td className="p-[var(--space-4)]">
                <OpportunityBadge score={lead.opportunity_score} />
              </td>

              {/* Issues Count & Details */}
              <td className="p-[var(--space-4)] max-w-md">
                <div className="flex flex-wrap gap-[var(--space-1)]">
                  {lead.issues.map((issue) => (
                    <span
                      key={issue}
                      className="
                        inline-flex items-center px-2 py-0.5
                        bg-[var(--bg-elevated)] border border-[var(--bg-border)]
                        rounded-[var(--radius-sm)] text-[0.75rem] text-[var(--text-secondary)]
                      "
                    >
                      {issue}
                    </span>
                  ))}
                </div>
              </td>

              {/* Action Trigger */}
              <td className="p-[var(--space-4)] text-right">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onActionClick(lead)}
                  className="inline-flex items-center"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  Analyze
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
