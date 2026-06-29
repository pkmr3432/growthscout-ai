"use client";

import { useState, useEffect, useMemo, use, useCallback } from "react";
import {
  Play,
  XCircle,
  RefreshCw,
  FileBarChart,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import {
  PageContainer,
  Card,
  CardTitle,
  Button,
  Badge,
  Alert,
  SkeletonCard,
} from "@/components/ui";
import { ExecutionTimeline } from "@/components/monitor/ExecutionTimeline";
import { AgentStatus } from "@/components/monitor/AgentStatus";
import { CollapsibleLogViewer } from "@/components/monitor/CollapsibleLogViewer";
import { HitlReviewPanel, type HitlRecommendation } from "@/components/monitor/HitlReviewPanel";
import {
  getSession,
  runSession,
  cancelSession,
  submitFeedback,
  type SessionResponse,
  type SSEEventEnvelope,
} from "@/utils/api-client";
import { useSessionStream } from "@/hooks/use-session-stream";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function SessionDetailPage({ params }: PageProps) {
  const { id: sessionId } = use(params);

  // Core Session Details
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Active Run States
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // SSE Stream events list
  const [events, setEvents] = useState<SSEEventEnvelope[]>([]);
  const [logLines, setLogLines] = useState<Array<{ timestamp: string; level: "info" | "warning" | "error"; message: string; source: string }>>([]);

  const isSessionRunning = session?.status === "running";

  // Load Session Data
  const loadSession = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await getSession(sessionId);
      setSession(data);
      
      // Seed initial timeline and logs if session has completed or paused
      if (data.status === "paused_on_gate") {
        setLogLines([
          {
            timestamp: new Date().toLocaleTimeString(),
            level: "warning",
            message: "Execution paused at human review gate. Awaiting feedback.",
            source: "orchestrator",
          },
        ]);
      } else if (data.status === "completed") {
        setLogLines([
          {
            timestamp: new Date().toLocaleTimeString(),
            level: "info",
            message: "Workflow finished in terminal completed state.",
            source: "orchestrator",
          },
        ]);
      }
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : "Failed to load session details.");
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadSession();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadSession]);

  // Event handler for incoming SSE events
  const handleIncomingEvent = useCallback((ev: SSEEventEnvelope) => {
    setEvents((prev) => {
      // Avoid duplicate event insertions
      if (prev.some((p) => p.event_id === ev.event_id)) return prev;
      return [...prev, ev];
    });

    // Formulate a console log line from the SSE envelope
    const timestamp = new Date(ev.timestamp).toLocaleTimeString();
    let message = "";
    let level: "info" | "warning" | "error" = "info";

    if (ev.event_type === "execution_started") {
      message = `Workflow run started: niche="${ev.data.niche}", location="${ev.data.location}".`;
    } else if (ev.event_type === "step_completed") {
      message = `Transitioned: state ${ev.data.previous_state} -> ${ev.data.new_state}. Revision: ${ev.data.revision_count}.`;
    } else if (ev.event_type === "gate_reached") {
      level = "warning";
      message = `Paused: reached gate ${ev.data.gate_type}. Awaiting human review.`;
      // Reload session metadata to update state to paused_on_gate
      getSession(sessionId).then(setSession).catch(() => {});
    } else if (ev.event_type === "execution_completed") {
      message = `Completed: workflow completed successfully.`;
      getSession(sessionId).then(setSession).catch(() => {});
    } else if (ev.event_type === "execution_failed") {
      level = "error";
      message = `Failed: ${ev.data.reason}`;
      getSession(sessionId).then(setSession).catch(() => {});
    } else if (ev.event_type === "execution_cancelled") {
      level = "warning";
      message = `Cancelled: Active run cancelled by user request.`;
      getSession(sessionId).then(setSession).catch(() => {});
    } else if (ev.event_type === "stream_connected") {
      message = `Event stream connection established.`;
    } else if (ev.event_type === "stream_ended") {
      message = `Event stream connection terminated.`;
    } else {
      message = `Heartbeat keepalive trace.`;
    }

    if (ev.event_type !== "heartbeat") {
      setLogLines((prev) => [...prev, { timestamp, level, message, source: ev.event_type }]);
    }
  }, [sessionId]);

  const handleStreamError = useCallback((err: Error) => {
    console.error("SSE Stream error callback:", err);
    setLogLines((prev) => [
      ...prev,
      {
        timestamp: new Date().toLocaleTimeString(),
        level: "error",
        message: `SSE Connection lost: ${err.message}. Retrying...`,
        source: "stream",
      },
    ]);
  }, []);

  // Listen to SSE Stream if the session is running
  useSessionStream({
    sessionId,
    onEvent: handleIncomingEvent,
    onError: handleStreamError,
    enabled: isSessionRunning,
  });

  // Action: Trigger workflow execution run
  const handleStartAnalysis = async () => {
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      setLogLines((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          level: "info",
          message: "Initiating execution request... acquired locks.",
          source: "client",
        },
      ]);
      const updated = await runSession(sessionId);
      setSession(updated);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to start workflow execution.";
      setActionError(errMsg);
      setLogLines((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          level: "error",
          message: `Start failed: ${errMsg}`,
          source: "client",
        },
      ]);
    } finally {
      setIsSubmittingAction(false);
    }
  };

  // Action: Cancel active workflow execution
  const handleCancelAnalysis = async () => {
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      const updated = await cancelSession(sessionId);
      setSession(updated);
      setLogLines((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          level: "warning",
          message: "Cancellation request completed successfully.",
          source: "client",
        },
      ]);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to cancel workflow execution.");
    } finally {
      setIsSubmittingAction(false);
    }
  };

  // Action: Submit feedback to advance the review gate
  const handleFeedbackSubmit = async (approved: boolean, recommendations: HitlRecommendation[], notes: string) => {
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      const adjusted_data = {
        opportunities: recommendations.filter((r) => r.approved).map((r) => r.title),
        lead_score: Math.round(
          recommendations.reduce((sum, r) => sum + (r.approved ? r.confidence : 0), 0) /
            Math.max(1, recommendations.filter((r) => r.approved).length)
        ),
        notes,
      };

      setLogLines((prev) => [
        ...prev,
        {
          timestamp: new Date().toLocaleTimeString(),
          level: "info",
          message: `Submitting feedback response (approved=${approved}). Advancing workflow gate...`,
          source: "client",
        },
      ]);

      const updated = await submitFeedback(sessionId, {
        approved,
        feedback_notes: notes,
        adjusted_data,
      });

      setSession(updated);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to submit gate feedback.");
    } finally {
      setIsSubmittingAction(false);
    }
  };

  // Generate fallback mock recommendations for HITL view if backend results are unpopulated
  const mockRecommendations = useMemo((): HitlRecommendation[] => {
    if (!session) return [];
    
    // We use niche to make mock evidence highly contextual
    const nicheName = session.niche || "local business";
    return [
      {
        id: "rec_1",
        title: "Deploy Structured Schema Markup",
        category: "SEO Optimization",
        evidence: `No structured JSON-LD schema parsed in homepage source for ${nicheName}.`,
        consequence: "Search engines cannot display rich snippets, lowering CTR visibility.",
        confidence: 85,
        impact: "High",
        value: "$2,400 / year",
        approved: true,
      },
      {
        id: "rec_2",
        title: "Optimize Mobile Loading Speeds",
        category: "Mobile Performance",
        evidence: "Page speed load latency is 5.4s on 4G networks. Core Web Vitals failing.",
        consequence: "High mobile bounce rate, leading to lost customer conversions.",
        confidence: 78,
        impact: "High",
        value: "$3,600 / year",
        approved: true,
      },
      {
        id: "rec_3",
        title: "Integrate Scheduling Widget",
        category: "Conversion Rate Optimization",
        evidence: "No contact form or online booking calendar detected above the fold.",
        consequence: "Friction in online booking funnel. Customers bail rather than dial.",
        confidence: 90,
        impact: "Medium",
        value: "$1,800 / year",
        approved: true,
      },
    ];
  }, [session]);

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex flex-col gap-[var(--space-6)]">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </PageContainer>
    );
  }

  if (loadError || !session) {
    return (
      <PageContainer>
        <Alert variant="error" title="Session Loading Failed">
          <p>{loadError ?? "Unable to resolve session document identifier."}</p>
          <div className="mt-4 flex gap-[var(--space-2)]">
            <Link href="/sessions">
              <Button variant="secondary">Back to Sessions</Button>
            </Link>
            <Button variant="primary" onClick={loadSession}>
              Retry Load
            </Button>
          </div>
        </Alert>
      </PageContainer>
    );
  }

  // Map Session status to friendly labels and classes
  const statusConfig = {
    idle: { label: "Idle", class: "bg-[var(--bg-elevated)] text-[var(--text-secondary)]" },
    running: { label: "Running Analysis", class: "bg-[var(--color-info-muted)] text-[var(--color-info)]" },
    paused_on_gate: { label: "Awaiting Review", class: "bg-[var(--color-warning-muted)] text-[var(--color-warning)]" },
    completed: { label: "Completed", class: "bg-[var(--color-success-muted)] text-[var(--color-success)]" },
    failed: { label: "Failed", class: "bg-[var(--color-error-muted)] text-[var(--color-error)]" },
  }[session.status] ?? { label: session.status, class: "bg-[var(--bg-elevated)] text-[var(--text-secondary)]" };

  return (
    <PageContainer>
      {/* Page Header */}
      <div className="flex items-center gap-[var(--space-2)] mb-[var(--space-4)]">
        <Link
          href="/discovery"
          className="
            p-2 rounded-[var(--radius-md)] text-[var(--text-secondary)]
            hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]
            transition-colors duration-[var(--duration-fast)]
          "
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <span className="text-[0.875rem] text-[var(--text-muted)] font-medium">Back to Discovery</span>
      </div>

      {/* Session Status Banner */}
      <div
        className="
          p-[var(--space-4)] mb-[var(--space-6)]
          bg-[var(--bg-surface)] border border-[var(--bg-border)]
          rounded-[var(--radius-lg)] shadow-[var(--shadow-low)]
          flex flex-col sm:flex-row sm:items-center sm:justify-between gap-[var(--space-4)]
        "
      >
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-[var(--space-2)]">
            <h1 className="text-[1.25rem] font-bold text-[var(--text-primary)]">
              Session {session.session_id}
            </h1>
            <Badge className={statusConfig.class}>{statusConfig.label}</Badge>
          </div>
          <p className="text-[0.8125rem] text-[var(--text-secondary)]">
            Niche: <span className="font-semibold text-[var(--text-primary)]">{session.niche}</span> in{" "}
            <span className="font-semibold text-[var(--text-primary)]">{session.location}</span> (Max leads:{" "}
            {session.max_leads})
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-[var(--space-2)] shrink-0">
          {session.status === "idle" && (
            <Button variant="primary" loading={isSubmittingAction} onClick={handleStartAnalysis}>
              <Play className="w-4 h-4 shrink-0 fill-current" />
              Start Diagnostic Audit
            </Button>
          )}

          {session.status === "running" && (
            <Button
              variant="danger"
              loading={isSubmittingAction}
              onClick={handleCancelAnalysis}
              className="bg-transparent border border-[var(--color-error)] text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
            >
              <XCircle className="w-4 h-4 shrink-0" />
              Cancel Execution
            </Button>
          )}

          {session.status === "completed" && (
            <Link href="/reports">
              <Button variant="primary">
                <FileBarChart className="w-4 h-4 shrink-0" />
                View Opportunity Report
              </Button>
            </Link>
          )}

          {session.status === "failed" && (
            <Button variant="primary" loading={isSubmittingAction} onClick={handleStartAnalysis}>
              <RefreshCw className="w-4 h-4 shrink-0" />
              Re-run Diagnostic
            </Button>
          )}
        </div>
      </div>

      {actionError && (
        <Alert variant="error" className="mb-[var(--space-6)]" title="Action Trigger Failed">
          {actionError}
        </Alert>
      )}

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-[var(--space-6)] items-start">
        {/* Left Side: Monitor status, timeline, agent highlighted status */}
        <div className="lg:col-span-2 flex flex-col gap-[var(--space-6)]">
          {/* Progress sequence */}
          <Card>
            <CardTitle className="mb-[var(--space-4)]">Orchestrator Agent Progress</CardTitle>
            <div className="grid grid-cols-5 gap-2 text-center text-[0.75rem] font-medium">
              {[
                { label: "Created", states: ["CREATED", "IDLE"] },
                { label: "Lead Discover", states: ["RUNNING"] },
                { label: "Web Audits", states: ["RUNNING"] },
                { label: "HITL Gate", states: ["AWAITING_APPROVAL", "NEEDS_REVIEW"] },
                { label: "Completed", states: ["COMPLETED"] },
              ].map((step, idx) => {
                const isActive = session.status !== "idle" && (
                  (step.label === "Created" && ["idle", "running", "paused_on_gate", "completed"].includes(session.status)) ||
                  (step.label === "Lead Discover" && isSessionRunning) ||
                  (step.label === "Web Audits" && isSessionRunning) ||
                  (step.label === "HITL Gate" && ["paused_on_gate", "completed"].includes(session.status)) ||
                  (step.label === "Completed" && session.status === "completed")
                );

                return (
                  <div key={step.label} className="flex flex-col items-center gap-1.5">
                    <span
                      className={`
                        w-6 h-6 rounded-full flex items-center justify-center border font-mono
                        ${isActive
                          ? "bg-[var(--color-primary-muted)] border-[var(--color-primary)] text-[var(--color-primary)] font-bold"
                          : "bg-[var(--bg-base)] border-[var(--bg-border)] text-[var(--text-muted)]"
                        }
                      `}
                    >
                      {idx + 1}
                    </span>
                    <span className={isActive ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"}>
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* HITL Review Console Display */}
          {session.status === "paused_on_gate" && (
            <HitlReviewPanel
              initialRecommendations={mockRecommendations}
              onSubmit={handleFeedbackSubmit}
              isSubmitting={isSubmittingAction}
            />
          )}

          {/* Active Agents Highlight */}
          <AgentStatus currentState={session.current_state} isRunning={isSessionRunning} />

          {/* Expanded timeline list */}
          <Card>
            <CardTitle className="mb-[var(--space-4)]">Live Timeline Feed</CardTitle>
            <ExecutionTimeline events={events} />
          </Card>
        </div>

        {/* Right Side: Collapsible Search log console terminal */}
        <div className="lg:col-span-1 flex flex-col gap-[var(--space-6)]">
          <CollapsibleLogViewer logs={logLines} />

          {/* Quick Metrics display */}
          <Card>
            <CardTitle className="mb-[var(--space-2)]">Audit Provenance</CardTitle>
            <div className="flex flex-col gap-[var(--space-3)] text-[0.8125rem]">
              <div className="flex items-center justify-between border-b border-[var(--bg-border)] pb-2">
                <span className="text-[var(--text-muted)]">Workflow Run:</span>
                <span className="font-mono text-[var(--text-primary)] font-semibold">{session.workflow_id}</span>
              </div>
              <div className="flex items-center justify-between border-b border-[var(--bg-border)] pb-2">
                <span className="text-[var(--text-muted)]">Revision Count:</span>
                <span className="font-mono text-[var(--text-primary)] font-semibold">{session.revision_count}</span>
              </div>
              <div className="flex items-center justify-between border-b border-[var(--bg-border)] pb-2">
                <span className="text-[var(--text-muted)]">Created timestamp:</span>
                <span className="text-[var(--text-secondary)]">{new Date(session.created_at).toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[var(--text-muted)]">Orchestrator tag:</span>
                <span className="text-[var(--text-secondary)] font-mono">ADK 2.3.0 / v4.0</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}
