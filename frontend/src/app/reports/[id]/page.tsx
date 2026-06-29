"use client";
/* eslint-disable @next/next/no-img-element */

import { useState, useEffect, use, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Printer,
  Sliders,
  Settings2,
  Maximize2,
  Minimize2,
  Sun,
  Moon,
  Upload,
} from "lucide-react";
import {
  PageContainer,
  Button,
  Alert,
  SkeletonCard,
} from "@/components/ui";
import { getSession, type SessionResponse } from "@/utils/api-client";
import { OpportunityBadge } from "@/components/ui/opportunity-badge";
import {
  getBranding,
  saveBranding,
  getReportOverrides,
  saveReportOverrides,
  type BrandingSettings,
  type ReportOverrides,
  type OpportunityOverride,
} from "@/utils/report-storage";

interface ReportDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function ReportDetailPage({ params }: ReportDetailPageProps) {
  const { id: reportId } = use(params);

  // States
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Branding
  const [branding, setBrandingState] = useState<BrandingSettings>(() => getBranding());

  // Report fields
  const [overrides, setOverridesState] = useState<ReportOverrides | null>(null);

  // Editor Settings
  const [activeTab, setActiveTab] = useState<"content" | "branding">("content");
  const [previewTheme, setPreviewTheme] = useState<"light" | "dark">("light");
  const [presentationMode, setPresentationMode] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(100);

  // Save branding updates
  const handleBrandingChange = (updated: Partial<BrandingSettings>) => {
    setBrandingState((prev) => {
      const next = { ...prev, ...updated };
      saveBranding(next);
      return next;
    });
  };

  // Save report overrides changes
  const handleOverrideChange = useCallback((updated: Partial<ReportOverrides>) => {
    if (!overrides) return;
    setOverridesState((prev) => {
      if (!prev) return null;
      const next = { ...prev, ...updated };
      saveReportOverrides(reportId, next);
      return next;
    });
  }, [reportId, overrides]);

  // Load baseline completed session
  useEffect(() => {
    const loadSessionData = async () => {
      setIsLoading(true);
      try {
        const liveSession = await getSession(reportId);
        setSession(liveSession);

        // Load existing overrides or initialize baseline
        const existingOverrides = getReportOverrides(reportId);
        if (existingOverrides) {
          setOverridesState(existingOverrides);
        } else {
          // Initialize baseline opportunities from session context or generate defaults
          const niche = liveSession.niche || "Dental Services";
          const location = liveSession.location || "Austin, TX";
          
          const baselineOpportunities: OpportunityOverride[] = [
            {
              id: "op_seo",
              title: "Structured Schema Integration",
              category: "SEO Optimization",
              severity: "High",
              confidence: 85,
              evidence: `No structured JSON-LD local schema markup detected on homepage source for ${niche}.`,
              consequence: "Search engines cannot display contact and service details in rich snippets.",
              estimatedRevenue: "$2,400 / yr",
              recommendedService: "Schema Metadata Implementation",
              estimatedEffort: "Low",
              technicalDetails: "Deploy JSON-LD schemas representing Organization, LocalBusiness, and services catalog.",
              reasoningSummary: "Google leverages schema markup to build trust graphs and display details in local packs.",
              included: true,
            },
            {
              id: "op_speed",
              title: "Core Web Vitals Latency Tuning",
              category: "Performance Optimization",
              severity: "High",
              confidence: 78,
              evidence: "Homepage mobile page loading speed is 5.4 seconds on 4G networks.",
              consequence: "High visitor bounce rates and reduced ranking positioning.",
              estimatedRevenue: "$3,600 / yr",
              recommendedService: "Core Web Vitals Tuning & Asset Caching",
              estimatedEffort: "Medium",
              technicalDetails: "Optimizing media payloads, deferring unused JS, and deploying CDN asset distribution.",
              reasoningSummary: "Page speed is a primary search signal and conversion factor.",
              included: true,
            },
            {
              id: "op_cro",
              title: "Online Conversion Call-to-Actions",
              category: "Conversion Rate Optimization",
              severity: "Medium",
              confidence: 90,
              evidence: "No contact form, appointment schedule widget, or phone link detected above the fold.",
              consequence: "High visitor abandonment because of booking flow friction.",
              estimatedRevenue: "$1,800 / yr",
              recommendedService: "Frictionless Booking Integrations",
              estimatedEffort: "Low",
              technicalDetails: "Embed booking calendar integrations and place tap-to-call link CTA blocks prominently.",
              reasoningSummary: "Local service clients prioritize instant contact options.",
              included: true,
            },
          ];

          const newOverrides: ReportOverrides = {
            id: reportId,
            clientName: "Business Owner",
            companyName: `${niche} Services`,
            preparedBy: branding.consultantName || "Consultant Analyst",
            proposalTitle: `${niche} Growth Opportunity Analysis`,
            executiveSummary: `We performed a comprehensive diagnostic audit of the digital presence for ${niche} in ${location}. Our analysis revealed several critical optimization opportunities in local search pack positioning, mobile speed latencies, and conversion funnel components. Addressing these gaps will dramatically reduce customer acquisition costs.`,
            opportunities: baselineOpportunities,
            businessValueSummary: "Addressing these three critical opportunities is estimated to capture between 15-30% more client leads annually.",
            callToAction: "Schedule a complimentary 15-minute diagnostic review call to finalize the integration scope.",
            closingRemarks: "We look forward to partnering with your team to scale your digital presence.",
            finalPrice: "1250",
            notes: "Suggested pricing includes complete deployment, tag auditing, and a 30-day post-launch review.",
          };

          saveReportOverrides(reportId, newOverrides);
          setOverridesState(newOverrides);
        }
      } catch (err: unknown) {
        setLoadError(err instanceof Error ? err.message : "Failed to load session reports data.");
      } finally {
        setIsLoading(false);
      }
    };

    loadSessionData();
  }, [reportId, branding.consultantName]);

