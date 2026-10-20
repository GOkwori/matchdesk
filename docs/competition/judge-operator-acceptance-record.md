# MatchDesk Issue #64 — judge operator acceptance record

**State: NOT RUN / NOT APPROVED.** This blank record is a human-review
template, not a certification, completed rehearsal, or submission authorization.
PR #80 qualified the **synthetic-only automated loopback browser workbench**
on its recorded source; current candidate changes require their own exact-head
checks. Human demo acceptance must be established independently.

## Evidence identity (complete during the actual rehearsal)

| Field | Actual value |
| --- | --- |
| Tested commit (full SHA, `git rev-parse HEAD`) | NOT RECORDED |
| Checkout cleanliness (`git status --porcelain`) | NOT RECORDED |
| UTC rehearsal date and time | NOT RECORDED |
| Operator and independent reviewer | NOT RECORDED |
| OS, browser/version, keyboard/assistive technology | NOT RECORDED |
| Local host and port (must be exact 127.0.0.1) | NOT RECORDED |
| CI workflow runs for the *tested SHA* | NOT RECORDED |
| Sanitized screenshot/artifact locations | NOT RECORDED |
| Reviewer decision and date | **NOT RUN** |

Never paste or attach bearer tokens, session JSON containing tokens, cookies,
authorization headers, private environment variables, or raw browser network logs.
Record only source SHA, safe on-screen evidence, test outcomes and deviations.

## Operator procedure

1. Check out the intended candidate on an approved local workstation, record
   `git rev-parse HEAD` and `git status --porcelain`, and install only the
   approved lockfile dependencies. Follow
   [the isolated host startup guide](judge-loopback-workbench.md). **Do not**
   use a LAN bind, reverse proxy, public tunnel, live model key, production
   identity, paid hosting or default API route mounting.
2. Launch the Python judge host and Next.js interface using the documented
   explicit localhost commands, then open `http://127.0.0.1:3000/judge`.
   Capture the *initial empty* state and the synthetic/read-only disclosure.
3. Select **Start demo**. Read the source-event trail and deterministic
   moments; inspect the registered metric, evidence SHA-256, actual
   `verified` verdict and deliberate `needs_revision` verdict. Confirm
   specialist wording is labelled **scripted**, not a live AI result.
4. Capture only the public, rendered source/claim/variant sections (no browser
   network payload). Select **Replay** and confirm the same visible evidence
   and all nine visible audience variants. Variants are not approved
   translations and must say **language review not run**.
5. Select **Reset**; the run should return to the empty evidence state
   with generation incremented. Select **Replay** and compare the
   same evidence and variants again. Never record the rotating bearer.
6. Start a second judge run in a separate private browser context. Reset
   and close the first run; ensure the second still replays independently,
   then close it. Confirm that both sessions lose access when ended.
7. Confirm producer authentication, approval and publication remain
   unavailable. Check denied requests, custom error messaging and
   clean teardown, using the already-defined automated negative tests.
8. Perform manual keyboard-only navigation, visible focus, error handling,
   responsive checks at narrow and desktop widths, and a screen-reader
   assessment **only if an appropriately qualified reviewer actually runs
   it**. Independent WCAG acceptance is tracked by Issue #52 and is not
   implied by this rehearsal.

Run the scoped source-backed tests from the repository root (or record why
they could not run):

```bash
git rev-parse HEAD
git status --porcelain
PYTHONPATH=backend/src uv run --no-sync python -m pytest -q backend/tests/test_judge_sessions.py backend/tests/test_judge_local_routes.py backend/tests/test_judge_golden_path.py
PYTHONPATH=backend/src uv run --no-sync python scripts/judge_demo.py
```

The connected browser suite requires the explicit local hosts described in the
startup guide. Its committed CI workflow is `Judge loopback browser`, and it
must be tied to the *exact candidate SHA* before citing its result.

## Acceptance register — fill only with observed outcomes

Use **PASS**, **FAIL**, **BLOCKED**, or **NOT RUN** for each row.
Do not prefill a passing result based on an earlier PR or a planned action.

| ID | Observed qualification | Outcome | Safe evidence reference |
| --- | --- | --- | --- |
| J64-01 | Exact source, loopback-only host, synthetic-only disclosure | NOT RUN | — |
| J64-02 | Start and source-event/moment/metric provenance | NOT RUN | — |
| J64-03 | Verified claim and false claim rejected | NOT RUN | — |
| J64-04 | Replay identical before and after reset | NOT RUN | — |
| J64-05 | Nine scripted, unreviewed audience variants | NOT RUN | — |
| J64-06 | Independent second browser session survives first-session reset/end | NOT RUN | — |
| J64-07 | Expired/old bearer, cross-origin and direct privileged access denied | NOT RUN | — |
| J64-08 | Producer/publisher withheld, clean end and recovery/error banners | NOT RUN | — |
| J64-09 | Keyboard, visible focus, responsive mobile/desktop checks | NOT RUN | — |
| J64-10 | Exact-head CI gates and connected loopback Playwright results | NOT RUN | — |
| J64-11 | Independent reviewer approval of actual local rehearsal | NOT RUN | — |

**Deviations / defects:** NOT RECORDED.

**Reviewer decision (PASS / FAIL / BLOCKED / NOT RUN):** NOT RUN.

**Reviewer evidence and sign-off:** NOT RECORDED.

## Non-substitutable release holds

Automated tests and a successful rehearsal would demonstrate only the bounded
synthetic workbench. They do **not** establish independent assistive-technology
acceptance (#52), owner/source asset provenance (#65), delegated producer
identity and single-use authorization (#61), real multilingual semantics (#62),
the broader security/recovery boundary (#63), a functioning live broadcast
publisher, main promotion, production deployment, or official competition
submission. Those require their own authorizations and evidence.
