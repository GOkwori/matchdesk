# P2-05 live Foundry model evaluation — 9 October 2026

Status: **TESTED / PASS**.

Source under test:
`94fa73a37d69dbd03bf14820da63aeee5694383e`.

Workflow:
[P2E live Foundry evaluation run 37941568298](https://github.com/GOkwori/matchdesk/actions/runs/37941568298).

## Scope

This qualification executed exactly one bounded tactical-specialist turn through the
reviewed Microsoft Agent Framework / Foundry adapter and then evaluated the returned
proposal through the deterministic P2-05 model-evaluation gate.

The model was permitted to propose only non-authoritative output. The host retained
control of evidence binding, claim verification, timeout/retry policy and publication
authority. The live run used `store=False` and the existing 1,200-token output ceiling.

## Result

The workflow completed successfully.

Retained non-secret evidence:

| Field | Value |
|---|---:|
| Runtime | `microsoft-agent-framework-foundry` |
| Specialist | `tactical_analyst` |
| Input tokens | 2,007 |
| Output tokens | 117 |
| Total tokens | 2,124 |
| Latency | 8,187 ms |
| Maximum output tokens | 1,200 |
| Proposed claims | 1 |
| Store | false |
| Evaluation status | `pass` |
| Verification status | `supported_inference` |
| Evidence digest | `6b46703808ef501667ad7cf994207e4298439a41bc75fa44c0f63e2cfaca9645` |

The configured model/deployment identifier was masked by GitHub because it is supplied
through a repository secret. This record therefore does not infer or duplicate the
secret value from workflow logs.

## Artifact identity

GitHub artifact:

- name: `p2e-live-foundry-evidence`;
- artifact ID: `11621674108`;
- size: 429 bytes;
- digest:
  `sha256:20665b333b121aa85abe05b006b3e456fee43def3524ae9488c46ff291888958`;
- retention expiry reported by GitHub: 8 November 2026.

## Qualification conclusion

P2-05 is TESTED for its defined scope. Deterministic qualification already covered
bounded retry success, retry exhaustion, timeout fallback, host permission blocking,
role-mismatch blocking, persisted workflow recovery, false measured claims, unbound
claims and natural prose without evidence.

The live qualification now additionally demonstrates that a real model-generated
proposal can pass through the same deterministic evaluation path and remain classified
as `supported_inference`, not upgraded to deterministic fact.

This PASS does not authorize production deployment, publication, unrestricted agent
autonomy, durable production workflow execution or increased model spend.

P2-06 Phase 2 review is next.
