"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderKanban, Play, Trash2, Calendar } from "lucide-react";
import {
  PageContainer,
  SectionHeader,
  EmptyState,
  Card,
  Button,
  Badge,
} from "@/components/ui";
import { getSession } from "@/utils/api-client";

interface SessionListItem {
  id: string;
  niche: string;
  location: string;
  maxLeads: number;
  timestamp: string;
  status?: string;
}

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loadingStates, setLoadingStates] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const saved = localStorage.getItem("gs-search-history");
    if (saved) {
      try {
        const parsed: SessionListItem[] = JSON.parse(saved);
        const timer = setTimeout(() => {
          setSessions(parsed);

          // Fetch live status for each session in background
          parsed.forEach(async (item) => {
            setLoadingStates((prev) => ({ ...prev, [item.id]: true }));
            try {
              const data = await getSession(item.id);
              setSessions((current) =>
                current.map((s) => (s.id === item.id ? { ...s, status: data.status } : s))
              );
            } catch {
              // fallback to idle if getSession fails
              setSessions((current) =>
                current.map((s) => (s.id === item.id ? { ...s, status: "idle" } : s))
              );
            } finally {
              setLoadingStates((prev) => ({ ...prev, [item.id]: false }));
            }
          });
        }, 0);
        return () => clearTimeout(timer);
      } catch (e) {
        console.error("Failed to parse search history:", e);
      }
    }
  }, []);

  const handleDelete = (id: string) => {
    const updated = sessions.filter((s) => s.id !== id);
    setSessions(updated);
    localStorage.setItem("gs-search-history", JSON.stringify(updated));
  };

  const getStatusBadge = (status?: string, loading?: boolean) => {
    if (loading) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[0.75rem] font-medium bg-[var(--bg-elevated)] text-[var(--text-muted)]">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--text-muted)] animate-pulse"></span>
          Checking...
        </span>
      );
    }

    const config = {
      idle: { label: "Idle", class: "bg-[var(--bg-elevated)] text-[var(--text-secondary)]" },
      running: { label: "Running", class: "bg-[var(--color-info-muted)] text-[var(--color-info)]" },
      paused_on_gate: { label: "Awaiting Review", class: "bg-[var(--color-warning-muted)] text-[var(--color-warning)]" },
      completed: { label: "Completed", class: "bg-[var(--color-success-muted)] text-[var(--color-success)]" },
      failed: { label: "Failed", class: "bg-[var(--color-error-muted)] text-[var(--color-error)]" },
    }[status ?? "idle"] ?? { label: status, class: "bg-[var(--bg-elevated)] text-[var(--text-secondary)]" };

    return <Badge className={config.class}>{config.label}</Badge>;
  };

  return (
    <PageContainer>
      <SectionHeader
        title="Diagnostic Audit Sessions"
        description="Monitor, adjust, and review your multi-agent lead analysis histories"
      />

      {sessions.length === 0 ? (
        <EmptyState
          icon={<FolderKanban className="w-12 h-12" strokeWidth={1.5} />}
          title="No Diagnostic Sessions Found"
          description="You haven't run any business searches or triggered any state audits yet. Navigate to the Discovery hub to search for prospects and begin diagnostics."
          action={{
            label: "Find Local Businesses",
            onClick: () => router.push("/discovery"),
          }}
        />
      ) : (
        <div className="flex flex-col gap-[var(--space-4)] max-w-5xl">
          {sessions.map((session) => (
            <Card
              key={session.id}
              className="
                flex flex-col sm:flex-row sm:items-center sm:justify-between gap-[var(--space-4)]
                hover:border-[var(--text-muted)] transition-all duration-[var(--duration-fast)]
              "
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-[var(--space-2)] flex-wrap">
                  <h3 className="font-bold text-[1rem] text-[var(--text-primary)] font-mono">
                    Session {session.id}
                  </h3>
                  {getStatusBadge(session.status, loadingStates[session.id])}
                </div>
                <p className="text-[0.875rem] text-[var(--text-secondary)]">
                  Niche: <span className="font-semibold text-[var(--text-primary)]">{session.niche}</span> in{" "}
                  <span className="font-semibold text-[var(--text-primary)]">{session.location}</span> (Max:{" "}
                  {session.maxLeads})
                </p>
                <div className="flex items-center gap-1 text-[0.75rem] text-[var(--text-muted)] mt-1">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Created {new Date(session.timestamp).toLocaleString()}</span>
                </div>
              </div>

              <div className="flex items-center gap-[var(--space-2)] shrink-0 self-end sm:self-center">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(session.id)}
                  className="text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
                  aria-label={`Delete Session ${session.id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
                <Link href={`/sessions/${session.id}`}>
                  <Button variant="primary" size="sm">
                    <Play className="w-3.5 h-3.5 shrink-0 fill-current" />
                    Open Monitor
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
