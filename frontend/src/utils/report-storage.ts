/* ──────────────────────────────────────────────────
   GrowthScout AI — Report & Proposals Storage Manager
   Phase 10.6 Specifications
   ────────────────────────────────────────────────── */

export interface BrandingSettings {
  agencyLogo?: string; // base64 or URL
  agencyName: string;
  consultantName: string;
  phone: string;
  email: string;
  website: string;
  linkedin: string;
  footerText: string;
  disclaimer: string;
  accentColor: string; // Hex color
  includeCoverPage: boolean;
}

export interface OpportunityOverride {
  id: string;
  title: string;
  category: string;
  severity: "High" | "Medium" | "Low";
  confidence: number;
  evidence: string;
  consequence: string;
  estimatedRevenue: string;
  recommendedService: string;
  estimatedEffort: "Low" | "Medium" | "High";
  technicalDetails: string;
  reasoningSummary: string;
  included: boolean;
}

export interface ReportOverrides {
  id: string; // Report ID (either session_id or generated uuid)
  clientName: string;
  companyName: string;
  preparedBy: string;
  proposalTitle: string;
  executiveSummary: string;
  opportunities: OpportunityOverride[];
  businessValueSummary: string;
  callToAction: string;
  closingRemarks: string;
  finalPrice: string;
  notes: string;
}

export interface ReportHistoryItem {
  id: string; // reportId
  sessionId: string;
  title: string;
  clientName: string;
  companyName: string;
  opportunityScore: number;
  createdAt: string;
  isArchived: boolean;
}

export const DEFAULT_BRANDING: BrandingSettings = {
  agencyName: "Apex Digital Consulting",
  consultantName: "Alex Mercer",
  phone: "(555) 321-7654",
  email: "alex@apexdigital.io",
  website: "www.apexdigital.io",
  linkedin: "linkedin.com/in/alexmercer",
  footerText: "GrowthScout AI Intelligence Report — Confidential",
  disclaimer: "Disclaimer: Audit findings are generated using automated analysis. Values are estimates.",
  accentColor: "#2563eb", // color-primary default
  includeCoverPage: true,
};

export function getBranding(): BrandingSettings {
  if (typeof window === "undefined") return DEFAULT_BRANDING;
  const saved = localStorage.getItem("gs-branding");
  if (!saved) return DEFAULT_BRANDING;
  try {
    return { ...DEFAULT_BRANDING, ...JSON.parse(saved) };
  } catch {
    return DEFAULT_BRANDING;
  }
}

export function saveBranding(branding: BrandingSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("gs-branding", JSON.stringify(branding));
}

export function getReportOverrides(reportId: string): ReportOverrides | null {
  if (typeof window === "undefined") return null;
  const saved = localStorage.getItem("gs-report-overrides");
  if (!saved) return null;
  try {
    const overridesMap = JSON.parse(saved);
    return overridesMap[reportId] || null;
  } catch {
    return null;
  }
}

export function saveReportOverrides(reportId: string, overrides: Partial<ReportOverrides>): void {
  if (typeof window === "undefined") return;
  const saved = localStorage.getItem("gs-report-overrides");
  let overridesMap: Record<string, ReportOverrides> = {};
  if (saved) {
    try {
      overridesMap = JSON.parse(saved);
    } catch {
      // reset if corrupted
    }
  }

  const existing = overridesMap[reportId] || {
    id: reportId,
    clientName: "",
    companyName: "",
    preparedBy: "",
    proposalTitle: "Digital Presence & Growth Opportunity Proposal",
    executiveSummary: "",
    opportunities: [],
    businessValueSummary: "",
    callToAction: "",
    closingRemarks: "",
    finalPrice: "",
    notes: "",
  };

  overridesMap[reportId] = { ...existing, ...overrides } as ReportOverrides;
  localStorage.setItem("gs-report-overrides", JSON.stringify(overridesMap));
}

export function getReportHistory(): ReportHistoryItem[] {
  if (typeof window === "undefined") return [];
  const saved = localStorage.getItem("gs-report-history");
  if (!saved) return [];
  try {
    return JSON.parse(saved);
  } catch {
    return [];
  }
}

export function saveReportHistory(history: ReportHistoryItem[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("gs-report-history", JSON.stringify(history));
}

// Settings Interfaces
export interface ProfileSettings {
  displayName: string;
  agencyName: string;
  consultantName: string;
  email: string;
  phone: string;
  website: string;
  linkedin: string;
  timezone: string;
  defaultCurrency: string;
  defaultLanguage: string;
}

export interface ApiKeysSettings {
  googleMapsKey: string;
  googleMapsStatus: "unconfigured" | "valid" | "invalid";
  customSearchKey: string;
  customSearchStatus: "unconfigured" | "valid" | "invalid";
  llmProviderKey: string;
  llmProviderStatus: "unconfigured" | "valid" | "invalid";
}

export interface PreferencesSettings {
  defaultPage: string;
  defaultReportTemplate: string;
  defaultOpportunityThreshold: number;
  defaultPageSize: number;
  defaultSortOrder: "asc" | "desc";
  autosaveInterval: number;
}

export const DEFAULT_PROFILE: ProfileSettings = {
  displayName: "Alex Mercer",
  agencyName: "Apex Digital Consulting",
  consultantName: "Alex Mercer",
  email: "alex@apexdigital.io",
  phone: "(555) 321-7654",
  website: "www.apexdigital.io",
  linkedin: "linkedin.com/in/alexmercer",
  timezone: "UTC",
  defaultCurrency: "USD",
  defaultLanguage: "en",
};

export const DEFAULT_API_KEYS: ApiKeysSettings = {
  googleMapsKey: "",
  googleMapsStatus: "unconfigured",
  customSearchKey: "",
  customSearchStatus: "unconfigured",
  llmProviderKey: "",
  llmProviderStatus: "unconfigured",
};

export const DEFAULT_PREFERENCES: PreferencesSettings = {
  defaultPage: "/dashboard",
  defaultReportTemplate: "Standard Intelligence Report",
  defaultOpportunityThreshold: 70,
  defaultPageSize: 10,
  defaultSortOrder: "desc",
  autosaveInterval: 5,
};

export function getProfile(): ProfileSettings {
  if (typeof window === "undefined") return DEFAULT_PROFILE;
  const saved = localStorage.getItem("gs-settings");
  if (!saved) return DEFAULT_PROFILE;
  try {
    return { ...DEFAULT_PROFILE, ...JSON.parse(saved) };
  } catch {
    return DEFAULT_PROFILE;
  }
}

export function saveProfile(profile: ProfileSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("gs-settings", JSON.stringify(profile));
}

export function getApiKeys(): ApiKeysSettings {
  if (typeof window === "undefined") return DEFAULT_API_KEYS;
  const saved = localStorage.getItem("gs-api-keys");
  if (!saved) return DEFAULT_API_KEYS;
  try {
    return { ...DEFAULT_API_KEYS, ...JSON.parse(saved) };
  } catch {
    return DEFAULT_API_KEYS;
  }
}

export function saveApiKeys(keys: ApiKeysSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("gs-api-keys", JSON.stringify(keys));
}

export function getPreferences(): PreferencesSettings {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  const saved = localStorage.getItem("gs-preferences");
  if (!saved) return DEFAULT_PREFERENCES;
  try {
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(saved) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function savePreferences(prefs: PreferencesSettings): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("gs-preferences", JSON.stringify(prefs));
}

