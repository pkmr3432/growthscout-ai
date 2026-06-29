"use client";

import { useEffect, useState, useTransition } from "react";
import {
  User,
  Image as ImageIcon,
  KeyRound,
  Paintbrush,
  Bell,
  Sliders,
  ShieldAlert,
  Info,
  Eye,
  EyeOff,
  Copy,
  Check,
  RotateCcw,
  Trash2,
  ExternalLink,
  Sun,
  Moon,
} from "lucide-react";
import {
  PageContainer,
  SectionHeader,
  Card,
  Button,
  Badge,
} from "@/components/ui";
import {
  getProfile,
  saveProfile,
  getBranding,
  saveBranding,
  getApiKeys,
  saveApiKeys,
  getPreferences,
  savePreferences,
  DEFAULT_PROFILE,
  DEFAULT_BRANDING,
  DEFAULT_PREFERENCES,
  type ProfileSettings,
  type BrandingSettings,
  type ApiKeysSettings,
  type PreferencesSettings,
} from "@/utils/report-storage";

type SettingsSection =
  | "profile"
  | "branding"
  | "apikeys"
  | "theme"
  | "notifications"
  | "preferences"
  | "security"
  | "about";

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState<SettingsSection>("profile");

  // Core settings states
  const [profile, setProfileState] = useState<ProfileSettings>(() => getProfile());
  const [branding, setBrandingState] = useState<BrandingSettings>(() => getBranding());
  const [apiKeys, setApiKeysState] = useState<ApiKeysSettings>(() => getApiKeys());
  const [prefs, setPrefsState] = useState<PreferencesSettings>(() => getPreferences());

  // Theme state
  const [theme, setThemeState] = useState<"light" | "dark" | "system">("dark");

  // Local storage usage stats
  const [storageBytes, setStorageBytes] = useState(0);
  const [cachedSessionsCount, setCachedSessionsCount] = useState(0);
  const [cachedReportsCount, setCachedReportsCount] = useState(0);

  // UI state controllers
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({});
  const [isPending, startTransition] = useTransition();

  // Destructive confirmations
  const [confirmAction, setConfirmAction] = useState<{
    type: "clear_cache" | "reset_branding" | "reset_prefs" | null;
    title: string;
    message: string;
  }>({ type: null, title: "", message: "" });

  const recalculateStats = () => {
    if (typeof window === "undefined") return;
    
    // local storage size
    let bytes = 0;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        bytes += (localStorage.getItem(key) || "").length * 2; // UTF-16 characters are 2 bytes
      }
    }
    setStorageBytes(bytes);

    // counts
    const sessions = localStorage.getItem("gs-search-history");
    if (sessions) {
      try {
        setCachedSessionsCount(JSON.parse(sessions).length);
      } catch {
        setCachedSessionsCount(0);
      }
    }

    const reports = localStorage.getItem("gs-report-history");
    if (reports) {
      try {
        setCachedReportsCount(JSON.parse(reports).length);
      } catch {
        setCachedReportsCount(0);
      }
    }
  };

  // Initialize theme and cache calculations
  useEffect(() => {
    if (typeof window !== "undefined") {
      const savedTheme = localStorage.getItem("theme") as "light" | "dark" | "system" | null;
      const timer = setTimeout(() => {
        if (savedTheme) {
          setThemeState(savedTheme);
        }
        recalculateStats();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, []);

  // State update handlers
  const handleProfileChange = (updated: Partial<ProfileSettings>) => {
    setProfileState((prev) => {
      const next = { ...prev, ...updated };
      saveProfile(next);
      return next;
    });
  };

  const handleBrandingChange = (updated: Partial<BrandingSettings>) => {
    setBrandingState((prev) => {
      const next = { ...prev, ...updated };
      saveBranding(next);
      return next;
    });
  };

  const handleApiKeysChange = (updated: Partial<ApiKeysSettings>) => {
    setApiKeysState((prev) => {
      const next = { ...prev, ...updated };
      saveApiKeys(next);
      return next;
    });
  };

  const handlePrefsChange = (updated: Partial<PreferencesSettings>) => {
    setPrefsState((prev) => {
      const next = { ...prev, ...updated };
      savePreferences(next);
      return next;
    });
  };

  const handleThemeChange = (newTheme: "light" | "dark" | "system") => {
    setThemeState(newTheme);
    localStorage.setItem("theme", newTheme);
    
    // Apply theme to document element
    const root = window.document.documentElement;
    if (newTheme === "dark") {
      root.setAttribute("data-theme", "dark");
      root.classList.add("dark");
    } else if (newTheme === "light") {
      root.setAttribute("data-theme", "light");
      root.classList.remove("dark");
    } else {
      // System default resolver
      const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.setAttribute("data-theme", systemDark ? "dark" : "light");
      if (systemDark) root.classList.add("dark");
      else root.classList.remove("dark");
    }
  };

  // Copy API key utility
  const copyKeyToClipboard = (keyId: string, value: string) => {
    if (!value) return;
    navigator.clipboard.writeText(value);
    setCopiedKey(keyId);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Visibility toggle
  const toggleKeyVisibility = (keyId: string) => {
    setVisibleKeys((prev) => ({ ...prev, [keyId]: !prev[keyId] }));
  };

  // Destructive executions
  const executeDestructiveAction = () => {
    if (!confirmAction.type) return;

    startTransition(() => {
      if (confirmAction.type === "clear_cache") {
        localStorage.removeItem("gs-search-history");
        localStorage.removeItem("gs-report-history");
        localStorage.removeItem("gs-report-overrides");
        setCachedSessionsCount(0);
        setCachedReportsCount(0);
      } else if (confirmAction.type === "reset_branding") {
        localStorage.setItem("gs-branding", JSON.stringify(DEFAULT_BRANDING));
        setBrandingState(DEFAULT_BRANDING);
      } else if (confirmAction.type === "reset_prefs") {
        localStorage.setItem("gs-preferences", JSON.stringify(DEFAULT_PREFERENCES));
        setPrefsState(DEFAULT_PREFERENCES);
        localStorage.setItem("gs-settings", JSON.stringify(DEFAULT_PROFILE));
        setProfileState(DEFAULT_PROFILE);
      }
      recalculateStats();
      setConfirmAction({ type: null, title: "", message: "" });
    });
  };

  // Nav sidebar list mapping
  const navItems = [
    { id: "profile", label: "User Profile", icon: User },
    { id: "branding", label: "Branding", icon: ImageIcon },
    { id: "apikeys", label: "API Credentials", icon: KeyRound },
    { id: "theme", label: "Visual Theme", icon: Paintbrush },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "preferences", label: "Preferences", icon: Sliders },
    { id: "security", label: "Cache & Security", icon: ShieldAlert },
    { id: "about", label: "About Platform", icon: Info },
  ] as const;

  return (
    <PageContainer>
      <SectionHeader
        title="Settings & Workspace Preferences"
        description="Configure your consultant profile, white-labeled proposals settings, API key credentials, and localized templates."
      />

      <div className="flex flex-col lg:flex-row gap-[var(--space-6)] items-start mt-[var(--space-2)]">
        {/* Settings Navigation Sidebars (Tab pills) */}
        <aside className="w-full lg:w-64 bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-[var(--radius-lg)] p-1.5 shrink-0 flex flex-row lg:flex-col overflow-x-auto lg:overflow-visible gap-0.5 select-none no-print">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                className={`
                  flex items-center gap-2.5 px-3 py-2 text-[0.8125rem] font-semibold rounded-[var(--radius-md)] shrink-0 cursor-pointer whitespace-nowrap lg:w-full
                  transition-all duration-[var(--duration-fast)]
                  ${
                    activeSection === item.id
                      ? "bg-[var(--color-primary)] text-[var(--color-primary-foreground)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            );
          })}
        </aside>

        {/* Settings Detail Panels Content Area */}
        <div className="flex-1 w-full max-w-3xl">
          <Card className="p-[var(--space-5)]">
            {/* 1. USER PROFILE SECTION */}
            {activeSection === "profile" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">Consultant Profile</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Customize your agency profile defaults for diagnostic reviews and report cover pages.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-3)] pt-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Display Name</label>
                    <input
                      type="text"
                      value={profile.displayName}
                      onChange={(e) => handleProfileChange({ displayName: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Agency Name</label>
                    <input
                      type="text"
                      value={profile.agencyName}
                      onChange={(e) => handleProfileChange({ agencyName: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Consultant Title</label>
                    <input
                      type="text"
                      value={profile.consultantName}
                      onChange={(e) => handleProfileChange({ consultantName: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Contact Email</label>
                    <input
                      type="email"
                      value={profile.email}
                      onChange={(e) => handleProfileChange({ email: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Contact Phone</label>
                    <input
                      type="text"
                      value={profile.phone}
                      onChange={(e) => handleProfileChange({ phone: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Agency Website</label>
                    <input
                      type="text"
                      value={profile.website}
                      onChange={(e) => handleProfileChange({ website: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">LinkedIn URL</label>
                    <input
                      type="text"
                      value={profile.linkedin}
                      onChange={(e) => handleProfileChange({ linkedin: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Local Time Zone</label>
                    <select
                      value={profile.timezone}
                      onChange={(e) => handleProfileChange({ timezone: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] cursor-pointer text-[var(--text-primary)]"
                    >
                      <option value="UTC">UTC / GMT</option>
                      <option value="EST">Eastern Time (EST)</option>
                      <option value="CST">Central Time (CST)</option>
                      <option value="PST">Pacific Time (PST)</option>
                    </select>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Default Currency</label>
                    <input
                      type="text"
                      value={profile.defaultCurrency}
                      onChange={(e) => handleProfileChange({ defaultCurrency: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Preferred Language</label>
                    <input
                      type="text"
                      value={profile.defaultLanguage}
                      onChange={(e) => handleProfileChange({ defaultLanguage: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 2. BRANDING SECTION */}
            {activeSection === "branding" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">Proposal Branding</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Adjust custom logo assets and accent cover page variables applied across growth proposals.</p>
                </div>

                <div className="flex flex-col gap-[var(--space-3)] pt-2">
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Default Agency Logo</label>
                    <div className="flex items-center gap-[var(--space-2)]">
                      {branding.agencyLogo ? (
                        <div className="relative w-12 h-12 bg-white border border-[var(--bg-border)] rounded overflow-hidden flex items-center justify-center p-1 shrink-0">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={branding.agencyLogo} alt="Logo" className="max-h-full max-w-full object-contain" />
                        </div>
                      ) : (
                        <div className="w-12 h-12 bg-[var(--bg-base)] border border-[var(--bg-border)] rounded flex items-center justify-center text-[var(--text-muted)] shrink-0 font-bold text-[0.75rem]">
                          LOGO
                        </div>
                      )}
                      <label className="flex-1 flex flex-col items-center justify-center h-12 border border-dashed border-[var(--bg-border)] rounded hover:bg-[var(--bg-hover)] cursor-pointer select-none">
                        <span className="text-[0.75rem] font-bold text-[var(--text-secondary)]">Choose Logo</span>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              const r = new FileReader();
                              r.onload = (ev) => {
                                if (ev.target?.result) {
                                  handleBrandingChange({ agencyLogo: ev.target.result as string });
                                }
                              };
                              r.readAsDataURL(file);
                            }
                          }}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Accent Print Hex Color</label>
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
                        className="flex-1 h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none font-mono"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <label htmlFor="cover-page-defaults-switch" className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Include Cover Page by Default</label>
                    <input
                      id="cover-page-defaults-switch"
                      type="checkbox"
                      checked={branding.includeCoverPage}
                      onChange={(e) => handleBrandingChange({ includeCoverPage: e.target.checked })}
                      className="accent-[var(--color-primary)] w-4 h-4 cursor-pointer"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Disclaimer Text</label>
                    <textarea
                      value={branding.disclaimer}
                      onChange={(e) => handleBrandingChange({ disclaimer: e.target.value })}
                      rows={3}
                      className="w-full p-2 text-[0.75rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none text-[var(--text-muted)] leading-relaxed"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* 3. API CREDENTIALS MODULE */}
            {activeSection === "apikeys" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">Secure API Credentials</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Tokens and integration keys are stored strictly in-browser within local namespaces. Credentials never leave the device.</p>
                </div>

                <div className="flex flex-col gap-[var(--space-3)] pt-2">
                  {/* Google Maps Key */}
                  <div className="flex flex-col gap-1.5 p-3.5 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded-[var(--radius-md)]">
                    <div className="flex items-center justify-between">
                      <span className="text-[0.8125rem] font-bold text-[var(--text-primary)]">Google Maps API Key</span>
                      <Badge className={apiKeys.googleMapsKey ? "bg-[var(--color-success-muted)] text-[var(--color-success)]" : "bg-[var(--color-warning-muted)] text-[var(--color-warning)]"}>
                        {apiKeys.googleMapsKey ? "Configured" : "Unconfigured"}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="relative flex-1">
                        <input
                          type={visibleKeys.maps ? "text" : "password"}
                          value={apiKeys.googleMapsKey}
                          onChange={(e) => handleApiKeysChange({ googleMapsKey: e.target.value })}
                          placeholder="AIzaSy..."
                          className="w-full h-8 px-3 pr-8 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none font-mono"
                        />
                        <button
                          onClick={() => toggleKeyVisibility("maps")}
                          className="absolute right-2.5 top-2.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                        >
                          {visibleKeys.maps ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => copyKeyToClipboard("maps", apiKeys.googleMapsKey)}
                        disabled={!apiKeys.googleMapsKey}
                        className="h-8"
                      >
                        {copiedKey === "maps" ? <Check className="w-3.5 h-3.5 text-[var(--color-success)]" /> : <Copy className="w-3.5 h-3.5" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleApiKeysChange({ googleMapsKey: "" })}
                        disabled={!apiKeys.googleMapsKey}
                        className="h-8 text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
                      >
                        Clear
                      </Button>
                    </div>
                  </div>

                  {/* Search Provider Key */}
                  <div className="flex flex-col gap-1.5 p-3.5 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded-[var(--radius-md)]">
                    <div className="flex items-center justify-between">
                      <span className="text-[0.8125rem] font-bold text-[var(--text-primary)]">Search Provider Engine API Key</span>
                      <Badge className={apiKeys.customSearchKey ? "bg-[var(--color-success-muted)] text-[var(--color-success)]" : "bg-[var(--color-warning-muted)] text-[var(--color-warning)]"}>
                        {apiKeys.customSearchKey ? "Configured" : "Unconfigured"}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="relative flex-1">
                        <input
                          type={visibleKeys.search ? "text" : "password"}
                          value={apiKeys.customSearchKey}
                          onChange={(e) => handleApiKeysChange({ customSearchKey: e.target.value })}
                          placeholder="Search engine token..."
                          className="w-full h-8 px-3 pr-8 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none font-mono"
                        />
                        <button
                          onClick={() => toggleKeyVisibility("search")}
                          className="absolute right-2.5 top-2.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                        >
                          {visibleKeys.search ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => copyKeyToClipboard("search", apiKeys.customSearchKey)}
                        disabled={!apiKeys.customSearchKey}
                        className="h-8"
                      >
                        {copiedKey === "search" ? <Check className="w-3.5 h-3.5 text-[var(--color-success)]" /> : <Copy className="w-3.5 h-3.5" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleApiKeysChange({ customSearchKey: "" })}
                        disabled={!apiKeys.customSearchKey}
                        className="h-8 text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
                      >
                        Clear
                      </Button>
                    </div>
                  </div>

                  {/* LLM Key */}
                  <div className="flex flex-col gap-1.5 p-3.5 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded-[var(--radius-md)]">
                    <div className="flex items-center justify-between">
                      <span className="text-[0.8125rem] font-bold text-[var(--text-primary)]">LLM Provider API Key (Gemini Enterprise)</span>
                      <Badge className={apiKeys.llmProviderKey ? "bg-[var(--color-success-muted)] text-[var(--color-success)]" : "bg-[var(--color-warning-muted)] text-[var(--color-warning)]"}>
                        {apiKeys.llmProviderKey ? "Configured" : "Unconfigured"}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-2">
                      <div className="relative flex-1">
                        <input
                          type={visibleKeys.llm ? "text" : "password"}
                          value={apiKeys.llmProviderKey}
                          onChange={(e) => handleApiKeysChange({ llmProviderKey: e.target.value })}
                          placeholder="sk-gemini-..."
                          className="w-full h-8 px-3 pr-8 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none font-mono"
                        />
                        <button
                          onClick={() => toggleKeyVisibility("llm")}
                          className="absolute right-2.5 top-2.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                        >
                          {visibleKeys.llm ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => copyKeyToClipboard("llm", apiKeys.llmProviderKey)}
                        disabled={!apiKeys.llmProviderKey}
                        className="h-8"
                      >
                        {copiedKey === "llm" ? <Check className="w-3.5 h-3.5 text-[var(--color-success)]" /> : <Copy className="w-3.5 h-3.5" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleApiKeysChange({ llmProviderKey: "" })}
                        disabled={!apiKeys.llmProviderKey}
                        className="h-8 text-[var(--color-error)] hover:bg-[var(--color-error-muted)]"
                      >
                        Clear
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 4. VISUAL THEME SELECTOR */}
            {activeSection === "theme" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">Visual Interface Theme</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Toggle interface styling colors between Light, Dark, or System Sync.</p>
                </div>

                <div className="grid grid-cols-3 gap-3 pt-4 select-none">
                  {(["light", "dark", "system"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => handleThemeChange(t)}
                      className={`
                        p-5 rounded-lg border flex flex-col items-center justify-center gap-2 cursor-pointer capitalize font-bold text-[0.875rem]
                        transition-all duration-[var(--duration-fast)]
                        ${
                          theme === t
                            ? "border-[var(--color-primary)] bg-[var(--bg-elevated)] text-[var(--text-primary)] shadow-[var(--focus-ring)]"
                            : "border-[var(--bg-border)] bg-[var(--bg-base)] text-[var(--text-secondary)] hover:border-[var(--text-muted)]"
                        }
                      `}
                    >
                      {t === "light" && <Sun className="w-5 h-5 text-amber-500" />}
                      {t === "dark" && <Moon className="w-5 h-5 text-indigo-400" />}
                      {t === "system" && <Sliders className="w-5 h-5 text-teal-400" />}
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 5. NOTIFICATIONS */}
            {activeSection === "notifications" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">System Alerts & Notifications</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Configure alerting channels for diagnostic runs and output reports.</p>
                </div>

                <div className="flex flex-col gap-[var(--space-3)] pt-2 select-none">
                  <div className="flex items-center justify-between py-1.5 border-b border-[var(--bg-border)]">
                    <div>
                      <span className="text-[0.8125rem] font-bold block text-[var(--text-primary)]">Desktop Notifications</span>
                      <span className="text-[0.6875rem] text-[var(--text-muted)]">Fire browser notifications on diagnostic completion events.</span>
                    </div>
                    <input type="checkbox" defaultChecked className="accent-[var(--color-primary)] w-4 h-4 cursor-pointer" />
                  </div>
                  <div className="flex items-center justify-between py-1.5 border-b border-[var(--bg-border)]">
                    <div>
                      <span className="text-[0.8125rem] font-bold block text-[var(--text-primary)]">Workflow Completion Sound</span>
                      <span className="text-[0.6875rem] text-[var(--text-muted)]">Play a sound notification when a background crawler ends.</span>
                    </div>
                    <input type="checkbox" defaultChecked className="accent-[var(--color-primary)] w-4 h-4 cursor-pointer" />
                  </div>
                  <div className="flex items-center justify-between py-1.5 border-b border-[var(--bg-border)]">
                    <div>
                      <span className="text-[0.8125rem] font-bold block text-[var(--text-primary)]">Email Summary Reports (Future SaaS)</span>
                      <span className="text-[0.6875rem] text-[var(--text-muted)]">Send diagnostic reports summary directly to your inbox.</span>
                    </div>
                    <input type="checkbox" disabled className="accent-[var(--color-primary)] w-4 h-4 cursor-not-allowed opacity-50" />
                  </div>
                </div>
              </div>
            )}

            {/* 6. APP PREFERENCES */}
            {activeSection === "preferences" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">Workspace Preferences</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Personalize default pagination bounds and opportunity thresholds.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-[var(--space-3)] pt-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Default Landing Route</label>
                    <select
                      value={prefs.defaultPage}
                      onChange={(e) => handlePrefsChange({ defaultPage: e.target.value })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none cursor-pointer text-[var(--text-primary)]"
                    >
                      <option value="/dashboard">Dashboard</option>
                      <option value="/discovery">Lead Discovery</option>
                      <option value="/sessions">Diagnostics Hub</option>
                      <option value="/reports">Proposals Dashboard</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Autosave Interval (Seconds)</label>
                    <input
                      type="number"
                      value={prefs.autosaveInterval}
                      onChange={(e) => handlePrefsChange({ autosaveInterval: parseInt(e.target.value, 10) })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Opportunity Threshold Score (Min)</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="50"
                        max="90"
                        value={prefs.defaultOpportunityThreshold}
                        onChange={(e) => handlePrefsChange({ defaultOpportunityThreshold: parseInt(e.target.value, 10) })}
                        className="flex-1 accent-[var(--color-primary)] cursor-pointer"
                      />
                      <span className="text-[0.8125rem] font-mono font-bold text-[var(--text-primary)]">
                        {prefs.defaultOpportunityThreshold}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[0.75rem] font-medium text-[var(--text-secondary)]">Default Page Size</label>
                    <select
                      value={prefs.defaultPageSize}
                      onChange={(e) => handlePrefsChange({ defaultPageSize: parseInt(e.target.value, 10) })}
                      className="w-full h-9 px-3 text-[0.8125rem] bg-[var(--bg-base)] border border-[var(--bg-border)] rounded focus:outline-none cursor-pointer text-[var(--text-primary)]"
                    >
                      <option value="5">5 items</option>
                      <option value="10">10 items</option>
                      <option value="25">25 items</option>
                      <option value="50">50 items</option>
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* 7. CACHE & SECURITY */}
            {activeSection === "security" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">Workspace Cache & Security</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Manage local browser cache consumption and execute cleanup commands.</p>
                </div>

                <div className="grid grid-cols-2 gap-3.5 pt-2">
                  <div className="p-3.5 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded-[var(--radius-md)]">
                    <span className="text-gray-400 font-semibold block uppercase text-[0.625rem]">Total Cache Size</span>
                    <span className="text-2xl font-black text-[var(--text-primary)] font-mono">
                      {(storageBytes / 1024).toFixed(2)} KB
                    </span>
                  </div>
                  <div className="p-3.5 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded-[var(--radius-md)]">
                    <span className="text-gray-400 font-semibold block uppercase text-[0.625rem]">Cached Sessions</span>
                    <span className="text-2xl font-black text-[var(--text-primary)] font-mono">
                      {cachedSessionsCount}
                    </span>
                  </div>
                  <div className="p-3.5 bg-[var(--bg-elevated)] border border-[var(--bg-border)] rounded-[var(--radius-md)] grid-span-2">
                    <span className="text-gray-400 font-semibold block uppercase text-[0.625rem]">Customized Reports</span>
                    <span className="text-2xl font-black text-[var(--text-primary)] font-mono">
                      {cachedReportsCount}
                    </span>
                  </div>
                </div>

                <div className="flex flex-col gap-2 mt-4 pt-4 border-t border-[var(--bg-border)]">
                  <h4 className="text-[0.8125rem] font-bold text-[var(--text-primary)]">Cleanup Operations</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        setConfirmAction({
                          type: "reset_branding",
                          title: "Reset Proposal Branding?",
                          message: "This will revert your customized agency logos, disclaimers, and accent colors back to system defaults. This action cannot be undone.",
                        })
                      }
                      className="gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Reset Branding
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        setConfirmAction({
                          type: "reset_prefs",
                          title: "Reset Preferences & Profile?",
                          message: "This will restore defaults for default currency, threshold scores, local timezones, and page size filters. This action cannot be undone.",
                        })
                      }
                      className="gap-1.5"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Reset Defaults
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() =>
                        setConfirmAction({
                          type: "clear_cache",
                          title: "Clear Diagnostic Sessions Cache?",
                          message: "This will permanently purge all local diagnostic search histories, duplicated reports, and customized overrides. You will need to re-query sessions. This action cannot be undone.",
                        })
                      }
                      className="text-[var(--color-error)] hover:bg-[var(--color-error-muted)] gap-1.5"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Clear Cache
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* 8. ABOUT PLATFORM */}
            {activeSection === "about" && (
              <div className="flex flex-col gap-[var(--space-4)]">
                <div>
                  <h3 className="text-[1rem] font-bold text-[var(--text-primary)]">About GrowthScout AI</h3>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-0.5">Product specifications, documentation directories, and licensing frameworks.</p>
                </div>

                <div className="flex flex-col gap-1 pt-2">
                  <div className="flex justify-between py-2 border-b border-[var(--bg-border)] text-[0.8125rem]">
                    <span className="text-[var(--text-secondary)]">Platform Version</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">1.0.0-rc1</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-[var(--bg-border)] text-[0.8125rem]">
                    <span className="text-[var(--text-secondary)]">Frontend Target</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">Next.js 16 (Turbopack)</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-[var(--bg-border)] text-[0.8125rem]">
                    <span className="text-[var(--text-secondary)]">Environment Mode</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">Production Operations</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-[var(--bg-border)] text-[0.8125rem]">
                    <span className="text-[var(--text-secondary)]">Licensing Type</span>
                    <span className="font-mono font-bold text-[var(--text-primary)]">Commercial Enterprise</span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-[var(--bg-border)]">
                  <h4 className="text-[0.8125rem] font-bold text-[var(--text-primary)]">Reference Links</h4>
                  <div className="flex gap-[var(--space-4)] mt-2">
                    <a
                      href="https://google.github.io/adk"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[0.75rem] text-[var(--color-primary)] hover:underline flex items-center gap-1 font-semibold"
                    >
                      Google ADK Documentation <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Confirmation Dialog Modal overlay */}
      {confirmAction.type && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-[var(--space-4)] z-50 no-print">
          <div className="bg-[var(--bg-surface)] border border-[var(--bg-border)] rounded-[var(--radius-lg)] p-[var(--space-5)] max-w-md w-full shadow-[var(--shadow-high)]">
            <h4 className="text-[1rem] font-bold text-[var(--text-primary)] flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-[var(--color-error)]" />
              {confirmAction.title}
            </h4>
            <p className="text-[0.8125rem] text-[var(--text-secondary)] mt-[var(--space-3)] leading-normal">
              {confirmAction.message}
            </p>
            <div className="flex items-center justify-end gap-[var(--space-2)] mt-[var(--space-5)]">
              <Button
                variant="secondary"
                onClick={() => setConfirmAction({ type: null, title: "", message: "" })}
                disabled={isPending}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={executeDestructiveAction}
                disabled={isPending}
                className="bg-[var(--color-error)] text-[var(--color-primary-foreground)] hover:bg-[var(--color-error-muted)]"
              >
                {isPending ? "Clearing..." : "Yes, Confirm"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
