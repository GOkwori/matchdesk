# MatchDesk — audience, recovery and manual accessibility assurance handoff

Status: **DRAFT / PARTIAL**. This document records preparation, not completed live or manual qualification.
Source baseline: `development` `fb9292db705800d86035796eddbb34bbd93a653a` (18 October 2026).
Associated issues: [#62](https://github.com/GOkwori/matchdesk/issues/62), [#63](https://github.com/GOkwori/matchdesk/issues/63), [#52](https://github.com/GOkwori/matchdesk/issues/52).

## Audience integrity (#62)

- All nine language/persona synthetic contracts exist. They do **not** prove translated meaning.
- Exact source scope, evidence IDs, claim IDs, match window, item version, replay and digest must match before recording a quality assessment. Failed or forged verification statuses are not acceptable.
- PR #90's cooperative timeout, payload revalidation and response-size tests have four exact-head CI successes. Its code is not in `development` until a separately authorized merge.
- Combined draft PR #101 is separately five-workflow-green on exact head `40e2798` (as observed on 20 October). It must not be represented as deployed or approved.
- Still blocked: approved model adapter, real transport deadline and token/cost limits, privacy and prompt-poisoning review, **nine independent fluent language/persona evaluations**, and owner-controlled spending/activation.

## Recovery and security (#63)

Existing disposable integration coverage includes real PostgreSQL customer-session rotation under a separately authenticated role, restart persistence, injected insert rollback, legacy ID3H dump/restore on a clone, replay denial, clone-only account suspension, and source-isolation checks. Unit-level outage/transaction-failure probes are additive; they do not replace real PostgreSQL execution.

Remaining independent work:
- Real restricted-role issuer/stager and producer grant races: revoked-vs-consumed grants, concurrent issuers, expiry at the commit boundary, audit rollback, forced restart and replay.
- Recovery point/time objectives and restore drill measured with an operator, including recovery authorization/secret handling.
- Explicit checks that no authenticated session, approval, or publication authority is reconstructed from stale backups.
- No protected branch, production dataset, or paid environment may be touched during these tests.

## Accessibility reviewer handoff (#52)

**All manual modalities: NOT RUN.** Current [runbook](sunset-v3-accessibility-manual-runbook.md), [observation template](sunset-v3-accessibility-session-template.md), and [Phase 2 protocol](sunset-v3-accessibility-phase2.md) remain authoritative. A tester should use a pinned disposable local build, record its *actual* tested SHA, and verify all 14 destinations in **both** themes.

| Modality | Required observation | Status |
| --- | --- | --- |
| Windows Chrome keyboard-only | Skip link, focus order, expanded navigation, modal trap/return, long-page focus | NOT RUN |
| Windows Chrome NVDA | Announced headings, roles, states, tables, dynamic status, modal isolation | NOT RUN |
| macOS Safari VoiceOver | Rotor landmarks/controls, spoken states, modal behaviour | NOT RUN |
| Android Chrome TalkBack or iOS Safari VoiceOver | Real device gestures, focus and touch targets | NOT RUN |
| Actual browser zoom 200% and 400% | Reflow, clipping, fixed UI occlusion at effective CSS widths | NOT RUN |
| Both themes, contrast/spacing/forced colours | 4.5:1 text/3:1 applicable elements, spacing overrides, reduced motion | NOT RUN |
| Qualified independent sign-off | Attributable evidence, severity, exact-head retest and disposition | NOT RUN |

For **every screen × theme × method** retain tester, date/timezone, OS/browser/AT version, physical and effective viewport, test SHA, keystrokes or gestures, actual screen-reader output, WCAG 2.2 criterion, redacted evidence reference, defect link and outcome. Do not infer PASS from Playwright screenshots or CI.

## Hold and promotion rules

- Separate draft PR into `development` only after new exact-head Foundation CI, Foundation integration, Source security, and Dependency audit success plus review. No automatic merge.
- No live Entra/MFA, external model calls, producer approvals, publishing, production deployment, or charged cloud provisioning.
- Judge/manual demonstration and physical accessibility sign-off remain separately gated.
