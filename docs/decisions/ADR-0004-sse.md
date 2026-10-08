# SSE and HTTP commands

Date: 8 October 2026. Status: Accepted design direction; implementation planned.

## Decision and consequences

Use HTTP for explicit producer commands and server-sent events for notifications. Cursors must be session/replay-scoped; replay reset invalidates the prior cursor generation. Backpressure and reconnect behaviour need tests. No SSE endpoint exists in this foundation.
