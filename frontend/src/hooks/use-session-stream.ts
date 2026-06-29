"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { getApiConfig, type SSEEventEnvelope } from "@/utils/api-client";

interface UseSessionStreamProps {
  sessionId: string;
  onEvent: (event: SSEEventEnvelope) => void;
  onError: (error: Error) => void;
  enabled: boolean;
}

export function useSessionStream({ sessionId, onEvent, onError, enabled }: UseSessionStreamProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  const startStream = useCallback(async () => {
    if (!enabled || !sessionId) return;
    
    stopStream();
    setIsConnecting(true);

    const { baseUrl, apiKey } = getApiConfig();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`${baseUrl}/api/v1/sessions/${sessionId}/stream`, {
        headers: {
          "X-API-Key": apiKey,
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`SSE stream returned error status: ${response.statusText}`);
      }

      setIsConnecting(false);
      setIsConnected(true);

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("ReadableStream not supported on response body.");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            const rawData = trimmed.slice(6).trim();
            try {
              const envelope: SSEEventEnvelope = JSON.parse(rawData);
              onEvent(envelope);
            } catch (e) {
              console.warn("Failed to parse event JSON data chunk:", e);
            }
          }
        }
      }
    } catch (err: unknown) {
      const isAbort = err instanceof Error && err.name === "AbortError";
      if (isAbort) {
        // Safe cancellation
        return;
      }
      setIsConnected(false);
      setIsConnecting(false);
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  }, [sessionId, enabled, onEvent, onError, stopStream]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (enabled) {
        startStream();
      } else {
        stopStream();
      }
    }, 0);
    return () => {
      clearTimeout(timer);
      stopStream();
    };
  }, [enabled, startStream, stopStream]);

  return {
    isConnected,
    isConnecting,
    reconnect: startStream,
    disconnect: stopStream,
  };
}
