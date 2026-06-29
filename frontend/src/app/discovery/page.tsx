"use client";

import { useState, useEffect, useMemo, useTransition, Suspense, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, Sparkles, RefreshCw } from "lucide-react";
import {
  PageContainer,
  SectionHeader,
  Card,
  CardTitle,
  Input,
  Button,
  Alert,
  SkeletonCard,
  EmptyState,
  Dialog,
  OpportunityBadge,
} from "@/components/ui";
import {
  SearchHistory,
  type SearchHistoryItem,
} from "@/components/discovery/SearchHistory";
import { SearchFilters, type FilterState } from "@/components/discovery/SearchFilters";
import { ResultsTable } from "@/components/discovery/ResultsTable";
import { BusinessCard } from "@/components/discovery/BusinessCard";
import { createSession, generateMockLeads, type LeadProfile } from "@/utils/api-client";

const nicheOptions = [
  "Dental Clinic",
  "Auto Repair Shop",
  "HVAC Repair Services",
  "Roofing Contractor",
  "Law Firm",
  "Bakery",
  "Coffee Shop",
  "Gym",
  "Dry Cleaner",
  "Accounting Services",
];

const ITEMS_PER_PAGE = 5;

function DiscoveryContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  // Search parameters state
  const [niche, setNiche] = useState("");
  const [location, setLocation] = useState("");
  const [maxLeads, setMaxLeads] = useState(5);

  // Form errors
  const [errors, setErrors] = useState<{ niche?: string; location?: string }>({});

  // Loading/Error states
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Search History State
  const [searchHistory, setHistory] = useState<SearchHistoryItem[]>([]);

  // Search Results
  const [leads, setLeads] = useState<LeadProfile[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);

  // Filters State
  const [filters, setFilters] = useState<FilterState>({
    scoreRange: "all",
    hasWebsite: "all",
    searchTerm: "",
  });

  // Sorting State
  const [sortField, setSortField] = useState<"name" | "score">("name");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Selected Lead for Analysis Dialog (Phase 10.5 Placeholder)
  const [selectedLead, setSelectedLead] = useState<LeadProfile | null>(null);

  // Sync Search History to localStorage
  const saveHistory = useCallback((newHistory: SearchHistoryItem[]) => {
    setHistory(newHistory);
    localStorage.setItem("gs-search-history", JSON.stringify(newHistory));
  }, []);

  // Perform lead extraction query
  const triggerSearch = useCallback(async (sNiche: string, sLocation: string, sMaxLeads: number) => {
    setIsLoading(true);
    setApiError(null);
    setHasSearched(true);
    setCurrentPage(1);

    try {
      // 1. Call real backend API POST /sessions to register the session
      const session = await createSession({
        niche: sNiche,
        location: sLocation,
        max_leads: sMaxLeads,
      });

      // 2. Generate matching leads deterministically based on parameters
      const extractedLeads = generateMockLeads(sNiche, sLocation, sMaxLeads);
      setLeads(extractedLeads);

      // 3. Update search history list
      const newHistoryItem: SearchHistoryItem = {
        id: session.session_id,
        niche: sNiche,
        location: sLocation,
        maxLeads: sMaxLeads,
        timestamp: new Date().toISOString(),
      };
      
      setHistory((prev) => {
        const filteredHistory = prev.filter(
          (h) => !(h.niche.toLowerCase() === sNiche.toLowerCase() && h.location.toLowerCase() === sLocation.toLowerCase())
        );
        const updated = [newHistoryItem, ...filteredHistory].slice(0, 5);
        localStorage.setItem("gs-search-history", JSON.stringify(updated));
        return updated;
      });

    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "An error occurred during search. Please verify base API server status.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load Search History and URL parameters on mount
  useEffect(() => {
    // Load local storage search history
    const saved = localStorage.getItem("gs-search-history");
    let historyTimer: NodeJS.Timeout;
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        historyTimer = setTimeout(() => {
          setHistory(parsed);
        }, 0);
      } catch {
        // ignore
      }
    }

    // Sync state with URL params
    const urlNiche = searchParams.get("niche") ?? "";
    const urlLocation = searchParams.get("location") ?? "";
    const urlMaxLeads = parseInt(searchParams.get("max_leads") ?? "5", 10);

    const syncTimer = setTimeout(() => {
      if (urlNiche) setNiche(urlNiche);
      if (urlLocation) setLocation(urlLocation);
      if (urlMaxLeads) setMaxLeads(urlMaxLeads);
      
      if (urlNiche && urlLocation) {
        // Auto-trigger search if URL params are present
        triggerSearch(urlNiche, urlLocation, urlMaxLeads);
      }
    }, 0);

    return () => {
      if (historyTimer) clearTimeout(historyTimer);
      clearTimeout(syncTimer);
    };
  }, [searchParams, triggerSearch]);

  // Form Submit Handler
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: { niche?: string; location?: string } = {};

    if (!niche.trim()) newErrors.niche = "Please select or type a niche vertical.";
    if (!location.trim()) newErrors.location = "Target location is required.";

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});

    // Sync params with URL state
    const params = new URLSearchParams();
    params.set("niche", niche);
    params.set("location", location);
    params.set("max_leads", maxLeads.toString());

    startTransition(() => {
      router.push(`/discovery?${params.toString()}`);
    });

    triggerSearch(niche, location, maxLeads);
  };

  // Clear History Handlers
  const handleClearHistoryItem = (id: string) => {
    saveHistory(searchHistory.filter((h) => h.id !== id));
  };

  const handleClearAllHistory = () => {
    saveHistory([]);
  };

  // Re-load past search
  const handleSelectHistory = (item: SearchHistoryItem) => {
    setNiche(item.niche);
    setLocation(item.location);
    setMaxLeads(item.maxLeads);
    setErrors({});
    
    const params = new URLSearchParams();
    params.set("niche", item.niche);
    params.set("location", item.location);
    params.set("max_leads", item.maxLeads.toString());
    
    startTransition(() => {
      router.push(`/discovery?${params.toString()}`);
    });

    triggerSearch(item.niche, item.location, item.maxLeads);
  };

  // Filter & Sort Application
  const filteredLeads = useMemo(() => {
    return leads
      .filter((lead) => {
        // Name Search Filter
        if (filters.searchTerm && !lead.name.toLowerCase().includes(filters.searchTerm.toLowerCase())) {
          return false;
        }

        // Score Range Filter
        if (filters.scoreRange === "high" && lead.opportunity_score < 80) return false;
        if (filters.scoreRange === "medium" && (lead.opportunity_score < 60 || lead.opportunity_score >= 80)) return false;
        if (filters.scoreRange === "low" && lead.opportunity_score >= 60) return false;

        // Website Present Filter
        if (filters.hasWebsite === "yes" && !lead.website) return false;
        if (filters.hasWebsite === "no" && lead.website) return false;

        return true;
      })
      .sort((a, b) => {
        // Sort Logic
        if (sortField === "name") {
          return sortOrder === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
        } else {
          return sortOrder === "asc" ? a.opportunity_score - b.opportunity_score : b.opportunity_score - a.opportunity_score;
        }
      });
  }, [leads, filters, sortField, sortOrder]);

  // Paginated Segment
  const paginatedLeads = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredLeads.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredLeads, currentPage]);

  const totalPages = Math.max(1, Math.ceil(filteredLeads.length / ITEMS_PER_PAGE));

  const handleSort = (field: "name" | "score") => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  return (
    <PageContainer>
      <SectionHeader
        title="Lead Discovery"
        description="Search local business niches and identify digital presence opportunities"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-[var(--space-6)] items-start">
        {/* Left Panel: Search Form + Search History */}
        <div className="flex flex-col gap-[var(--space-6)] lg:col-span-1">
          <Card>
            <CardTitle className="flex items-center gap-1.5">
              <Search className="w-5 h-5 text-[var(--color-primary)]" />
              Find Businesses
            </CardTitle>

            <form onSubmit={handleSearchSubmit} className="flex flex-col gap-[var(--space-4)] mt-[var(--space-4)]">
              {/* Niche Selection dropdown/input */}
              <div className="flex flex-col gap-[var(--space-1)]">
                <label htmlFor="niche-select" className="text-[0.875rem] font-medium text-[var(--text-secondary)]">
                  Business Niche / Category
                </label>
                <div className="relative">
                  <input
                    id="niche-select"
                    type="text"
                    value={niche}
                    onChange={(e) => setNiche(e.target.value)}
                    placeholder="Search dental, plumbing..."
                    list="niches-list"
                    className={`
                      w-full h-10 px-3 text-[0.875rem]
                      bg-[var(--bg-surface)] border border-[var(--bg-border)]
                      rounded-[var(--radius-sm)] text-[var(--text-primary)]
                      focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent
                      ${errors.niche ? "border-[var(--color-error)]" : ""}
                    `}
                  />
                  <datalist id="niches-list">
                    {nicheOptions.map((opt) => (
                      <option key={opt} value={opt} />
                    ))}
                  </datalist>
                </div>
                {errors.niche && (
                  <p className="text-[0.75rem] text-[var(--color-error)] mt-1" role="alert">
                    {errors.niche}
                  </p>
                )}
              </div>

              {/* Location Input */}
              <Input
                label="Target City & State"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Austin, TX"
                error={errors.location}
              />

              {/* Max Leads Slider */}
              <div className="flex flex-col gap-[var(--space-2)]">
                <div className="flex items-center justify-between text-[0.875rem] font-medium">
                  <span className="text-[var(--text-secondary)]">Leads count</span>
                  <span className="text-[var(--color-primary)] font-mono">{maxLeads} leads</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="30"
                  value={maxLeads}
                  onChange={(e) => setMaxLeads(parseInt(e.target.value, 10))}
                  className="w-full accent-[var(--color-primary)] h-1.5 bg-[var(--bg-border)] rounded-lg cursor-pointer"
                />
              </div>

              {/* Discover Submit Button */}
              <Button type="submit" loading={isLoading || isPending} className="w-full">
                <Sparkles className="w-4 h-4 fill-current shrink-0" />
                Discover Leads
              </Button>
            </form>
          </Card>

          {/* Search History Panel */}
          <SearchHistory
            items={searchHistory}
            onSelect={handleSelectHistory}
            onClearOne={handleClearHistoryItem}
            onClearAll={handleClearAllHistory}
          />
        </div>

        {/* Right Panel: Results Listing & Opportunity Cards */}
        <div className="lg:col-span-2 flex flex-col gap-[var(--space-6)]">
          {/* Loading Skeleton state */}
          {isLoading && (
            <div className="flex flex-col gap-[var(--space-4)]">
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </div>
          )}

          {/* API Error state */}
          {!isLoading && apiError && (
            <Alert variant="error" title="Extraction Request Failed">
              <p>{apiError}</p>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => triggerSearch(niche, location, maxLeads)}
                className="mt-[var(--space-3)] flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Retry Extraction
              </Button>
            </Alert>
          )}

          {/* EmptyState before first search */}
          {!isLoading && !apiError && !hasSearched && (
            <EmptyState
              icon={<Search className="w-12 h-12" strokeWidth={1.5} />}
              title="Start Local Lead Discovery"
              description="Select a business category, enter a target location, and click 'Discover Leads' to pull prospects, verify websites, and calculate digital opportunity index scores."
            />
          )}

          {/* Leads Results view */}
          {!isLoading && !apiError && hasSearched && leads.length > 0 && (
            <div className="flex flex-col gap-[var(--space-4)]">
              {/* Filter Panel */}
              <SearchFilters
                filters={filters}
                onChange={setFilters}
                onReset={() => setFilters({ scoreRange: "all", hasWebsite: "all", searchTerm: "" })}
                totalResults={leads.length}
                filteredResults={filteredLeads.length}
              />

              {/* Empty results after filtering */}
              {filteredLeads.length === 0 && (
                <EmptyState
                  title="No Matches Found"
                  description="No discovered business leads match the active filter criteria. Clear or adjust your search filters."
                />
              )}

              {/* Grid / Table Content */}
              {filteredLeads.length > 0 && (
                <>
                  {/* Desktop Table View */}
                  <div className="hidden md:block">
                    <ResultsTable
                      items={paginatedLeads}
                      onActionClick={setSelectedLead}
                      sortField={sortField}
                      sortOrder={sortOrder}
                      onSort={handleSort}
                    />
                  </div>

                  {/* Responsive Mobile Cards View */}
                  <div className="grid grid-cols-1 gap-[var(--space-4)] md:hidden">
                    {paginatedLeads.map((lead) => (
                      <BusinessCard
                        key={lead.id}
                        lead={lead}
                        onActionClick={() => setSelectedLead(lead)}
                      />
                    ))}
                  </div>

                  {/* Pagination Controls */}
                  <div className="flex items-center justify-between border-t border-[var(--bg-border)] pt-[var(--space-4)]">
                    <span className="text-[0.75rem] text-[var(--text-muted)]">
                      Page {currentPage} of {totalPages}
                    </span>
                    <div className="flex items-center gap-[var(--space-2)]">
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
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Analysis Dialog Placeholder (HITL / Phase 10.5) */}
      <Dialog
        open={selectedLead !== null}
        onClose={() => setSelectedLead(null)}
        title="Trigger Workflow Diagnostics"
        footer={
          <div className="flex items-center gap-[var(--space-2)]">
            <Button variant="secondary" onClick={() => setSelectedLead(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                if (!selectedLead) return;
                try {
                  const session = await createSession({
                    niche: selectedLead.niche,
                    location: selectedLead.location,
                    max_leads: 5,
                  });
                  setSelectedLead(null);
                  router.push(`/sessions/${session.session_id}`);
                } catch (e) {
                  alert("Failed to initiate audit diagnostic run: " + (e instanceof Error ? e.message : String(e)));
                }
              }}
            >
              Confirm & Start Audit
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-[var(--space-4)]">
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-[1.125rem]">{selectedLead?.name}</h4>
            {selectedLead && <OpportunityBadge score={selectedLead.opportunity_score} />}
          </div>
          <p className="text-[0.875rem] text-[var(--text-secondary)]">
            Confirming will register a state machine audit run. The multi-agent orchestrator will initiate page audits, crawlers, and score generation on:
          </p>
          <div className="p-[var(--space-3)] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded-[var(--radius-sm)]">
            <div className="flex items-center gap-[var(--space-2)] text-[0.875rem] font-semibold">
              <span className="text-[var(--text-muted)]">Domain:</span>
              <span className="text-[var(--color-primary)]">{selectedLead?.website || "Lacks Website"}</span>
            </div>
            <div className="flex items-center gap-[var(--space-2)] text-[0.875rem] mt-[var(--space-1)]">
              <span className="text-[var(--text-muted)]">Address:</span>
              <span>{selectedLead?.address}</span>
            </div>
          </div>
          <Alert variant="info" title="Integrated Workflow Monitor">
            Confirming will take you to the live workflow monitor page where you can run the diagnostic, inspect agent timeline states, view real-time crawl logs, and participate in human review feedback.
          </Alert>
        </div>
      </Dialog>
    </PageContainer>
  );
}

export default function DiscoveryPage() {
  return (
    <Suspense
      fallback={
        <PageContainer>
          <SectionHeader
            title="Lead Discovery"
            description="Loading discovery tools..."
          />
          <div className="flex flex-col gap-[var(--space-4)]">
            <div className="skeleton h-[200px] w-full" />
          </div>
        </PageContainer>
      }
    >
      <DiscoveryContent />
    </Suspense>
  );
}
