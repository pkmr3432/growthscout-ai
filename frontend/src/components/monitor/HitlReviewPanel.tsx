"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Check, X } from "lucide-react";
import { OpportunityBadge } from "@/components/ui/opportunity-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";

export interface HitlRecommendation {
  id: string;
  title: string;
  category: string;
  evidence: string;
  consequence: string;
  confidence: number;
  impact: "High" | "Medium" | "Low";
  value: string;
  approved: boolean;
}

interface HitlReviewPanelProps {
  initialRecommendations: HitlRecommendation[];
  onSubmit: (approved: boolean, recommendations: HitlRecommendation[], notes: string) => void;
  isSubmitting: boolean;
}

export function HitlReviewPanel({
  initialRecommendations,
  onSubmit,
  isSubmitting,
}: HitlReviewPanelProps) {
  const [recs, setRecs] = useState<HitlRecommendation[]>(initialRecommendations);
  const [notes, setNotes] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editEvidence, setEditEvidence] = useState("");

  const handleToggleApprove = (id: string) => {
    setRecs((prev) =>
      prev.map((r) => (r.id === id ? { ...r, approved: !r.approved } : r))
    );
  };

  const handleConfidenceChange = (id: string, val: number) => {
    setRecs((prev) =>
      prev.map((r) => (r.id === id ? { ...r, confidence: val } : r))
    );
  };

  const startEdit = (rec: HitlRecommendation) => {
    setEditingId(rec.id);
    setEditTitle(rec.title);
    setEditEvidence(rec.evidence);
  };

  const saveEdit = (id: string) => {
    setRecs((prev) =>
      prev.map((r) =>
        r.id === id ? { ...r, title: editTitle, evidence: editEvidence } : r
      )
    );
    setEditingId(null);
  };

  const approvedCount = recs.filter((r) => r.approved).length;

  return (
    <div className="flex flex-col gap-[var(--space-6)]">
      <Alert variant="warning" title="Human-in-the-Loop Review Gate">
        The AI analysis has paused on a human verification gate. Review the opportunities and evidence gathered, adjust values, and approve to advance.
      </Alert>

      {/* Grid List of Opportunities */}
      <div className="flex flex-col gap-[var(--space-4)]">
        <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">
          Discovered Recommendations ({recs.length})
        </h3>

        {recs.map((rec) => {
          const isEditing = editingId === rec.id;
          return (
            <Card
              key={rec.id}
              className={`
                flex flex-col gap-[var(--space-4)] border-l-4 transition-all duration-[var(--duration-fast)]
                ${rec.approved ? "border-l-[var(--color-primary)]" : "border-l-[var(--bg-border)] opacity-60"}
              `}
            >
              {/* Card Header */}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-[var(--space-2)]">
                <div>
                  {isEditing ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="
                        w-full h-8 px-2 text-[0.875rem] font-semibold
                        bg-[var(--bg-base)] border border-[var(--bg-border)]
                        rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]
                      "
                    />
                  ) : (
                    <h4 className="font-bold text-[0.9375rem] text-[var(--text-primary)]">
                      {rec.title}
                    </h4>
                  )}
                  <span className="text-[0.75rem] text-[var(--text-secondary)] font-medium mt-0.5 block">
                    Category: {rec.category}
                  </span>
                </div>

                <div className="flex items-center gap-[var(--space-2)] mt-1 sm:mt-0 shrink-0">
                  <OpportunityBadge score={rec.confidence} />
                  <Button
                    variant={rec.approved ? "primary" : "secondary"}
                    size="sm"
                    onClick={() => handleToggleApprove(rec.id)}
                    className="h-8 px-3"
                    aria-label={rec.approved ? "Approve recommendation" : "Reject recommendation"}
                  >
                    {rec.approved ? <ThumbsUp className="w-3.5 h-3.5" /> : <ThumbsDown className="w-3.5 h-3.5" />}
                    <span className="ml-1.5 text-[0.75rem]">{rec.approved ? "Approved" : "Excluded"}</span>
                  </Button>
                </div>
              </div>

              {/* Evidence & Consequence */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-4)] bg-[var(--bg-base)] p-[var(--space-3)] rounded border border-[var(--bg-border)]">
                <div>
                  <h5 className="text-[0.75rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-1">
                    Technical Evidence
                  </h5>
                  {isEditing ? (
                    <textarea
                      value={editEvidence}
                      onChange={(e) => setEditEvidence(e.target.value)}
                      rows={3}
                      className="
                        w-full p-2 text-[0.8125rem] font-mono
                        bg-[var(--bg-surface)] border border-[var(--bg-border)]
                        rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]
                      "
                    />
                  ) : (
                    <p className="text-[0.8125rem] text-[var(--text-primary)] italic leading-relaxed">
                      &ldquo;{rec.evidence}&rdquo;
                    </p>
                  )}
                </div>
                <div>
                  <h5 className="text-[0.75rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider mb-1">
                    Business Consequence
                  </h5>
                  <p className="text-[0.8125rem] text-[var(--text-secondary)] leading-relaxed">
                    {rec.consequence}
                  </p>
                </div>
              </div>

              {/* Value and sliders */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-[var(--space-4)] pt-2 border-t border-[var(--bg-border)]">
                <div className="flex items-center gap-[var(--space-4)] text-[0.8125rem]">
                  <div>
                    <span className="text-[var(--text-muted)]">Impact:</span>{" "}
                    <span className="font-semibold text-[var(--text-primary)]">{rec.impact}</span>
                  </div>
                  <div>
                    <span className="text-[var(--text-muted)]">Est. Annual Value:</span>{" "}
                    <span className="font-semibold text-[var(--color-success)]">{rec.value}</span>
                  </div>
                </div>

                <div className="flex items-center gap-[var(--space-4)] flex-1 max-w-xs justify-end">
                  <span className="text-[0.75rem] text-[var(--text-muted)] shrink-0 font-medium">Confidence Score:</span>
                  <input
                    type="range"
                    min="1"
                    max="100"
                    value={rec.confidence}
                    onChange={(e) => handleConfidenceChange(rec.id, parseInt(e.target.value, 10))}
                    className="w-full accent-[var(--color-primary)] h-1 bg-[var(--bg-border)] rounded-lg cursor-pointer"
                    aria-label="Adjust confidence score slider"
                  />
                </div>
              </div>

              {/* Card footer edit buttons */}
              <div className="flex justify-end gap-[var(--space-2)] border-t border-[var(--bg-border)] pt-[var(--space-2)]">
                {isEditing ? (
                  <>
                    <Button variant="secondary" size="sm" onClick={() => setEditingId(null)} className="h-7 px-2">
                      <X className="w-3.5 h-3.5" />
                      Cancel
                    </Button>
                    <Button variant="primary" size="sm" onClick={() => saveEdit(rec.id)} className="h-7 px-2">
                      <Check className="w-3.5 h-3.5" />
                      Save
                    </Button>
                  </>
                ) : (
                  <Button variant="ghost" size="sm" onClick={() => startEdit(rec)} className="h-7 px-2 text-[0.75rem]">
                    Edit Text
                  </Button>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Feedback notes */}
      <div className="flex flex-col gap-[var(--space-2)] bg-[var(--bg-surface)] border border-[var(--bg-border)] p-[var(--space-4)] rounded-[var(--radius-lg)]">
        <label htmlFor="feedback-notes" className="text-[0.875rem] font-bold text-[var(--text-primary)]">
          Reviewer Notes / Revision Request Instructions
        </label>
        <textarea
          id="feedback-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Enter notes to append to the report, or outline requested revisions if rejecting..."
          rows={4}
          className="
            w-full p-[var(--space-3)] text-[0.875rem]
            bg-[var(--bg-base)] border border-[var(--bg-border)]
            rounded-[var(--radius-md)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
            focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent
          "
        />

        <div className="flex items-center justify-between border-t border-[var(--bg-border)] pt-[var(--space-4)] mt-[var(--space-2)]">
          <div className="text-[0.8125rem] text-[var(--text-muted)] font-medium">
            {approvedCount} of {recs.length} recommendations approved
          </div>
          <div className="flex items-center gap-[var(--space-3)]">
            <Button
              variant="secondary"
              loading={isSubmitting}
              onClick={() => onSubmit(false, recs, notes)}
              className="border-[var(--color-error)] text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
            >
              <ThumbsDown className="w-4 h-4 shrink-0" />
              Request Revision
            </Button>
            <Button
              variant="primary"
              loading={isSubmitting}
              disabled={approvedCount === 0}
              onClick={() => onSubmit(true, recs, notes)}
            >
              <ThumbsUp className="w-4 h-4 shrink-0" />
              Approve & Resume
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
