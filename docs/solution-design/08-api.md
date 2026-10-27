# API reference

Status (26 October 2026): the four foundation contract routes below remain documented for their original narrow purpose. The Azure competition demo also serves replay, verified feeds, bounded live-agent calls, read-only MCP tools and an optional Ask planner. Use the [judging guide](../competition/judging-guide.md), [traceability matrix](../competition/traceability-matrix.md) and [Azure demo runbook](../operations/azure-demo.md) for the hosted routes. [OpenAPI](../../contracts/openapi.json) is a committed contract artifact; do not assume it represents every route exposed by the deployed demo.

| Method | Path | Result |
|---|---|---|
| GET | /api/health | Process liveness; historical `phase`/`model_mode` labels in its response are not an authoritative test of the separately mounted live-agent route |
| GET | /api/ready | Legacy foundation readiness behavior; do not treat it as a full hosted-demo readiness certificate |
| GET | /api/contracts/event | Structural MatchEvent schema |
| POST | /api/contracts/event/validate | Structural acceptance and content SHA-256; evidence_verified=false |

Bodies are limited to 65,536 actual bytes. Declared lengths are validated but are not
trusted as a substitute for counting bytes. Errors include field locations and error
codes without echoing the submitted value. No events are persisted by these routes.

The hosted API also exposes read-only or bounded endpoints: `/api/agents/run` (rate-limited live Foundry run), `/api/mcp` (read-only MCP tools), `/api/live/stream` (replay stream), `/api/assistant/plan` (optional Ask planner), `/api/voice/status` and `/api/voice/{kind}/{item}` (Azure AI Speech for allowlisted verified items only), and `/api/producer/preview`. The overlay and recap feeds are served by the studio, not the API, at `/overlays/nbr-riv.json` and `/recaps/nbr-riv.json`. The public producer approval/publishing experience is simulated in the browser and does not send to real destinations. Real authenticated producer session, authorization, publishing and externally connected delivery remain future production work.
