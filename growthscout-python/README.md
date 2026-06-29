# GrowthScout AI Python SDK

The official Python client library for interacting with the GrowthScout AI Platform.

---

## Installation

```bash
pip install growthscout
```

## Quick Start

```python
import asyncio
from growthscout import GrowthScout

async def main():
    # Initialize core client
    client = GrowthScout(
        api_key="gs_dev_key_12345",
        base_url="http://localhost:8000"
    )

    # Create a new session
    session = await client.sessions.create(
        niche="dental clinic",
        location="Miami, FL",
        max_leads=5
    )
    print(f"Created Session ID: {session.session_id} (Status: {session.status})")

if __name__ == "__main__":
    asyncio.run(main())
```

## Authentication

All requests require authentication via an API Key injected into the `X-API-Key` header:

```python
client = GrowthScout(api_key="YOUR_API_KEY")
```

## Real-Time SSE Streaming & Reconnection

The SDK supports consuming real-time execution steps through Server-Sent Events (SSE). Reconnection and event synchronization are handled automatically using `Last-Event-ID`:

```python
async for event in client.sessions.stream("sess_a1b2c3d4").listen():
    print(f"[{event.event_type}] {event.data}")
```

## Exception Handling

Errors are mapped to standard python exceptions:

```python
from growthscout import GrowthScout, GrowthScoutRateLimitError, GrowthScoutValidationError

try:
    await client.sessions.create(niche="", location="")
except GrowthScoutValidationError as e:
    print(f"Validation failure: {e}")
except GrowthScoutRateLimitError as e:
    print(f"Rate limited: retry after {e.retry_after} seconds.")
```

## Versioning Policy

This SDK adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Version numbers match the API platform compatibility bounds.
