# API reference

Status: the four routes below are implemented. [OpenAPI](../../contracts/openapi.json)
is exported from the application, not hand-maintained as a list of future endpoints.

| Method | Path | Result |
|---|---|---|
| GET | /api/health | Process liveness, foundation phase, models not connected |
| GET | /api/ready | HTTP 503; product dependencies not implemented |
| GET | /api/contracts/event | Structural MatchEvent schema |
| POST | /api/contracts/event/validate | Structural acceptance and content SHA-256; evidence_verified=false |

Bodies are limited to 65,536 actual bytes. Declared lengths are validated but are not
trusted as a substitute for counting bytes. Errors include field locations and error
codes without echoing the submitted value. No events are persisted by these routes.

Future session, replay, content, approval, audit, overlay and SSE routes remain planned.
They must acquire scoped actor/session context, reject unauthorised cross-session
access and use concurrency controls before being made externally available.
