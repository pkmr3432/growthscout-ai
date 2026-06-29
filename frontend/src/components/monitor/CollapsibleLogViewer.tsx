"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Copy, Terminal, ChevronDown, ChevronUp, Check, Search } from "lucide-react";
import { Button } from "@/components/ui/button";

interface LogLine {
  timestamp: string;
  level: "info" | "warning" | "error";
  message: string;
  source: string;
}

interface CollapsibleLogViewerProps {
  logs: LogLine[];
  onClear?: () => void;
}

export function CollapsibleLogViewer({ logs }: CollapsibleLogViewerProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of logs if scroll is already near bottom
  useEffect(() => {
    if (collapsed || !containerRef.current) return;
    const el = containerRef.current;
    const threshold = 100; // px
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    if (isNearBottom || el.scrollTop === 0) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logs, collapsed]);

  const filteredLogs = useMemo(() => {
    if (!search.trim()) return logs;
    const q = search.toLowerCase();
    return logs.filter(
      (l) => l.message.toLowerCase().includes(q) || l.source.toLowerCase().includes(q)
    );
  }, [logs, search]);

  const handleCopy = async () => {
    const text = logs
      .map((l) => `[${l.timestamp}] [${l.level.toUpperCase()}] [${l.source}] ${l.message}`)
      .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error("Failed to copy logs:", e);
    }
  };

  const getLevelColor = (level: string) => {
    if (level === "error") return "text-[var(--color-error)]";
    if (level === "warning") return "text-[var(--color-warning)]";
    return "text-[var(--text-secondary)]";
  };

  return (
    <div className="border border-[var(--bg-border)] rounded-[var(--radius-lg)] overflow-hidden">
      {/* Header controls */}
      <div className="flex items-center justify-between p-[var(--space-3)] bg-[var(--bg-surface)] border-b border-[var(--bg-border)] select-none">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[var(--color-primary)]" />
          <span className="text-[0.875rem] font-semibold font-mono text-[var(--text-primary)]">
            Execution Logs Console ({filteredLogs.length})
          </span>
        </div>
        <div className="flex items-center gap-[var(--space-2)]">
          {/* Search log field */}
          <div className="relative hidden sm:block">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search console..."
              className="
                h-7 pl-7 pr-2 text-[0.75rem] font-mono
                bg-[var(--bg-base)] border border-[var(--bg-border)]
                rounded-[var(--radius-sm)] text-[var(--text-primary)]
                focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]
              "
            />
            <Search className="w-3.5 h-3.5 text-[var(--text-muted)] absolute left-2 top-1.5" />
          </div>

          <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 px-2" aria-label="Copy logs">
            {copied ? <Check className="w-3.5 h-3.5 text-[var(--color-success)]" /> : <Copy className="w-3.5 h-3.5" />}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCollapsed(!collapsed)}
            className="h-7 px-2"
            aria-expanded={!collapsed}
            aria-label="Toggle terminal display"
          >
            {collapsed ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </Button>
        </div>
      </div>

      {/* Terminal View body */}
      {!collapsed && (
        <div
          ref={containerRef}
          className="
            p-[var(--space-4)] h-[240px]
            bg-[var(--bg-base)]
            font-mono text-[0.75rem] leading-[1.6]
            overflow-y-auto flex flex-col gap-1
          "
          role="log"
          aria-live="polite"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-[var(--text-muted)] text-center py-[var(--space-8)]">
              No console outputs matched search query.
            </div>
          ) : (
            filteredLogs.map((log, i) => (
              <div key={i} className="flex items-start gap-3 select-text">
                <span className="text-[var(--text-muted)] shrink-0 select-none">{log.timestamp}</span>
                <span className={`shrink-0 font-bold ${getLevelColor(log.level)} select-none`}>
                  [{log.source.toUpperCase()}]
                </span>
                <span className="text-[var(--text-primary)] break-all whitespace-pre-wrap">
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
