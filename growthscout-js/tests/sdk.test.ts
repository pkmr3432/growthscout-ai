// growthscout-js/tests/sdk.test.ts
/**
 * Unit tests verifying behavior and error mapping for the TypeScript client.
 */

import {
  GrowthScout,
  GrowthScoutAuthenticationError,
  GrowthScoutValidationError,
  GrowthScoutRateLimitError,
  GrowthScoutLockConflictError,
  GrowthScoutPayloadTooLargeError,
  GrowthScoutNetworkError
} from "../src";

describe("TypeScript SDK Validation", () => {
  let mockFetch: any;

  beforeEach(() => {
    mockFetch = jest.fn();
    (global as any).fetch = mockFetch;
  });

  it("should throw AuthenticationError if API key is missing or empty", () => {
    expect(() => new GrowthScout({ apiKey: "" })).toThrow(GrowthScoutAuthenticationError);
    expect(() => new GrowthScout({ apiKey: null as any })).toThrow(GrowthScoutAuthenticationError);
  });

  it("should inject X-API-Key header to every request", async () => {
    const client = new GrowthScout({ apiKey: "test_key_123" });
    
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ session_id: "sess_123" })
    });

    await client.sessions.get("sess_123");
    
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers["X-API-Key"]).toBe("test_key_123");
  });

  it("should map HTTP status codes to corresponding custom errors", async () => {
    const client = new GrowthScout({ apiKey: "test_key" });

    const mappings = [
      { status: 400, expected: GrowthScoutValidationError },
      { status: 401, expected: GrowthScoutAuthenticationError },
      { status: 403, expected: GrowthScoutAuthenticationError },
      { status: 404, expected: GrowthScoutValidationError },
      { status: 409, expected: GrowthScoutLockConflictError },
      { status: 413, expected: GrowthScoutPayloadTooLargeError },
      { status: 429, expected: GrowthScoutRateLimitError }
    ];

    for (const item of mappings) {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: item.status,
        text: async () => JSON.stringify({ error: { message: "Failed", code: "FAIL" } })
      });

      await expect(client.sessions.get("sess_123")).rejects.toThrow(item.expected);
    }
  });

  it("should retry on transient failures and succeed", async () => {
    const client = new GrowthScout({ apiKey: "test_key", maxRetries: 2 });
    
    // Simulate two failures, then success
    mockFetch
      .mockRejectedValueOnce(new Error("Timeout/Connection Error"))
      .mockRejectedValueOnce(new Error("Timeout/Connection Error"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: "sess_123" })
      });

    // Mock setTimeout to execute immediately during retry sleep
    const originalSetTimeout = global.setTimeout;
    (global as any).setTimeout = (cb: any) => cb();

    const session = await client.sessions.get("sess_123");
    expect(session.session_id).toBe("sess_123");
    expect(mockFetch).toHaveBeenCalledTimes(3);

    (global as any).setTimeout = originalSetTimeout;
  });

  it("should fail-fast on non-transient validation/auth errors", async () => {
    const client = new GrowthScout({ apiKey: "test_key", maxRetries: 2 });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      text: async () => JSON.stringify({ error: { message: "Bad parameters" } })
    });

    await expect(client.sessions.create("niche", "loc")).rejects.toThrow(GrowthScoutValidationError);
    expect(mockFetch).toHaveBeenCalledTimes(1); // Fails fast, no retry
  });

  it("should propagate pagination query parameters correctly", async () => {
    const client = new GrowthScout({ apiKey: "test_key" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => []
    });

    await client.sessions.listSessions(10, 20);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=20");
  });
});
