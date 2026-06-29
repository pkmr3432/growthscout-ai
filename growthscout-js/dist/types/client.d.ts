/**
 * Core client wrapper for the GrowthScout AI TS/JS SDK.
 */
import { SessionResponse } from "./models.js";
import { EventStream } from "./streaming.js";
export interface ClientConfig {
    apiKey: string;
    baseUrl?: string;
    timeout?: number;
    maxRetries?: number;
}
export declare class GrowthScout {
    apiKey: string;
    baseUrl: string;
    timeout: number;
    maxRetries: number;
    sessions: SessionsResource;
    constructor(config: ClientConfig);
    getHeaders(): Record<string, string>;
    /**
     * Executes HTTP requests with transient retry middleware.
     */
    request(method: string, path: string, bodyData?: any, queryParams?: Record<string, any>): Promise<any>;
    handleStatusError(status: number, text: string): Promise<void>;
}
declare class SessionsResource {
    private client;
    constructor(client: GrowthScout);
    create(niche: string, location: string, maxLeads?: number): Promise<SessionResponse>;
    get(sessionId: string): Promise<SessionResponse>;
    run(sessionId: string): Promise<SessionResponse>;
    submitFeedback(sessionId: string, approved: boolean, feedbackNotes?: string, adjustedData?: Record<string, any>): Promise<SessionResponse>;
    cancel(sessionId: string): Promise<SessionResponse>;
    stream(sessionId: string): EventStream;
    listSessions(limit?: number, offset?: number): Promise<SessionResponse[]>;
}
export {};
