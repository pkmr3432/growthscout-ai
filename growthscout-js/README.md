# GrowthScout AI JavaScript/TypeScript SDK

The official JS/TS client library for interacting with the GrowthScout AI Platform. Compatible with ESM, CommonJS, browser and server-side runtimes.

---

## Installation

```bash
npm install growthscout-js
```

## Quick Start

```typescript
import { GrowthScout } from "growthscout-js";

async function main() {
  // Initialize client
  const client = new GrowthScout({
    apiKey: "gs_dev_key_12345",
    baseUrl: "http://localhost:8000"
  });

  // Create session
  const session = await client.sessions.create("dental clinic", "Miami, FL", 5);
  console.log(`Created Session ID: ${session.session_id}`);
}
main();
```

## Authentication

All requests require authentication via an API Key injected into the `X-API-Key` header:

```typescript
const client = new GrowthScout({ apiKey: "YOUR_API_KEY" });
```

## Real-Time SSE Streaming & Reconnection

The SDK supports consuming real-time execution steps through Server-Sent Events (SSE). Reconnection and event synchronization are handled automatically using `Last-Event-ID`:

```typescript
const stream = client.sessions.stream("sess_a1b2c3d4");

stream.on("step_completed", (envelope) => {
  console.log(`[Step Completed] State: ${envelope.data.new_state}`);
});

stream.on("error", (err) => {
  console.error("Stream failed:", err.message);
});

// Begin stream listener
stream.listen();
```

## Exception Handling

Errors are mapped to specific custom errors:

```typescript
import { GrowthScout, GrowthScoutValidationError } from "growthscout-js";

try {
  await client.sessions.create("", "", 5);
} catch (err) {
  if (err instanceof GrowthScoutValidationError) {
    console.error(`Validation failed: ${err.message}`);
  }
}
```

## Versioning Policy

This SDK adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Version numbers match the API platform compatibility bounds.
