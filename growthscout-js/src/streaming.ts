// growthscout-js/src/streaming.ts
/**
 * SSE Event Stream consumer for JavaScript/TypeScript SDK.
 */

import { EventEnvelope } from "./models.js";
import { GrowthScoutError, GrowthScoutNetworkError } from "./exceptions.js";

export class EventStream {
  private client: any;
  private sessionId: string;
  private lastEventId: number | null = null;
  private active: boolean = true;
  private listeners: Record<string, ((data: any) => void)[]> = {};

  constructor(client: any, sessionId: string) {
    this.client = client;
    this.sessionId = sessionId;
  }

  /**
   * Registers a callback listener for specific event types.
   */
  public on(event: string, callback: (data: any) => void): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  /**
   * Closes the active stream connection.
   */
  public close(): void {
    this.active = false;
  }

  /**
   * Starts listening to the stream, handling chunks and reconnection automatically.
   */
  public async listen(): Promise<void> {
    const url = `${this.client.baseUrl}/api/v1/sessions/${this.sessionId}/stream`;
    let attempt = 0;

    while (this.active) {
      try {
        const headers = this.client.getHeaders();
        if (this.lastEventId !== null) {
          headers["Last-Event-ID"] = String(this.lastEventId);
        }

        const response = await fetch(url, {
          method: "GET",
          headers: headers,
        });

        if (!response.ok) {
          await this.client.handleStatusError(response.status, await response.text());
        }

        attempt = 0;
        const reader = response.body?.getReader();
        if (!reader) {
          throw new GrowthScoutError("Failed to obtain response stream reader.");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (this.active) {
          const { done, value } = await reader.read();
          if (done || !this.active) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          while (buffer.includes("\n\n")) {
            const index = buffer.indexOf("\n\n");
            const block = buffer.slice(0, index);
            buffer = buffer.slice(index + 2);

            const envelope = this.parseBlock(block);
            if (envelope) {
              this.lastEventId = envelope.event_id;
              this.emit(envelope.event_type, envelope);
              this.emit("message", envelope);

              if (envelope.event_type === "stream_ended") {
                this.active = false;
                return;
              }
            }
          }
        }
      } catch (err: any) {
        if (!this.active) break;
        attempt++;
        if (attempt > this.client.maxRetries) {
          const networkErr = new GrowthScoutNetworkError(`Reconnection failed after ${attempt} attempts: ${err.message}`);
          this.emit("error", networkErr);
          throw networkErr;
        }

        const sleepTime = Math.min(10000, 1000 * Math.pow(2, attempt));
        this.emit("warning", `Connection dropped. Retrying in ${sleepTime / 1000}s...`);
        await new Promise((resolve) => setTimeout(resolve, sleepTime));
      }
    }
  }

  private emit(event: string, data: any): void {
    const list = this.listeners[event] || [];
    for (const callback of list) {
      try {
        callback(data);
      } catch (err) {
        console.error("Error in stream callback", err);
      }
    }
  }

  private parseBlock(block: string): EventEnvelope | null {
    const lines = block.trim().split("\n");
    let eventId: number | null = null;
    let eventType: string | null = null;
    let data: any = null;

    for (const line of lines) {
      if (line.startsWith("id:")) {
        const val = parseInt(line.slice(3).trim(), 10);
        if (!isNaN(val)) eventId = val;
      } else if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        try {
          data = JSON.parse(line.slice(5).trim());
        } catch {
          // ignore
        }
      }
    }

    if (eventId !== null && eventType && data !== null) {
      return {
        event_id: eventId,
        event_type: eventType,
        session_id: data.session_id || this.sessionId,
        timestamp: data.timestamp || new Date().toISOString(),
        data: data.data || {},
        correlation_id: data.correlation_id,
      };
    }
    return null;
  }
}
