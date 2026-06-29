// growthscout-js/src/client.ts
/**
 * Core client wrapper for the GrowthScout AI TS/JS SDK.
 */

import { SessionResponse, SessionCreateRequest, FeedbackSubmitRequest } from "./models.js";
import {
  GrowthScoutError,
  GrowthScoutNetworkError,
  GrowthScoutAuthenticationError,
  GrowthScoutValidationError,
  GrowthScoutRateLimitError,
  GrowthScoutLockConflictError,
  GrowthScoutPayloadTooLargeError
} from "./exceptions.js";
import { EventStream } from "./streaming.js";

export interface ClientConfig {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
}

export class GrowthScout {
  public apiKey: string;
  public baseUrl: string;
  public timeout: number;
  public maxRetries: number;
  public sessions: SessionsResource;

  constructor(config: ClientConfig) {
    if (!config.apiKey || typeof config.apiKey !== "string") {
      throw new GrowthScoutAuthenticationError("Invalid API key. Must be a non-empty string.");
    }

    this.apiKey = config.apiKey;
    this.baseUrl = (config.baseUrl || "http://localhost:8000").replace(/\/$/, "");
    this.timeout = config.timeout || 30000;
    this.maxRetries = config.maxRetries || 3;
    this.sessions = new SessionsResource(this);
  }

  public getHeaders(): Record<string, string> {
    return {
      "X-API-Key": this.apiKey,
      "Content-Type": "application/json",
      "Accept": "application/json"
    };
  }

  /**
   * Executes HTTP requests with transient retry middleware.
   */
  public async request(
    method: string,
    path: string,
    bodyData?: any,
    queryParams?: Record<string, any>
  ): Promise<any> {
    let url = `${this.baseUrl}${path}`;
    if (queryParams) {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(queryParams)) {
        q.append(k, String(v));
      }
      url += `?${q.toString()}`;
    }

    let attempt = 0;

    while (true) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          method: method,
          headers: this.getHeaders(),
          body: bodyData ? JSON.stringify(bodyData) : undefined,
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          return await response.json();
        }

        await this.handleStatusError(response.status, await response.text());
      } catch (err: any) {
        if (
          err instanceof GrowthScoutError &&
          !(err instanceof GrowthScoutNetworkError) &&
          !(err instanceof GrowthScoutRateLimitError)
        ) {
          throw err;
        }

        attempt++;
        if (attempt > this.maxRetries) {
          throw new GrowthScoutNetworkError(`Network connection request failed after ${attempt} attempts: ${err.message}`);
        }

        // Exponential backoff with jitter
        const sleepTime = Math.min(10000, 1000 * Math.pow(2, attempt)) + Math.random() * 500;
        await new Promise((resolve) => setTimeout(resolve, sleepTime));
      }
    }
  }

  public async handleStatusError(status: number, text: string): Promise<void> {
    let message = `API Error status ${status}: ${text}`;
    try {
      const json = JSON.parse(text);
      if (json.error && json.error.message) {
        message = json.error.message;
      }
    } catch {
      // ignore
    }

    if (status === 400) {
      throw new GrowthScoutValidationError(message);
    } else if (status === 401 || status === 403) {
      throw new GrowthScoutAuthenticationError(message);
    } else if (status === 404) {
      throw new GrowthScoutValidationError(`Not Found: ${message}`);
    } else if (status === 409) {
      throw new GrowthScoutLockConflictError(message);
    } else if (status === 413) {
      throw new GrowthScoutPayloadTooLargeError(message);
    } else if (status === 429) {
      throw new GrowthScoutRateLimitError(message, 1.0);
    } else {
      throw new GrowthScoutError(message);
    }
  }
}

class SessionsResource {
  private client: GrowthScout;

  constructor(client: GrowthScout) {
    this.client = client;
  }

  public async create(niche: string, location: string, maxLeads: number = 5): Promise<SessionResponse> {
    const payload: SessionCreateRequest = { niche, location, max_leads: maxLeads };
    return await this.client.request("POST", "/api/v1/sessions", payload);
  }

  public async get(sessionId: string): Promise<SessionResponse> {
    return await this.client.request("GET", `/api/v1/sessions/${sessionId}`);
  }

  public async run(sessionId: string): Promise<SessionResponse> {
    return await this.client.request("POST", `/api/v1/sessions/${sessionId}/run`);
  }

  public async submitFeedback(
    sessionId: string,
    approved: boolean,
    feedbackNotes?: string,
    adjustedData?: Record<string, any>
  ): Promise<SessionResponse> {
    const payload: FeedbackSubmitRequest = { approved, feedback_notes: feedbackNotes, adjusted_data: adjustedData };
    return await this.client.request("POST", `/api/v1/sessions/${sessionId}/feedback`, payload);
  }

  public async cancel(sessionId: string): Promise<SessionResponse> {
    return await this.client.request("POST", `/api/v1/sessions/${sessionId}/cancel`);
  }

  public stream(sessionId: string): EventStream {
    return new EventStream(this.client, sessionId);
  }

  public async listSessions(limit: number = 20, offset: number = 0): Promise<SessionResponse[]> {
    const params = { limit, offset };
    const docs = await this.client.request("GET", "/api/v1/sessions", undefined, params);
    if (Array.isArray(docs)) {
      return docs;
    } else if (docs && Array.isArray(docs.sessions)) {
      return docs.sessions;
    }
    return [];
  }
}
