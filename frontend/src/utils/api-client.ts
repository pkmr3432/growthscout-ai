/* ──────────────────────────────────────────────────
   GrowthScout AI — API Client Helper
   Consumes existing v1 FastAPI Gateway endpoints.
   ────────────────────────────────────────────────── */

export interface SessionResponse {
  session_id: string;
  workflow_id: string;
  current_state: string;
  niche: string;
  location: string;
  max_leads: number;
  revision_count: number;
  created_at: string;
  updated_at: string;
  status: string;
  context_data?: Record<string, unknown>;
}

export interface SessionCreateRequest {
  niche: string;
  location: string;
  max_leads: number;
}

export interface LeadProfile {
  id: string;
  name: string;
  niche: string;
  location: string;
  website: string;
  phone: string;
  address: string;
  opportunity_score: number;
  issues: string[];
  status: "discovered" | "audited";
}

const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_API_KEY = "gs_dev_key_12345";

export function getApiConfig() {
  if (typeof window === "undefined") {
    return { baseUrl: DEFAULT_BASE_URL, apiKey: DEFAULT_API_KEY };
  }
  const baseUrl = localStorage.getItem("gs-api-url") ?? DEFAULT_BASE_URL;
  const apiKey = localStorage.getItem("gs-api-key") ?? DEFAULT_API_KEY;
  return { baseUrl, apiKey };
}

export async function createSession(params: SessionCreateRequest): Promise<SessionResponse> {
  const { baseUrl, apiKey } = getApiConfig();
  const res = await fetch(`${baseUrl}/api/v1/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    let errMsg = `Failed to create session: ${res.statusText}`;
    try {
      const errData = await res.json();
      errMsg = errData?.error?.message ?? errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  return res.json();
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const { baseUrl, apiKey } = getApiConfig();
  const res = await fetch(`${baseUrl}/api/v1/sessions/${sessionId}`, {
    method: "GET",
    headers: {
      "X-API-Key": apiKey,
    },
  });

  if (!res.ok) {
    throw new Error(`Failed to load session details: ${res.statusText}`);
  }

  return res.json();
}

// Generate deterministic local business lead listings based on search parameters
export function generateMockLeads(niche: string, location: string, count: number): LeadProfile[] {
  const names = [
    "Summit",
    "Apex",
    "Choice",
    "Premier",
    "Vanguard",
    "Metro",
    "Elite",
    "Progressive",
    "Beacon",
    "North Star",
  ];
  const types = ["Care", "Associates", "Solutions", "Services", "Partners", "Hub", "Group", "Collective"];

  return Array.from({ length: count }).map((_, i) => {
    const businessName = `${names[i % names.length]} ${niche.charAt(0).toUpperCase() + niche.slice(1)} ${types[i % types.length]}`;
    const domainName = `${businessName.toLowerCase().replace(/[^a-z0-9]/g, "")}.com`;
    const score = 40 + (i * 13) % 55; // 40 - 95 score scale

    const possibleIssues = [
      "Missing robots.txt",
      "No OpenGraph metadata tags",
      "Failing P95 mobile load latency",
      "Missing Google Analytics tracker",
      "Unsecured HTTP connection",
      "No structured schema markup",
    ];
    // Select deterministic subset of issues based on index
    const issuesCount = 1 + (i % 3);
    const issues = Array.from({ length: issuesCount }).map((_, idx) => possibleIssues[(i + idx) % possibleIssues.length]);

    return {
      id: `lead_${sessionIdHash(businessName + i)}`,
      name: businessName,
      niche,
      location,
      website: i % 4 === 0 ? "" : `https://www.${domainName}`,
      phone: `(555) 019-${1000 + i}`,
      address: `${100 + i * 15} Main St, ${location}`,
      opportunity_score: score,
      issues,
      status: "discovered",
    };
  });
}

function sessionIdHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(16).slice(0, 8);
}

export async function runSession(sessionId: string): Promise<SessionResponse> {
  const { baseUrl, apiKey } = getApiConfig();
  const res = await fetch(`${baseUrl}/api/v1/sessions/${sessionId}/run`, {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
    },
  });

  if (!res.ok) {
    let errMsg = `Failed to run session: ${res.statusText}`;
    try {
      const errData = await res.json();
      errMsg = errData?.error?.message ?? errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  return res.json();
}

export async function cancelSession(sessionId: string): Promise<SessionResponse> {
  const { baseUrl, apiKey } = getApiConfig();
  const res = await fetch(`${baseUrl}/api/v1/sessions/${sessionId}/cancel`, {
    method: "POST",
    headers: {
      "X-API-Key": apiKey,
    },
  });

  if (!res.ok) {
    let errMsg = `Failed to cancel session: ${res.statusText}`;
    try {
      const errData = await res.json();
      errMsg = errData?.error?.message ?? errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  return res.json();
}

export interface FeedbackData {
  approved: boolean;
  feedback_notes?: string;
  adjusted_data?: Record<string, unknown>;
}

export async function submitFeedback(sessionId: string, data: FeedbackData): Promise<SessionResponse> {
  const { baseUrl, apiKey } = getApiConfig();
  const res = await fetch(`${baseUrl}/api/v1/sessions/${sessionId}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    let errMsg = `Failed to submit feedback: ${res.statusText}`;
    try {
      const errData = await res.json();
      errMsg = errData?.error?.message ?? errMsg;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  return res.json();
}

export interface SSEEventEnvelope {
  event_id: number;
  event_type: string;
  session_id: string;
  timestamp: string;
  data: Record<string, unknown>;
  correlation_id?: string;
}

