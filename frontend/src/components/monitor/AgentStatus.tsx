"use client";

import { Sparkles, Search, Code2, Heart, Award } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface AgentItem {
  id: string;
  name: string;
  role: string;
  icon: LucideIcon;
  states: string[];
}

const agents: AgentItem[] = [
  {
    id: "orchestrator",
    name: "Orchestrator Agent",
    role: "Coordinates state machine, transitions, and budget policies",
    icon: Award,
    states: ["IDLE", "RUNNING", "AWAITING_APPROVAL", "REPORT_GENERATION", "COMPLETED"],
  },
  {
    id: "discovery",
    name: "Business Discovery Agent",
    role: "Extracts local targets via place queries and API crawls",
    icon: Search,
    states: ["RUNNING"], // active during lead discovery/partitioning
  },
  {
    id: "auditor",
    name: "Technical Presence Agent",
    role: "Audits pages, analyzes meta tags, speeds, and booking components",
    icon: Code2,
    states: ["RUNNING"], // active during crawlers runs
  },
  {
    id: "opportunity",
    name: "Opportunity Agent",
    role: "Scores gaps, calculates competitive positions, maps consequences",
    icon: Sparkles,
    states: ["RUNNING"],
  },
  {
    id: "report_writer",
    name: "Growth Intelligence Agent",
    role: "Drafts markdown reports, proposals, and consultative email copies",
    icon: Heart,
    states: ["REPORT_GENERATION"],
  },
];

interface AgentStatusProps {
  currentState: string;
  isRunning: boolean;
}

export function AgentStatus({ currentState, isRunning }: AgentStatusProps) {
  const normalizedState = currentState.toUpperCase();

  return (
    <div className="flex flex-col gap-[var(--space-3)]">
      <h3 className="text-[0.875rem] font-semibold text-[var(--text-secondary)]">Active Agents</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-3)]">
        {agents.map((agent) => {
          // Determine if this agent is active in the current state
          const isAgentActive = isRunning && agent.states.includes(normalizedState) && (
            agent.id === "orchestrator" || 
            (agent.id === "discovery" && normalizedState === "RUNNING") ||
            (agent.id === "auditor" && normalizedState === "RUNNING") ||
            (agent.id === "opportunity" && normalizedState === "RUNNING") ||
            (agent.id === "report_writer" && normalizedState === "REPORT_GENERATION")
          );

          return (
            <div
              key={agent.id}
              className={`
                p-[var(--space-3)]
                bg-[var(--bg-surface)] border rounded-[var(--radius-md)]
                transition-all duration-[var(--duration-medium)]
                ${isAgentActive
                  ? "border-[var(--color-primary)] shadow-[var(--shadow-low)] ring-1 ring-[var(--color-primary)]"
                  : "border-[var(--bg-border)] opacity-70"
                }
              `}
            >
              <div className="flex items-start gap-[var(--space-3)]">
                <div
                  className={`
                    p-[var(--space-2)] rounded-[var(--radius-sm)]
                    ${isAgentActive
                      ? "bg-[var(--color-primary-muted)] text-[var(--color-primary)]"
                      : "bg-[var(--bg-base)] text-[var(--text-muted)]"
                    }
                  `}
                >
                  <agent.icon
                    className={`w-5 h-5 ${isAgentActive && agent.id !== "orchestrator" ? "animate-pulse" : ""}`}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-semibold text-[0.875rem] text-[var(--text-primary)] block truncate">
                      {agent.name}
                    </span>
                    {isAgentActive && (
                      <span className="flex h-2 w-2 relative shrink-0">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--color-primary)] opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--color-primary)]"></span>
                      </span>
                    )}
                  </div>
                  <p className="text-[0.75rem] text-[var(--text-secondary)] mt-0.5 leading-normal">
                    {agent.role}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
