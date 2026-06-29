// growthscout-js/src/client.ts
/**
 * Core client wrapper for the GrowthScout AI TS/JS SDK.
 */
import { GrowthScoutError, GrowthScoutNetworkError, GrowthScoutAuthenticationError, GrowthScoutValidationError, GrowthScoutRateLimitError, GrowthScoutLockConflictError, GrowthScoutPayloadTooLargeError } from "./exceptions.js";
import { EventStream } from "./streaming.js";
export class GrowthScout {
    apiKey;
    baseUrl;
    timeout;
    maxRetries;
    sessions;
    constructor(config) {
        if (!config.apiKey || typeof config.apiKey !== "string") {
            throw new GrowthScoutAuthenticationError("Invalid API key. Must be a non-empty string.");
        }
        this.apiKey = config.apiKey;
        this.baseUrl = (config.baseUrl || "http://localhost:8000").replace(/\/$/, "");
        this.timeout = config.timeout || 30000;
        this.maxRetries = config.maxRetries || 3;
        this.sessions = new SessionsResource(this);
    }
    getHeaders() {
        return {
            "X-API-Key": this.apiKey,
            "Content-Type": "application/json",
            "Accept": "application/json"
        };
    }
    /**
     * Executes HTTP requests with transient retry middleware.
     */
    async request(method, path, bodyData, queryParams) {
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
            }
            catch (err) {
                if (err instanceof GrowthScoutError &&
                    !(err instanceof GrowthScoutNetworkError) &&
                    !(err instanceof GrowthScoutRateLimitError)) {
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
    async handleStatusError(status, text) {
        let message = `API Error status ${status}: ${text}`;
        try {
            const json = JSON.parse(text);
            if (json.error && json.error.message) {
                message = json.error.message;
            }
        }
        catch {
            // ignore
        }
        if (status === 400) {
            throw new GrowthScoutValidationError(message);
        }
        else if (status === 401 || status === 403) {
            throw new GrowthScoutAuthenticationError(message);
        }
        else if (status === 404) {
            throw new GrowthScoutValidationError(`Not Found: ${message}`);
        }
        else if (status === 409) {
            throw new GrowthScoutLockConflictError(message);
        }
        else if (status === 413) {
            throw new GrowthScoutPayloadTooLargeError(message);
        }
        else if (status === 429) {
            throw new GrowthScoutRateLimitError(message, 1.0);
        }
        else {
            throw new GrowthScoutError(message);
        }
    }
}
class SessionsResource {
    client;
    constructor(client) {
        this.client = client;
    }
    async create(niche, location, maxLeads = 5) {
        const payload = { niche, location, max_leads: maxLeads };
        return await this.client.request("POST", "/api/v1/sessions", payload);
    }
    async get(sessionId) {
        return await this.client.request("GET", `/api/v1/sessions/${sessionId}`);
    }
    async run(sessionId) {
        return await this.client.request("POST", `/api/v1/sessions/${sessionId}/run`);
    }
    async submitFeedback(sessionId, approved, feedbackNotes, adjustedData) {
        const payload = { approved, feedback_notes: feedbackNotes, adjusted_data: adjustedData };
        return await this.client.request("POST", `/api/v1/sessions/${sessionId}/feedback`, payload);
    }
    async cancel(sessionId) {
        return await this.client.request("POST", `/api/v1/sessions/${sessionId}/cancel`);
    }
    stream(sessionId) {
        return new EventStream(this.client, sessionId);
    }
    async listSessions(limit = 20, offset = 0) {
        const params = { limit, offset };
        const docs = await this.client.request("GET", "/api/v1/sessions", undefined, params);
        if (Array.isArray(docs)) {
            return docs;
        }
        else if (docs && Array.isArray(docs.sessions)) {
            return docs.sessions;
        }
        return [];
    }
}
//# sourceMappingURL=client.js.map