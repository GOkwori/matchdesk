# Azure live checks, 23 October 2026 (evening)

The Azure demo was redeployed from `development` at `88db1b2` (after #181 and #182) by
GitHub Actions run 39994195100 (`azure-demo.yml`, mode deploy). Every step passed, including
the smoke test of the public studio and the API behind it. The checks below were then run
against the public studio, https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io,
in a real browser.

| Check | Result |
| --- | --- |
| MCP: `initialize` on `POST /api/mcp` through the studio's same-origin `/api` | Server `matchdesk` 1.0.0, protocol `2025-06-18` |
| MCP: `tools/list` | The nine tools, as in the [design note](../design/mcp.md) |
| MCP: `check_sentence` "Okafor scored 2 goals." / "Okafor scored 3 goals." | `verified` / `needs_revision` |
| Live stream: `GET /api/live/stream?speed=60&from_ms=2690000` | `hello` frame says "recorded synthetic log, played back"; the half-time recap frame arrived `verified`, checked at 45:01 on the 844 events received |
| Match recap page `/story/recap` | Rendered, and "Checked again in your browser" shown |
| Live agent run `POST /api/agents/run` | Accepted (202). Completed on Microsoft Foundry via Agent Framework: 8 specialist turns, 38 tool calls, 3 verification rounds, claims that never verified withheld, then the audience versions; 93,690 tokens |

The run's elapsed time kept counting after it finished (`elapsed_ms` was measured to "now"); the
API now reports a finished run's duration instead (`test_a_finished_run_reports_its_duration_not_its_age`).
Application Insights traces for these calls are in the workspace; they are not reproduced here.
