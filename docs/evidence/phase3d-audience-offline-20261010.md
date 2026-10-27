# Phase 3D — audience adaptation offline qualification (10 October 2026)

Status: **OFFLINE CONTROLS TESTED; FULL P3-04 IN PROGRESS**.

## Qualified source and hosted evidence

Exact `development` source: `d3709d89cfcd942a0a3acd8aacb7d4d6c6d3aa88`.

| Required workflow | Run ID | Conclusion |
|---|---:|---|
| Foundation CI | 38020128307 | success |
| Foundation integration | 38020128302 | success |
| Dependency audit | 38020128254 | success |
| Source security | 38020128281 | success |

Foundation CI executed **388 Python tests** under Python **3.12.15** with **96.01%
total package coverage**. Contracts, documentation, Ruff lint/format, strict mypy and
the frontend build passed; the integration/security checks passed on the same SHA.
Earlier formatting/mypy failures remain visible in CI and are not described as passes.

## Implemented and qualified

- `audience_variants.py`: exact source/variant content digests, replay/version/evidence
  and claim binding; rejects mismatched/blocked verification; preserves numerical
  overlay assertions; no approval inherited by a new localized draft.
- `audience_generation.py`: explicit language/persona adaptation prompt and bounded
  provider interface; validation of untrusted proposed payloads with a strict broadcast
  envelope; no automatically configured or activated external provider.
- `audience_quality.py`: source-bound reviewer-reported assessments in five independent
  categories: meaning preservation, football terminology accuracy, linguistic quality,
  persona fit, and avoidance of extra factual assertions. The matrix requires all nine
  English/Spanish/French and analyst/casual-fan/broadcast-caption combinations.
- The regression suite exercises each locale/persona pairing, invalid/missing claims,
  stale content digests, malformed provider output, changed output kind, missing/duplicate
  quality records and negative reviewer judgments using **offline fixtures**.

## What this evidence does NOT establish

- No live multilingual Foundry/Agent Framework run was made for Phase 3D.
- The generated wording in unit tests is mock text, **not model-produced translation**.
- `AudienceQualityAssessment.reported_pass` describes submitted reviewer flags, not
  demonstrated fluency or factual equivalence.
- No authenticated independent human linguistic assessment of nine real variants has
  been recorded.
- No translation model comparison, multilingual model evaluation, sustained reliability
  or end-to-end evidence-to-output acceptance was executed.
- No automatic publication, protected-main promotion, production deployment or
  additional paid model spend was authorized.

The pure evaluator cannot prove semantic equivalence merely because a new sentence
retains the original claim ID. Language-review acceptance must be a real reviewed,
identity-bound decision, and the host must retain the reviewer, evidence source and
current content digest. A failed reviewer judgment must prevent downstream acceptance.

## P3-04 remaining acceptance

1. Prepare an explicit **bounded live evaluation budget and activation approval**
   (model/deployment, number of calls, token ceiling, estimated cost and rollback).
2. Generate real outputs in **all nine** required language/persona combinations from
   the same frozen evidence-bound source, with no unreviewed additional facts.
3. Re-run deterministic metric/claim verification against the actual evidence. Retain
   source SHA, scenario/seed, content/evidence digests, model identity, token/time/cost
   telemetry, errors and generated artifacts, excluding credentials.
4. Obtain **independent fluent human review** of English, Spanish and French meaning,
   football terms, style, persona and unsupported claims. Record each version-bound
   decision and rejected/corrected candidates.
5. Verify repeatability/failure recovery and confirm no variant can publish without
   a separately authenticated, current, explicit producer approval.

Do not change the backlog to P3-04 TESTED or say R7 is complete before these
requirements have supporting execution and human-review evidence.
