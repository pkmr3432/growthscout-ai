"use client";

import { ExternalLink, Play, Globe } from "lucide-react";
import { OpportunityBadge } from "@/components/ui/opportunity-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { LeadProfile } from "@/utils/api-client";

interface BusinessCardProps {
  lead: LeadProfile;
  onActionClick: () => void;
}

export function BusinessCard({ lead, onActionClick }: BusinessCardProps) {
  return (
    <Card className="flex flex-col gap-[var(--space-4)] hover:border-[var(--text-muted)] transition-colors">
      {/* Header Info */}
      <div className="flex items-start justify-between gap-[var(--space-2)]">
        <div>
          <h4 className="font-bold text-[1rem] text-[var(--text-primary)]">{lead.name}</h4>
          <p className="text-[0.75rem] text-[var(--text-secondary)] mt-0.5">{lead.address}</p>
        </div>
        <OpportunityBadge score={lead.opportunity_score} className="shrink-0" />
      </div>

      {/* Website & Metadata */}
      <div>
        {lead.website ? (
          <a
            href={lead.website}
            target="_blank"
            rel="noopener noreferrer"
            className="
              inline-flex items-center gap-1.5
              text-[0.8125rem] text-[var(--color-primary)] hover:underline
            "
          >
            <Globe className="w-4 h-4" />
            {lead.website.replace("https://www.", "")}
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        ) : (
          <Badge variant="warning">No Website Detected</Badge>
        )}
      </div>

      {/* Issues list */}
      <div className="flex flex-wrap gap-[var(--space-1)]">
        {lead.issues.map((issue) => (
          <span
            key={issue}
            className="
              px-2 py-0.5
              bg-[var(--bg-elevated)] border border-[var(--bg-border)]
              rounded-[var(--radius-sm)] text-[0.75rem] text-[var(--text-secondary)]
            "
          >
            {issue}
          </span>
        ))}
      </div>

      {/* Action footer */}
      <div className="border-t border-[var(--bg-border)] pt-[var(--space-3)] mt-auto flex justify-end">
        <Button variant="secondary" size="sm" onClick={onActionClick} className="w-full sm:w-auto">
          <Play className="w-3.5 h-3.5 fill-current" />
          Analyze Lead
        </Button>
      </div>
    </Card>
  );
}
