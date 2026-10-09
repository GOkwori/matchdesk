# P2-04 live Foundry smoke qualification — 9 October 2026

Status: **TESTED / PASS**.

Source under test:
`f1ba3a9ae2b6e2e54de727761763085ee77776d8`.

Workflow:
[P2D live Foundry smoke run 37923842661](https://github.com/GOkwori/matchdesk/actions/runs/37923842661).

## Scope

This qualification executed exactly one real tactical-specialist turn through the
reviewed Microsoft Agent Framework / Foundry adapter. It exercised the configured
`matchdesk-gpt-4o` deployment through GitHub OIDC and Foundry RBAC. The test retained
no API key in source, used `store=False`, enforced the locked 1,200-token output ceiling,
and did not grant approval or publication authority.

## Result

The workflow completed successfully. All setup, OIDC authentication, dependency sync,
live execution and evidence-retention steps passed.

Retained non-secret runtime evidence:

| Field | Value |
|---|---:|
| Runtime | `microsoft-agent-framework-foundry` |
| Specialist | `tactical_analyst` |
| Input tokens | 2,009 |
| Output tokens | 104 |
| Total tokens | 2,113 |
| Latency | 6,763 ms |
| Maximum output tokens | 1,200 |
| Proposed claims | 1 |
| Structured content present | true |
| Store | false |
| Verification | `supported_inference` |
| Evidence digest | `3d7f721825329852938d485e5b46b80d6c7ab0eeac1720860a8e3aa6cbc0d5a3` |

The smoke therefore demonstrated that one live model-generated tactical claim remained
bound to supplied deterministic event IDs and passed through the P2-02 verifier as
`supported_inference`, rather than being upgraded to deterministic fact.

## Artifact identity

GitHub artifact:

- name: `p2d-live-foundry-evidence`;
- artifact ID: `11613755037`;
- size: 424 bytes;
- digest:
  `sha256:c150aefc7ff7d29efcba07b82adb2fcafad88b32d248ad875f3aa6ac4a1db481`;
- retention expiry reported by GitHub: 8 November 2026.

## Boundaries

This PASS qualifies the bounded P2-04 live-runtime path only. It does not establish
producer publication, production hosting, unrestricted autonomous execution, durable
workflow persistence, multilingual audience quality or broad model reliability.

P2-05 must separately qualify failure injection, timeout classification, retry-budget
enforcement, recovery, verifier rejection/revision paths and model-output evaluation.
