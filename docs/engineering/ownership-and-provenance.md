# Ownership, contributions and provenance

**Document status:** current editorial/engineering disclosure, checked against repository
records on 25 October 2026. This document neither rewrites Git history nor certifies who
manually typed each line.

## Accountable ownership

George Okwori originated the MatchDesk initiative and is its owner and architectural
decision-maker. The problem framing, product requirements, goals, priorities, approved
design direction and human release decisions are owned by him. Owner attribution is
distinct from claiming exclusive keystroke authorship of generated, assisted or contributed
source code.

## Development assistance and factual attribution

Claude (Anthropic) and ChatGPT (OpenAI) have assisted with review and validation,
and existing recorded project history also identifies assistance with code authoring,
refactoring and project documentation. For example, the prior README's authorship section,
the 24 October documentation overhaul PR #189 and the project engineering-workflow
record explicitly disclose development assistance beyond review alone.

Accordingly, no repository document may claim **"Claude and ChatGPT were used only
for code review and validation"**, or **"all code and documentation were written
personally by George"**, without independent evidence that reconciles those historical
records. Such wording would be a misleading retrospective attribution.

The professional public narrative is: **"I conceived and direct MatchDesk, own the
product decisions and take responsibility for its release. I use development tools,
including Claude and ChatGPT, to support engineering and validation, while retaining
human accountability for every approval."**

## Runtime AI is different

Microsoft Foundry and Microsoft Agent Framework are part of the implemented product:
Tactical Analyst, Narrative Composer, Editorial Reviewer and Audience Adapter.
Azure AI Speech is an optional code path. These are product integrations, not
source-repository co-authors or publication authorities.

## Verifiable records and review boundaries

- Commit and PR actors, generated-by footers, workflow identities and timestamps
  remain authoritative for recorded operations and must not be altered to improve
  attribution optics.
- Automated tests, CI checks, robot comments and screenshots are not independently
  attributable human acceptance or an owner release signature.
- Any human acceptance record requires actor, date, exact source SHA, observed
  actions/results, reviewer decision and non-sensitive evidence.
- Historical design and evaluation documentation retains its original date and
  status; updates are additive and traceable.
- Tool-assisted drafting and review are compatible with George retaining product
  ownership and decision accountability; neither implies AI owns the initiative.

## Repository evidence

- [Git history](https://github.com/GOkwori/matchdesk/commits/development)
- [PR #189 — documentation overhaul](https://github.com/GOkwori/matchdesk/pull/189)
- [Engineering workflow](development-workflow.md)
- [Documentation standard](documentation-standard.md)
- [Release and acceptance ledger](../operations/release-status.md)
