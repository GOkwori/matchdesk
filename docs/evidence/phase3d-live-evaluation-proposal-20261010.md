# P3-04 controlled multilingual live evaluation — proposed authorization

Date: 10 October 2026. Status: **PROPOSED — NOT AUTHORIZED / NOT EXECUTED**.

## Scope and existing resources

The candidate is the existing Microsoft Foundry UK South project `matchdesk`
within account `aif-matchdesk-dev`, deployment `matchdesk-gpt-4o`
(GPT-4o 2024-11-20, Regional Standard). These identifiers are historical
configuration, not freshly verified deployment state, billing scope or credit balance.
Before any call, discover the exact live deployment, pricing meter, quota, RBAC,
credential scope and remaining user budget. Never emit credentials or secrets.

No new Azure resources, PTUs, storage services, third-party subscriptions,
production release or publishing authority are requested. Prefer the existing
deployment only; otherwise stop and seek new explicit approval.

## Proposed bounded qualification

- Source: **one frozen, deterministic synthetic scenario and evidence digest**,
  under exact qualified GitHub SHA; store a read-only source artifact.
- Matrix: exactly **9 requests** (English, Spanish, French x analyst, casual fan,
  broadcast caption). One model proposal per combination. Zero automatic retries,
  no loops beyond nine, no fallback to more expensive models.
- Output: structured, bounded `BroadcastEnvelope` payload proposal, retaining
  exact item/replay/version, source evidence, claim IDs, claims and output kind.
  Model prose is never treated as evidence or authorization.
- Maximum output request: 1,200 tokens per request, `store=False`, constrained
  input context, sequential execution, timeout and hard stop on unreported usage.
  Intended average input assumption: <=4,000 tokens per request; this is an
  **estimate** until preflight tokenization or the live provider can enforce it.
- Abort on the first invalid authorization, missing telemetry, unsupported claims,
  unexpected model/deployment identity, cost threshold, provider change, or
  repeated model error. Retain failed evidence; no unattended retry.
- Host-run invocation must be manually authorized against an exact workflow
  source SHA with an explicit cost confirmation. Never trigger on push or PR.
- Pass requires deterministic claim/metric checks **and independent fluent
  human-language review** of each of the nine exact-version outputs. Human review
  rates/availability are not included in the token estimate.
- Retain non-secret model/version, duration, input/output/total tokens, estimated
  incremental USD cost, source SHA, scenario/seed, claim/evidence/content digests,
  verification verdicts and redacted output artifacts.

## Pricing basis and spending boundary

Public indicative retail meter for GPT-4o 2024-11-20 Regional Standard,
UK South: **USD 3.025 per 1M input tokens and USD 12.10 per 1M output tokens**.
Reference: https://www.azurespeed.com/AzureAiModelPricing/Models/openai-gpt-4-o-1120
(visible Regional Standard UK South meter). Official pricing reference:
https://azure.microsoft.com/en-gb/pricing/details/azure-openai/ and Azure
Retail Prices API per:
https://learn.microsoft.com/en-us/azure/ai-services/openai/faq

**Estimate, not a quote:** at 9 x (4,000 input + 1,200 output tokens),
`(36,000 * 3.025 + 10,800 * 12.10) / 1,000,000 = USD 0.23958`,
excluding tax, ancillary metering, unexpected extra tokens and human review.
A proposed owner-authorized absolute evaluation allowance is **up to USD 1.00**
for this one evaluation batch only. The workflow/script still needs explicit
preflight and post-call metering: an Azure alert is not a hard spending limit.

Do not use startup credits to imply zero marginal cost. Confirm whether credit
actually applies to this resource. A price change, increased attempt count,
additional tool invocation, different billing scope or request for larger allowance
invalidates this proposal and requires re-approval.

## Lower/no-cost alternatives and rollback

- Default and lowest cost: existing offline provider fixtures + seeded
  claim-verification tests at **zero new model tokens**. This validates
  engineering contracts but not multilingual semantics.
- Human-authored manually reviewed translation fixtures can exercise the review
  path without model calls, but do not evidence the model's live accuracy.
- If model activation is approved, reuse only the already present pay-per-token
  Standard deployment. Do not provision PTU capacity or new hosting.
- Rollback: stop/cancel the manually dispatched evaluation; clear transient
  activation, leave all ongoing scheduled invocations disabled, retain
  non-secret evidence of attempted calls, and verify the service incurs
  no new recurring resource cost. Never delete shared Azure assets.
- If approval is not given, proceed with P3-05 offline producer UI and its
  authentication design; keep P3-04 IN PROGRESS.

## Explicit owner gate

**No activation yet.** Owner approval must expressly cover the exact:
`P3-04, 9 GPT-4o calls, no retries, <=1,200 requested output tokens each,
estimated USD 0.24, maximum authorization USD 1.00, existing UK South
deployment only, no new resources, no publication, manual dispatch only`.

An ordinary `Proceed` to development or document preparation is **not**
authorization to make the paid calls. Verify a fresh exact-head CI and live
deployment/billing information before dispatch.
