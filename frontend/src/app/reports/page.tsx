"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Search,
  Copy,
  FolderArchive,
  Trash2,
  SlidersHorizontal,
  FolderOpen,
} from "lucide-react";
import {
  PageContainer,
  SectionHeader,
  EmptyState,
  Card,
  Button,
  Badge,
  Input,
} from "@/components/ui";
import { getSession } from "@/utils/api-client";
import {
  getReportHistory,
  saveReportHistory,
  getReportOverrides,
  saveReportOverrides,
  type ReportHistoryItem,
} from "@/utils/report-storage";

interface SessionSearchHistoryItem {
  id: string; // session_id
  niche: string;
  location: string;
  maxLeads: number;
  timestamp: string;
}

export default function ReportsPage() {
  const router = useRouter();
  const [reports, setReports] = useState<ReportHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "archived">("active");
  const [sortField, setSortField] = useState<"date" | "score">("date");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  // Load baseline completed sessions + historical overrides
  useEffect(() => {
    const initializeReports = async () => {
      setLoading(true);
      const history = getReportHistory();
      const savedSearch = localStorage.getItem("gs-search-history");
      const activeReports: ReportHistoryItem[] = [...history];

      if (savedSearch) {
        try {
          const sessions: SessionSearchHistoryItem[] = JSON.parse(savedSearch);
          
          // Identify completed sessions and auto-register them in reports list if not already present
          for (const sess of sessions) {
            if (activeReports.some((r) => r.sessionId === sess.id)) {
              continue;
            }

            try {
              const liveSession = await getSession(sess.id);
              if (liveSession.status === "completed" || liveSession.status === "paused_on_gate") {
                const ctx = liveSession.context_data as Record<string, Record<string, number>> | undefined;
                const score = ctx?.opportunity_results?.lead_score ?? 78;
                const newReport: ReportHistoryItem = {
                  id: liveSession.session_id,
                  sessionId: liveSession.session_id,
                  title: `${sess.niche} Growth Assessment`,
                  clientName: "Valued Prospect",
                  companyName: `${sess.niche} Local Clinic`,
                  opportunityScore: score,
                  createdAt: sess.timestamp,
                  isArchived: false,
                };
                activeReports.push(newReport);
              }
            } catch {
              // Ignore session fetch errors
            }
          }
        } catch {
          // Ignore parse errors
        }
      }

      saveReportHistory(activeReports);
      setReports(activeReports);
      setLoading(false);
    };

    initializeReports();
  }, []);

  // Filter & Sort Reports
  const filteredReports = useMemo(() => {
    return reports
      .filter((rep) => {
        // Search text matching
        const matchText =
          rep.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          rep.companyName.toLowerCase().includes(searchQuery.toLowerCase()) ||
          rep.clientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
          rep.id.toLowerCase().includes(searchQuery.toLowerCase());
        
        if (!matchText) return false;

        // Archive filters
        if (statusFilter === "active" && rep.isArchived) return false;
        if (statusFilter === "archived" && !rep.isArchived) return false;
        
        return true;
      })
      .sort((a, b) => {
        if (sortField === "date") {
          const tA = new Date(a.createdAt).getTime();
          const tB = new Date(b.createdAt).getTime();
          return sortOrder === "asc" ? tA - tB : tB - tA;
        } else {
          return sortOrder === "asc"
            ? a.opportunityScore - b.opportunityScore
            : b.opportunityScore - a.opportunityScore;
        }
      });
  }, [reports, searchQuery, statusFilter, sortField, sortOrder]);

  // Pagination bounds
  const totalPages = Math.max(1, Math.ceil(filteredReports.length / itemsPerPage));
  const paginatedReports = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredReports.slice(start, start + itemsPerPage);
  }, [filteredReports, currentPage]);

  // Report actions
  const handleDeleteReport = (id: string) => {
    if (!confirm("Are you sure you want to permanently delete this report?")) return;
    const updated = reports.filter((r) => r.id !== id);
    saveReportHistory(updated);
    setReports(updated);
    // clean overrides
    const savedOverrides = localStorage.getItem("gs-report-overrides");
    if (savedOverrides) {
      try {
        const parsed = JSON.parse(savedOverrides);
        delete parsed[id];
        localStorage.setItem("gs-report-overrides", JSON.stringify(parsed));
      } catch {
        // ignore
      }
    }
  };

  const handleArchiveReport = (id: string) => {
    const updated = reports.map((r) => (r.id === id ? { ...r, isArchived: !r.isArchived } : r));
    saveReportHistory(updated);
    setReports(updated);
  };

  const handleDuplicateReport = (source: ReportHistoryItem) => {
    const newId = `rep_${Math.random().toString(36).substr(2, 9)}`;
    const newReport: ReportHistoryItem = {
      ...source,
      id: newId,
      title: `${source.title} (Copy)`,
      createdAt: new Date().toISOString(),
      isArchived: false,
    };

    // Duplicate custom overrides if they exist
    const originalOverrides = getReportOverrides(source.id);
    if (originalOverrides) {
      saveReportOverrides(newId, {
        ...originalOverrides,
        id: newId,
        proposalTitle: `${originalOverrides.proposalTitle} (Copy)`,
      });
    }

    const updated = [newReport, ...reports];
    saveReportHistory(updated);
    setReports(updated);
  };

  const handleRenameReport = (id: string) => {
    const name = prompt("Enter a new title for this report:");
    if (!name?.trim()) return;
    const updated = reports.map((r) => (r.id === id ? { ...r, title: name } : r));
    saveReportHistory(updated);
    setReports(updated);
  };

  return (
    <PageContainer>
      <SectionHeader
        title="Client Proposals & Reports"
        description="Deliver consultative growth analysis reports and white-labeled pricing proposals."
      />

      {/* Dashboard control filters */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-[var(--space-4)] mb-[var(--space-6)] no-print">
        {/* Search */}
        <div className="relative flex-1 max-w-md">
          <Input
            type="text"
            placeholder="Search report name, client or company..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            className="pl-[var(--space-8)]"
          />
          <Search className="w-4 h-4 text-[var(--text-muted)] absolute left-3 top-3.5" />
        </div>

        {/* Filter Toolbar */}
        <div className="flex items-center gap-[var(--space-3)] flex-wrap">
          <div className="flex bg-[var(--bg-elevated)] p-0.5 rounded-[var(--radius-sm)] border border-[var(--bg-border)]">
            <button
              onClick={() => {
                setStatusFilter("active");
                setCurrentPage(1);
              }}
              className={`px-3 py-1.5 text-[0.75rem] font-semibold rounded-[var(--radius-sm)] cursor-pointer ${
                statusFilter === "active"
                  ? "bg-[var(--color-primary)] text-[var(--color-primary-foreground)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Active
            </button>
            <button
              onClick={() => {
                setStatusFilter("archived");
                setCurrentPage(1);
              }}
              className={`px-3 py-1.5 text-[0.75rem] font-semibold rounded-[var(--radius-sm)] cursor-pointer ${
                statusFilter === "archived"
                  ? "bg-[var(--color-primary)] text-[var(--color-primary-foreground)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              Archived
            </button>
          </div>

          <div className="flex items-center gap-1 bg-[var(--bg-elevated)] px-2 py-1 rounded border border-[var(--bg-border)]">
            <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--text-muted)]" />
            <select
              value={sortField}
              onChange={(e) => setSortField(e.target.value as "date" | "score")}
              className="bg-transparent text-[0.75rem] font-semibold text-[var(--text-primary)] focus:outline-none cursor-pointer"
            >
              <option value="date">Sort by Date</option>
              <option value="score">Sort by Score</option>
            </select>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as "asc" | "desc")}
              className="bg-transparent text-[0.75rem] font-semibold text-[var(--text-primary)] focus:outline-none cursor-pointer ml-1"
            >
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
          </div>
        </div>
      </div>

      {/* Reports Grid List */}
      {loading ? (
        <div className="flex items-center justify-center py-[var(--space-12)]">
          <div className="spinner w-8 h-8"></div>
        </div>
      ) : paginatedReports.length === 0 ? (
        <EmptyState
          icon={<FileText className="w-12 h-12" strokeWidth={1.5} />}
          title="No Reports Found"
          description="Your completed and custom generated diagnostic report audits will appear here. Navigate to the Discovery hub to execute sessions."
          action={{
            label: "Go to Lead Discovery",
            onClick: () => router.push("/discovery"),
          }}
        />
      ) : (
        <div className="flex flex-col gap-[var(--space-4)] max-w-5xl">
          {paginatedReports.map((rep) => (
            <Card
              key={rep.id}
              className="
                flex flex-col md:flex-row md:items-center justify-between gap-[var(--space-4)]
                hover:border-[var(--text-muted)] transition-all duration-[var(--duration-fast)]
              "
            >
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-[var(--space-2)] flex-wrap">
                  <h3 className="font-bold text-[1rem] text-[var(--text-primary)]">
                    {rep.title}
                  </h3>
                  <Badge className="bg-[var(--color-primary-muted)] text-[var(--color-primary)] font-mono text-[0.75rem]">
                    Score: {rep.opportunityScore}
                  </Badge>
                  {rep.isArchived && (
                    <Badge className="bg-[var(--bg-elevated)] text-[var(--text-muted)] text-[0.75rem]">
                      Archived
                    </Badge>
                  )}
                </div>
                <p className="text-[0.8125rem] text-[var(--text-secondary)]">
                  Client: <span className="font-semibold">{rep.clientName}</span> | Company: <span className="font-semibold">{rep.companyName}</span>
                </p>
                <div className="flex items-center gap-1.5 text-[0.75rem] text-[var(--text-muted)]">
                  <span>ID: <code className="font-mono">{rep.id}</code></span>
                  <span>•</span>
                  <span>Created: {new Date(rep.createdAt).toLocaleDateString()}</span>
                </div>
              </div>

              <div className="flex items-center gap-[var(--space-2)] shrink-0 flex-wrap">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRenameReport(rep.id)}
                  title="Rename"
                  className="h-8 px-2"
                >
                  Rename
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDuplicateReport(rep)}
                  title="Duplicate"
                  className="h-8 px-2"
                >
                  <Copy className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleArchiveReport(rep.id)}
                  title={rep.isArchived ? "Restore" : "Archive"}
                  className="h-8 px-2"
                >
                  <FolderArchive className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDeleteReport(rep.id)}
                  className="h-8 px-2 text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
                <Link href={`/reports/${rep.id}`}>
                  <Button variant="primary" size="sm" className="h-8 gap-1.5">
                    <FolderOpen className="w-3.5 h-3.5 shrink-0" />
                    Open Report
                  </Button>
                </Link>
              </div>
            </Card>
          ))}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-[var(--bg-border)] pt-[var(--space-4)] mt-[var(--space-2)]">
              <span className="text-[0.75rem] text-[var(--text-muted)] font-medium">
                Page {currentPage} of {totalPages}
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((c) => Math.max(1, c - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((c) => Math.min(totalPages, c + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
