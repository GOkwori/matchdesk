# MatchDesk over MCP

MatchDesk offers its match tools to other agents over the Model Context Protocol. A broadcaster's graphics assistant, an IDE agent or a Microsoft Foundry agent can compute registered statistics, read the events, overlays, stories and recaps, and, most usefully, have its own sentences checked by MatchDesk's verifier before anything is shown.

## Endpoint

- `POST /api/mcp` on the API, through the studio's same-origin `/api` on the Azure deployment: `https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/api/mcp`.
- **Transport:** Streamable HTTP, stateless. Each JSON-RPC request is one POST, answered with one `application/json` response. Notifications get `202`. `GET` returns `405` because the server never opens a stream of its own. There are no sessions and no batches.
- **Protocol versions:** `2025-06-18` (preferred), `2025-03-26` and `2024-11-05`.
- **Capabilities:** tools only. Every tool is annotated `readOnlyHint: true`.
- **Switch:** mounted only when the host sets `MATCHDESK_MCP_ENABLED=true`. It is on in the Azure demo (`infra/azure/demo.bicep`) and off everywhere else. The Vercel copy has no API.

To use it from VS Code, add `{"servers": {"matchdesk": {"type": "http", "url": "https://…/api/mcp"}}}` to `.vscode/mcp.json`. Any client that speaks Streamable HTTP works the same way. Interoperability was checked with the official MCP Python SDK client (`mcp` 1.20.0): initialise, list tools, call tools.

## Tools

| Tool | What it does |
|---|---|
| `list_metrics` | The fourteen registered statistics, with unit and definition |
| `list_players` | Both squads: id, name, shirt, position, starter |
| `compute_metric` | One statistic for a team or player over a window (minutes, or one half), recomputed from the log |
| `check_sentence` | Checks a sentence that states one statistic. It recomputes the number at the stated precision and checks the sentence names the subject, the statistic and any window it states. Returns `verified` or the reason it was sent back |
| `verify_claim` | Verifies a full `Claim` contract, including the registered event facts `goal_scorer.v1` and `sequence_gap.v1` |
| `get_events` | Logged events in a window, filtered by team, player or type (at most 200 per call) |
| `get_overlays` | The timed overlay cues in a window, in one persona and language, each with its claims and status |
| `get_story` | The verified fan story for a goal, or the list of goal stories |
| `get_recap` | The automated half-time recap or the recap at the replay point, with every figure's check |

Argument problems come back as tool results with `isError: true` and a message the model can act on, such as "player must be a player id such as nbr-09". An unknown tool or method is a JSON-RPC error.

## Limits

- **One synthetic match.** Northbridge FC v Riverside United, up to the replay point (67:12). Nothing is real, live or published.
- **Read-only.** No tool writes, publishes, calls a model or reads anything outside the synthetic log and the feeds built from it.
- **No key, no personal data.** The 64 KB request limit applies. Telemetry records one span per call (`matchdesk.mcp.call`) with the tool name and whether it answered, never the arguments.
- **The verifier's own limits apply.** They are listed in the [judging guide](../competition/judging-guide.md#what-the-verifier-does-not-check).

Source: `backend/src/matchdesk/api/mcp_routes.py` (protocol) and `backend/src/matchdesk/domain/mcp_tools.py` (tools); tests in `backend/tests/test_mcp_routes.py`.
