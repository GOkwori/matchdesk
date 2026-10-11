# ID3H disposable evidence-bound approval qualification — 11 October 2026

Status: **TESTED — offline/disposable CI only**. The qualification is not a
live migration approval, a real-tenant identity proof, a production release
certification or authorization to incur infrastructure costs.

## Exact source and passing hosted checks

**Source:** development commit `c3a166be953c4c9ae60d0e9fe6d84a10379f255c`.

| Gate | Hosted run | Outcome |
| --- | --- | --- |
| Foundation CI | [38138748717](https://github.com/GOkwori/matchdesk/actions/runs/38138748717) | PASS: 1,058 Python tests; lint, formatting, typing and frontend checks |
| Foundation integration | [38138748713](https://github.com/GOkwori/matchdesk/actions/runs/38138748713) | PASS: runtime-browser and native-images jobs |
| Source security | [38138748691](https://github.com/GOkwori/matchdesk/actions/runs/38138748691) | PASS: history-secrets and Python/JavaScript CodeQL jobs |
| Dependency audit | [38138748809](https://github.com/GOkwori/matchdesk/actions/runs/38138748809) | PASS |

All four results belong to the source commit above. This document records
those observations; it does not transfer their exact-source qualification
to a later code or documentation commit.

## Qualified controls and negative cases

The `DisposableApprovalQualificationHost` evaluates the host-observed actor,
exact disposable environment, trusted out-of-band Ed25519 verification key,
time-limited signed scope and durable single-use approval reservation.
It rechecks actor and observed state after reservation; failed checks deny
without restoring a consumed grant. Its receipt explicitly contains
`execution_authorized=False` and never runs migrations.

The `DisposableCIFileEvidenceReader` hashes seven fixed private CI files:
tenant identity, database identity, migration SQL, historical evidence, backup
evidence, catalog evidence and cost decision. It rejects missing, empty,
symbolic-linked and insecurely permissioned files; pins the evidence directory;
bounds file size and independently reads each content digest twice. The
`EvidenceBoundCIHostSource` compares all seven observed values with the
scope reported by its enclosing host before approval qualification.

The end-to-end synthetic tests cover valid, non-executing approvals; all seven
single-file tamper cases; missing evidence; workload identity mismatch; drift
after a one-use reservation; and replay rejection. Test identities, signing
keys and files are disposable. Hash agreement is **not** proof of any
real-world history, identity, backup or cost authorization.

## Retained failures, not waived

- `fb8d1013f2a0d4b8ffc6177888b49d68bf09f207` failed Python test
  collection due to a cross-test-module import.
- `d91daf819500b481e796dcd411a506de0f797e81` failed due to stale test
  fixture references.
- `7c08ff1ab94aa76b81831a11dd368419f81f977a` passed 1,058 Python
  tests but failed the pinned Ruff formatter on a test signature.
- `c3a166be953c4c9ae60d0e9fe6d84a10379f255c` passed all four required
  GitHub workflow groups after the exact formatter correction.

## Explicit blockers before any real operation

The CI adapter is not an identity provider, tenant verifier, migration
provenance proof, backup restore test or real execution host. Local file
modes and repeat reads do not defend against a compromised same-identity
process. A test host supplying `ObservedReleaseFacts` is not evidence that
those facts came from a genuine tenant or database.

A separately reviewed live execution host would need independently verified
workload/human identity, exact target and source state, migration provenance,
catalog reconciliation, recoverable backup evidence, pinned approval keys,
least-privilege execution rights and auditable, replay-resistant authorization
enforced at the action boundary. Caller-controlled model prompts, token
claims or tool inputs are not authorization sources. High-risk changes require
explicit human approval and cost governance before execution.

**Not authorized:** production or customer migrations, cloud spending,
publishing, live customer authentication, protected-main promotion or use of
this offline receipt as an execution grant.
