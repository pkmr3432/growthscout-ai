// growthscout-js/src/models.ts
/**
 * Type declarations and schema interfaces for the GrowthScout AI TS/JS SDK.
 */

export interface SessionCreateRequest {
  niche: string;
  location: string;
  max_leads?: number;
}

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
}

export interface FeedbackSubmitRequest {
  approved: boolean;
  feedback_notes?: string;
  adjusted_data?: Record<string, any>;
}

export interface EventEnvelope {
  event_id: number;
  event_type: string;
  session_id: string;
  timestamp: string;
  data: Record<string, any>;
  correlation_id?: string;
}
