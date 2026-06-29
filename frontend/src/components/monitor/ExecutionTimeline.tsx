"use client";

import { useState } from "react";
import { Play, CheckCircle2, AlertTriangle, AlertCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import type { SSEEventEnvelope } from "@/utils/api-client";

interface ExecutionTimelineProps {
  events: SSEEventEnvelope[];
}

export function ExecutionTimeline({ events }: ExecutionTimelineProps) {
  const [expandedItems, setExpandedItems] = useState<Record<number, boolean>>({});

  const toggleExpand = (id: number) => {
    setExpandedItems((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <RefreshCw className="w-5 h-5 text-[var(--color-primary)] animate-spin" />;
      case "completed":
        return <CheckCircle2 className="w-5 h-5 text-[var(--color-success)]" />;
      case "warning":
        return <AlertTriangle className="w-5 h-5 text-[var(--color-warning)]" />;
      case "failed":
        return <AlertCircle className="w-5 h-5 text-[var(--color-error)]" />;
      default:
        return <Play className="w-5 h-5 text-[var(--text-muted)]" />;
    }
  };

  const timelineItems = events.map((ev) => {
    let status: "pending" | "running" | "completed" | "warning" | "failed" = "completed";
    const name = ev.event_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    let details = "";

    if (ev.event_type === "execution_started") {
      status = "running";
      details = `Started search run for niche "${ev.data.niche}" in location "${ev.data.location}".`;
    } else if (ev.event_type === "step_completed") {
      details = `Step transitioned from state ${ev.data.previous_state} to ${ev.data.new_state}. Revision cycles: ${ev.data.revision_count}.`;
    } else if (ev.event_type === "gate_reached") {
      status = "warning";
      details = `Human gate review reached. Awaiting reviewer approval to advance.`;
    } else if (ev.event_type === "execution_completed") {
      status = "completed";
      details = `Workflow run successfully finished. Ready for report generation.`;
    } else if (ev.event_type === "execution_failed") {
      status = "failed";
      details = `Critical exception encountered: ${ev.data.reason}`;
    } else if (ev.event_type === "execution_cancelled") {
      status = "warning";
      details = "Active run was cooperatively cancelled by user.";
    }

    return {
      id: ev.event_id,
      name,
      status,
      timestamp: new Date(ev.timestamp).toLocaleTimeString(),
      details,
      data: ev.data,
    };
  });

  if (timelineItems.length === 0) {
    return (
      <div className="py-[var(--space-6)] text-center text-[var(--text-muted)] text-[0.875rem]">
        No execution timeline events recorded yet. Start analysis to monitor steps.
      </div>
    );
  }

  return (
    <div className="relative border-l border-[var(--bg-border)] ml-3 pl-6 flex flex-col gap-[var(--space-6)]">
      {timelineItems.map((item) => {
        const isExpanded = !!expandedItems[item.id];
        return (
          <div key={item.id} className="relative">
            {/* Timeline dot */}
            <span
              className="
                absolute -left-[35px] top-0.5
                flex items-center justify-center
                w-7 h-7 rounded-full bg-[var(--bg-surface)] border border-[var(--bg-border)]
              "
              aria-hidden="true"
            >
              {getStatusIcon(item.status)}
            </span>

            {/* Content card */}
            <div
              className="
                p-[var(--space-3)]
                bg-[var(--bg-surface)] border border-[var(--bg-border)]
                rounded-[var(--radius-md)]
                hover:border-[var(--text-muted)]
                transition-colors duration-[var(--duration-fast)]
              "
            >
              <div className="flex items-center justify-between gap-[var(--space-2)]">
                <div>
                  <h4 className="font-semibold text-[0.875rem] text-[var(--text-primary)]">
                    {item.name}
                  </h4>
                  <span className="text-[0.75rem] text-[var(--text-muted)] font-mono">
                    {item.timestamp}
                  </span>
                </div>
                {item.data && Object.keys(item.data).length > 0 && (
                  <button
                    onClick={() => toggleExpand(item.id)}
                    className="
                      p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]
                      rounded-[var(--radius-sm)] cursor-pointer
                    "
                    aria-expanded={isExpanded}
                    aria-label="Toggle details view"
                  >
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                )}
              </div>

              {item.details && (
                <p className="text-[0.8125rem] text-[var(--text-secondary)] mt-[var(--space-2)]">
                  {item.details}
                </p>
              )}

              {isExpanded && item.data && (
                <pre
                  className="
                    mt-[var(--space-3)] p-[var(--space-2)]
                    bg-[var(--bg-base)] border border-[var(--bg-border)]
                    rounded font-mono text-[0.75rem] text-[var(--text-muted)]
                    overflow-x-auto max-h-[150px]
                  "
                >
                  {JSON.stringify(item.data, null, 2)}
                </pre>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