  // Handle opportunity checkboxes toggling
  const handleToggleOpportunity = (opId: string) => {
    if (!overrides) return;
    const updatedOps = overrides.opportunities.map((o) =>
      o.id === opId ? { ...o, included: !o.included } : o
    );
    handleOverrideChange({ opportunities: updatedOps });
  };

  // Opportunity edit details
  const handleOpportunityDetailChange = (opId: string, fields: Partial<OpportunityOverride>) => {
    if (!overrides) return;
    const updatedOps = overrides.opportunities.map((o) =>
      o.id === opId ? { ...o, ...fields } : o
    );
    handleOverrideChange({ opportunities: updatedOps });
  };

  const handleLogoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      if (event.target?.result) {
        handleBrandingChange({ agencyLogo: event.target.result as string });
      }
    };
    reader.readAsDataURL(file);
  };

  // Printable action
  const handlePrint = () => {
    window.print();
  };

  // Calculate totals
  const totalSuggestedLow = 800;
  const totalSuggestedHigh = 1600;

  if (isLoading) {
    return (
      <PageContainer>
        <div className="flex flex-col gap-[var(--space-6)]">
          <SkeletonCard />
        </div>
      </PageContainer>
    );
  }

  if (loadError || !session || !overrides) {
    return (
      <PageContainer>
        <Alert variant="error" title="Report Load Failed">
          <p>{loadError ?? "Unable to resolve completed session parameters."}</p>
          <Link href="/reports" className="mt-4 inline-block">
            <Button variant="secondary">Back to Reports</Button>
          </Link>
        </Alert>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="p-0 sm:p-0 md:p-0 max-w-full">
      {/* Top Toolbar Control Strip (Hidden in Print Mode) */}
      <div className="flex items-center justify-between p-[var(--space-4)] bg-[var(--bg-surface)] border-b border-[var(--bg-border)] no-print select-none">
        <div className="flex items-center gap-[var(--space-3)]">
          <Link
            href="/reports"
            className="p-2 rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <span className="font-semibold text-[0.875rem] text-[var(--text-primary)] max-w-xs truncate hidden sm:block">
            {overrides.proposalTitle}
          </span>
        </div>

        <div className="flex items-center gap-[var(--space-2)]">
          {/* Light/Dark preview toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setPreviewTheme(previewTheme === "light" ? "dark" : "light")}
            title="Toggle Light/Dark Preview Mode"
            className="h-8 px-2"
          >
            {previewTheme === "light" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          </Button>

          {/* Zoom controls */}
          <div className="hidden lg:flex items-center gap-2 border-r border-[var(--bg-border)] pr-[var(--space-3)] mr-[var(--space-2)] text-[0.75rem] text-[var(--text-muted)]">
            <span>Zoom:</span>
            <input
              type="range"
              min="50"
              max="150"
              value={zoomLevel}
              onChange={(e) => setZoomLevel(parseInt(e.target.value, 10))}
              className="w-20 accent-[var(--color-primary)] cursor-pointer"
            />
            <span className="font-mono">{zoomLevel}%</span>
          </div>

          {/* Presentation Toggle */}
          <Button
            variant={presentationMode ? "primary" : "secondary"}
            size="sm"
            onClick={() => setPresentationMode(!presentationMode)}
            className="h-8 gap-1.5"
          >
            {presentationMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            <span className="text-[0.75rem]">{presentationMode ? "Exit Present" : "Presentation Mode"}</span>
          </Button>

          {/* Export PDF */}
          <Button variant="primary" size="sm" onClick={handlePrint} className="h-8 gap-1.5">
            <Printer className="w-4 h-4" />
            <span className="text-[0.75rem]">Download PDF</span>
          </Button>
        </div>
      </div>

      {/* Main Workspace Split Layout */}
      <div className="flex flex-col lg:flex-row min-h-[calc(100vh-var(--header-height)-1px)] overflow-x-hidden">
        {/* LEFT PANEL: Proposal Editor Forms (Hidden in Presentation Mode & Print) */}
        {!presentationMode && (
          <div className="w-full lg:w-[400px] xl:w-[450px] bg-[var(--bg-surface)] border-r border-[var(--bg-border)] no-print shrink-0 flex flex-col">
            {/* Tabs */}
            <div className="flex border-b border-[var(--bg-border)]">
              <button
                onClick={() => setActiveTab("content")}
                className={`flex-1 py-3 text-[0.8125rem] font-bold border-b-2 flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeTab === "content"
                    ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                    : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                <Sliders className="w-4 h-4" />
                Proposal Builder
              </button>
              <button
                onClick={() => setActiveTab("branding")}
                className={`flex-1 py-3 text-[0.8125rem] font-bold border-b-2 flex items-center justify-center gap-1.5 cursor-pointer ${
                  activeTab === "branding"
                    ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                    : "border-transparent text-[var(--text-secondary)] hover:text(--text-primary)"
                }`}
              >
                <Settings2 className="w-4 h-4" />
                Branding & Info
              </button>
            </div>

            {/* Scrollable forms wrapper */}
            <div className="p-[var(--space-4)] overflow-y-auto flex-1 flex flex-col gap-[var(--space-5)] max-h-[calc(100vh-120px)]">
              {activeTab === "content" ? (
                <>
                  {/* Client Info */}
                  <div className="flex flex-col gap-[var(--space-3)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Client Profile
                    </h3>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Client Name</label>
                      <input
                        type="text"
                        value={overrides.clientName}
                        onChange={(e) => handleOverrideChange({ clientName: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Company Name</label>
                      <input
                        type="text"
                        value={overrides.companyName}
                        onChange={(e) => handleOverrideChange({ companyName: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                  </div>

                  {/* Narrative details */}
                  <div className="flex flex-col gap-[var(--space-3)] border-t border-[var(--bg-border)] pt-[var(--space-4)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Executive Narrative
                    </h3>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Proposal Title</label>
                      <input
                        type="text"
                        value={overrides.proposalTitle}
                        onChange={(e) => handleOverrideChange({ proposalTitle: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Executive Summary</label>
                      <textarea
                        value={overrides.executiveSummary}
                        onChange={(e) => handleOverrideChange({ executiveSummary: e.target.value })}
                        rows={4}
                        className="w-full p-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)] leading-normal"
                      />
                    </div>
                  </div>

                  {/* Opportunities list switches */}
                  <div className="flex flex-col gap-[var(--space-3)] border-t border-[var(--bg-border)] pt-[var(--space-4)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Opportunities Inclusion
                    </h3>
                    {overrides.opportunities.map((op) => (
                      <div key={op.id} className="flex flex-col gap-1.5 p-2 bg-[var(--bg-elevated)] rounded border border-[var(--bg-border)]">
                        <div className="flex items-center justify-between">
                          <label className="text-[0.8125rem] font-bold text-[var(--text-primary)] flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={op.included}
                              onChange={() => handleToggleOpportunity(op.id)}
                              className="accent-[var(--color-primary)]"
                            />
                            {op.category}
                          </label>
                          <OpportunityBadge score={op.confidence} />
                        </div>
                        {op.included && (
                          <div className="flex flex-col gap-1.5 mt-2 pt-2 border-t border-[var(--bg-border)]">
                            <input
                              type="text"
                              value={op.title}
                              onChange={(e) => handleOpportunityDetailChange(op.id, { title: e.target.value })}
                              placeholder="Title"
                              className="w-full h-8 px-2 text-[0.75rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded"
                            />
                            <textarea
                              value={op.evidence}
                              onChange={(e) => handleOpportunityDetailChange(op.id, { evidence: e.target.value })}
                              placeholder="Evidence"
                              rows={2}
                              className="w-full p-1 text-[0.75rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded"
                            />
                            <div className="grid grid-cols-2 gap-1.5">
                              <input
                                type="text"
                                value={op.estimatedRevenue}
                                onChange={(e) => handleOpportunityDetailChange(op.id, { estimatedRevenue: e.target.value })}
                                placeholder="Est Value"
                                className="w-full h-8 px-2 text-[0.75rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded"
                              />
                              <input
                                type="text"
                                value={op.recommendedService}
                                onChange={(e) => handleOpportunityDetailChange(op.id, { recommendedService: e.target.value })}
                                placeholder="Service"
                                className="w-full h-8 px-2 text-[0.75rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Proposal value / Pricing */}
                  <div className="flex flex-col gap-[var(--space-3)] border-t border-[var(--bg-border)] pt-[var(--space-4)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Proposal Value & Pricing
                    </h3>
                    <div className="p-2 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded text-[0.75rem] text-[var(--text-muted)] flex flex-col gap-1">
                      <div className="flex justify-between">
                        <span>AI Suggested Price Range:</span>
                        <span className="font-semibold text-[var(--text-primary)] font-mono">
                          ${totalSuggestedLow} - ${totalSuggestedHigh}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-col gap-1 mt-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Final Proposal Price ($)</label>
                      <input
                        type="text"
                        value={overrides.finalPrice}
                        onChange={(e) => handleOverrideChange({ finalPrice: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)] font-mono"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Pricing Notes</label>
                      <input
                        type="text"
                        value={overrides.notes}
                        onChange={(e) => handleOverrideChange({ notes: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                  </div>

                  {/* Footer call to actions */}
                  <div className="flex flex-col gap-[var(--space-3)] border-t border-[var(--bg-border)] pt-[var(--space-4)] mb-[var(--space-6)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Call to Action & Closing
                    </h3>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Call to Action</label>
                      <input
                        type="text"
                        value={overrides.callToAction}
                        onChange={(e) => handleOverrideChange({ callToAction: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Closing Remarks</label>
                      <textarea
                        value={overrides.closingRemarks}
                        onChange={(e) => handleOverrideChange({ closingRemarks: e.target.value })}
                        rows={2}
                        className="w-full p-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)] leading-normal"
                      />
                    </div>
                  </div>
                </>
              ) : (
                /* BRANDING FORM TAB */
                <>
                  <div className="flex flex-col gap-[var(--space-3)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      White-Label Settings
                    </h3>
                    
                    {/* Logo upload */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Agency Logo</label>
                      <div className="flex items-center gap-[var(--space-2)]">
                        {branding.agencyLogo ? (
                          <div className="relative w-12 h-12 bg-white border border-[var(--bg-border)] rounded overflow-hidden flex items-center justify-center p-1 shrink-0">
                            <img src={branding.agencyLogo} alt="Logo" className="max-h-full max-w-full object-contain" />
                          </div>
                        ) : (
                          <div className="w-12 h-12 bg-[var(--bg-base)] border border-[var(--bg-border)] rounded flex items-center justify-center text-[var(--text-muted)] shrink-0 font-bold text-[0.75rem]">
                            LOGO
                          </div>
                        )}
                        <label className="flex-1 flex flex-col items-center justify-center h-12 border border-dashed border-[var(--bg-border)] rounded hover:bg-[var(--bg-hover)] cursor-pointer select-none">
                          <span className="text-[0.75rem] font-bold text-[var(--text-secondary)] flex items-center gap-1">
                            <Upload className="w-3.5 h-3.5" /> Upload File
                          </span>
                          <input type="file" accept="image/*" onChange={handleLogoUpload} className="hidden" />
                        </label>
                      </div>
                    </div>

                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Agency Name</label>
                      <input
                        type="text"
                        value={branding.agencyName}
                        onChange={(e) => handleBrandingChange({ agencyName: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Consultant Name</label>
                      <input
                        type="text"
                        value={branding.consultantName}
                        onChange={(e) => handleBrandingChange({ consultantName: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] text-[var(--text-primary)]"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-[var(--space-3)] border-t border-[var(--bg-border)] pt-[var(--space-4)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Contact Information
                    </h3>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Email Address</label>
                      <input
                        type="email"
                        value={branding.email}
                        onChange={(e) => handleBrandingChange({ email: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Phone Number</label>
                      <input
                        type="text"
                        value={branding.phone}
                        onChange={(e) => handleBrandingChange({ phone: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Website URL</label>
                      <input
                        type="text"
                        value={branding.website}
                        onChange={(e) => handleBrandingChange({ website: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">LinkedIn URL</label>
                      <input
                        type="text"
                        value={branding.linkedin}
                        onChange={(e) => handleBrandingChange({ linkedin: e.target.value })}
                        className="w-full h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-[var(--space-3)] border-t border-[var(--bg-border)] pt-[var(--space-4)] mb-[var(--space-6)]">
                    <h3 className="text-[0.8125rem] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Page Controls & Details
                    </h3>
                    <div className="flex items-center justify-between py-1">
                      <label htmlFor="cover-page-switch" className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Include Cover Page</label>
                      <input
                        id="cover-page-switch"
                        type="checkbox"
                        checked={branding.includeCoverPage}
                        onChange={(e) => handleBrandingChange({ includeCoverPage: e.target.checked })}
                        className="accent-[var(--color-primary)] w-4 h-4"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Branding Accent Color</label>
                      <div className="flex items-center gap-[var(--space-2)]">
                        <input
                          type="color"
                          value={branding.accentColor}
                          onChange={(e) => handleBrandingChange({ accentColor: e.target.value })}
                          className="w-9 h-9 border border-[var(--bg-border)] rounded cursor-pointer bg-transparent"
                        />
                        <input
                          type="text"
                          value={branding.accentColor}
                          onChange={(e) => handleBrandingChange({ accentColor: e.target.value })}
                          className="flex-1 h-9 px-2 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none font-mono"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Footer Disclaimer</label>
                      <textarea
                        value={branding.disclaimer}
                        onChange={(e) => handleBrandingChange({ disclaimer: e.target.value })}
                        rows={3}
                        className="w-full p-2 text-[0.75rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none text-[var(--text-muted)] leading-relaxed"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* RIGHT PANEL: Report Canonical Preview Rendering */}
        <div
          className={`
            flex-1 bg-[var(--bg-base)] p-[var(--space-6)] overflow-y-auto print-container
            ${previewTheme === "light" ? "data-theme-light" : ""}
          `}
          style={{ background: previewTheme === "light" ? "#f3f4f6" : undefined }}
        >
          <div
            id="report-print-target"
            className="
              mx-auto bg-white text-gray-900 shadow-[var(--shadow-med)] rounded-[var(--radius-lg)]
              p-[15mm] border border-gray-200 transition-all duration-[var(--duration-fast)]
              print:shadow-none print:border-none print:rounded-none print:p-0 print:m-0 print:max-w-full
            "
            style={{
              maxWidth: presentationMode ? "900px" : "800px",
              width: "100%",
              transform: `scale(${zoomLevel / 100})`,
              transformOrigin: "top center",
              color: "#1f2937", // strict gray-800 for report contrast
            }}
          >
            {/* 1. COVER PAGE */}
            {branding.includeCoverPage && (
              <div className="flex flex-col justify-between min-h-[250mm] page-break-after print:min-h-[250mm] select-text">
                <div className="pt-20">
                  {branding.agencyLogo ? (
                    <img src={branding.agencyLogo} alt="Agency logo" className="max-h-16 max-w-[200px] object-contain mb-8" />
                  ) : (
                    <div className="text-[0.875rem] font-bold text-gray-500 uppercase tracking-widest mb-8">
                      {branding.agencyName}
                    </div>
                  )}
                  <h1 className="text-4xl md:text-5xl font-black text-gray-900 leading-tight tracking-tight mt-6">
                    {overrides.proposalTitle}
                  </h1>
                  <p className="text-lg text-gray-500 mt-4 max-w-xl">
                    Growth Intelligence & technical diagnostics report compiled for local growth opportunity discovery.
                  </p>
                </div>

                <div className="border-t border-gray-200 pt-8 pb-12 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400 font-semibold block uppercase text-[0.6875rem]">Prepared For</span>
                    <span className="font-bold text-gray-900">{overrides.clientName}</span>
                    <span className="text-gray-500 block">{overrides.companyName}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 font-semibold block uppercase text-[0.6875rem]">Prepared By</span>
                    <span className="font-bold text-gray-900">{branding.consultantName}</span>
                    <span className="text-gray-500 block">{branding.agencyName}</span>
                    <span className="text-[0.75rem] text-gray-400 block mt-1">Date: {new Date(session.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            )}

            {/* 2. EXECUTIVE SUMMARY */}
            <div className="page-break-after pt-10 select-text">
              <div className="flex items-center justify-between border-b border-gray-200 pb-3">
                <h2 className="text-2xl font-bold tracking-tight text-gray-900 uppercase">
                  Executive Summary
                </h2>
                <span className="text-[0.75rem] font-mono text-gray-400">Section 1</span>
              </div>
              <p className="text-[0.9375rem] leading-relaxed text-gray-700 mt-6 whitespace-pre-wrap">
                {overrides.executiveSummary}
              </p>

              {/* 3. BUSINESS OVERVIEW */}
              <div className="mt-12">
                <h3 className="text-lg font-bold text-gray-900 uppercase tracking-wide border-b border-gray-100 pb-1.5">
                  Business Overview
                </h3>
                <div className="grid grid-cols-2 gap-6 mt-4 text-sm">
                  <div>
                    <span className="text-gray-400 block font-semibold text-[0.6875rem] uppercase">Audited Niche</span>
                    <span className="text-gray-900 font-bold block mt-0.5">{session.niche}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block font-semibold text-[0.6875rem] uppercase">Audited Location</span>
                    <span className="text-gray-900 font-bold block mt-0.5">{session.location}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block font-semibold text-[0.6875rem] uppercase">Diagnosis Session</span>
                    <span className="font-mono text-gray-600 block mt-0.5">{session.session_id}</span>
                  </div>
                  <div>
                    <span className="text-gray-400 block font-semibold text-[0.6875rem] uppercase">Target Leads Extracted</span>
                    <span className="text-gray-900 font-bold block mt-0.5">{session.max_leads} Leads</span>
                  </div>
                </div>
              </div>

              {/* 4. OPPORTUNITY SCORE */}
              <div className="mt-12 bg-gray-50 border border-gray-100 rounded-lg p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="max-w-md">
                  <h3 className="text-lg font-bold text-gray-900">Overall Growth Opportunity Index</h3>
                  <p className="text-[0.8125rem] text-gray-500 mt-1 leading-normal">
                    This index maps the urgency of technical optimizations. A higher index indicates larger untapped growth potential.
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-5xl font-black text-gray-900 font-mono">
                    {overrides.opportunities.filter((o) => o.included).length > 0 ? overrides.opportunities.reduce((acc, curr) => acc + (curr.included ? curr.confidence : 0), 0) / overrides.opportunities.filter((o) => o.included).length : 0}
                  </span>
                  <span className="text-[0.875rem] font-bold text-gray-400 font-mono">/ 100</span>
                </div>
              </div>
            </div>

            {/* 5. TECHNICAL FINDINGS & 6. BUSINESS IMPACT */}
            <div className="page-break-after pt-10 select-text">
              <div className="flex items-center justify-between border-b border-gray-200 pb-3 mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-gray-900 uppercase">
                  Technical Audits & Business Impact
                </h2>
                <span className="text-[0.75rem] font-mono text-gray-400">Section 2</span>
              </div>

              <div className="flex flex-col gap-6">
                {overrides.opportunities
                  .filter((op) => op.included)
                  .map((op) => (
                    <div key={op.id} className="p-5 border border-gray-200 rounded-lg bg-gray-50/50 print-no-break">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <span className="text-[0.6875rem] font-bold text-blue-600 uppercase tracking-widest">
                            {op.category}
                          </span>
                          <h4 className="font-bold text-base text-gray-900 mt-1">{op.title}</h4>
                        </div>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">
                          {op.severity} Severity
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4 pt-4 border-t border-gray-100 text-sm">
                        <div>
                          <span className="text-gray-400 block font-bold text-[0.6875rem] uppercase">Technical Finding</span>
                          <p className="text-gray-700 mt-1 italic font-medium leading-relaxed">
                            &ldquo;{op.evidence}&rdquo;
                          </p>
                          <div className="mt-3">
                            <span className="text-gray-400 block font-bold text-[0.6875rem] uppercase">Technical Details</span>
                            <p className="text-gray-500 mt-1 text-[0.8125rem] leading-normal">{op.technicalDetails}</p>
                          </div>
                        </div>
                        <div>
                          <span className="text-gray-400 block font-bold text-[0.6875rem] uppercase">Business Risk / Consequence</span>
                          <p className="text-gray-700 mt-1 leading-relaxed">{op.consequence}</p>
                          <div className="mt-3">
                            <span className="text-gray-400 block font-bold text-[0.6875rem] uppercase">Reasoning Summary</span>
                            <p className="text-gray-500 mt-1 text-[0.8125rem] leading-normal">{op.reasoningSummary}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>

            {/* 7. RECOMMENDED SERVICES & 8. ESTIMATED PRICING */}
            <div className="page-break-after pt-10 select-text">
              <div className="flex items-center justify-between border-b border-gray-200 pb-3 mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-gray-900 uppercase">
                  Scope of Recommended Services
                </h2>
                <span className="text-[0.75rem] font-mono text-gray-400">Section 3</span>
              </div>

              <table className="w-full border-collapse text-[0.875rem] text-left">
                <thead>
                  <tr className="border-b border-gray-200 text-[0.75rem] font-semibold text-gray-400 uppercase">
                    <th className="py-2.5">Category</th>
                    <th className="py-2.5">Recommended Service</th>
                    <th className="py-2.5">Effort</th>
                    <th className="py-2.5 text-right">Est. Value Capture</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {overrides.opportunities
                    .filter((op) => op.included)
                    .map((op) => (
                      <tr key={op.id} className="text-gray-700">
                        <td className="py-3 font-semibold text-gray-900">{op.category}</td>
                        <td className="py-3">{op.recommendedService}</td>
                        <td className="py-3">
                          <span className="px-2 py-0.5 rounded text-[0.6875rem] font-medium bg-gray-100 text-gray-800">
                            {op.estimatedEffort}
                          </span>
                        </td>
                        <td className="py-3 text-right font-semibold text-green-600 font-mono">
                          {op.estimatedRevenue}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>

              {/* Estimate business value summary */}
              <div className="mt-8">
                <h4 className="font-bold text-gray-900 text-sm">Value Capture Statement</h4>
                <p className="text-[0.875rem] text-gray-600 mt-1 leading-relaxed">
                  {overrides.businessValueSummary}
                </p>
              </div>

              {/* Final Pricing */}
              <div className="mt-12 bg-gray-50 border border-gray-100 rounded-lg p-6 flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-gray-900">Total Investment Summary</h4>
                  <p className="text-[0.75rem] text-gray-500 mt-0.5">{overrides.notes}</p>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-3xl font-black text-gray-900 font-mono">
                    ${overrides.finalPrice}
                  </span>
                  <span className="text-sm font-semibold text-gray-500 block">Single payment</span>
                </div>
              </div>
            </div>

            {/* 9. RECOMMENDED NEXT STEPS & 10. APPENDIX / 11. AI DISCLAIMER */}
            <div className="pt-10 select-text">
              <div className="flex items-center justify-between border-b border-gray-200 pb-3 mb-6">
                <h2 className="text-2xl font-bold tracking-tight text-gray-900 uppercase">
                  Next Steps & Next Call
                </h2>
                <span className="text-[0.75rem] font-mono text-gray-400">Section 4</span>
              </div>

              <div className="p-5 border border-blue-100 bg-blue-50/50 rounded-lg">
                <h4 className="font-bold text-blue-900 text-sm">Recommended Action Plan</h4>
                <p className="text-[0.875rem] text-blue-950 mt-1 leading-relaxed">
                  {overrides.callToAction}
                </p>
              </div>

              {overrides.closingRemarks && (
                <p className="text-sm text-gray-500 mt-6 leading-relaxed italic">
                  &ldquo;{overrides.closingRemarks}&rdquo;
                </p>
              )}

              {/* Disclaimer */}
              <div className="mt-16 pt-6 border-t border-gray-200">
                <span className="text-gray-400 block font-bold text-[0.6875rem] uppercase">AI Safety Disclaimer</span>
                <p className="text-[0.75rem] text-gray-400 mt-2 leading-relaxed">
                  {branding.disclaimer}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
