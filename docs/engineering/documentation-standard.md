# MatchDesk Documentation Standard

Project owner: George Okwori

Applies to: repository documentation, project descriptions, release notes and presentations

## Purpose

Present MatchDesk as George's initiative, with a clear account of the problem, the design, the implementation and the evidence. The project story should sound like its owner explaining his work. Technical material should explain the system directly.

This standard governs editorial voice. It does not change technical requirements, establish that work has been completed, or replace factual development records.

## Voice by document

| Material | Voice | Example |
| --- | --- | --- |
| README introduction and project story | First person, singular | "I am building MatchDesk around a simple question: what evidence supports the story?" |
| Goals and scope | First person for intent; precise statements for requirements | "My priority is a complete event-to-publication workflow." |
| Design decisions | First person only for a confirmed owner decision; otherwise proposed or neutral | "The proposed design separates metric calculation from narrative generation." |
| Solution design and API reference | Neutral technical prose | "The verification gate compares a numerical assertion with its registered metric query." |
| Test strategy and results | Neutral, evidence-led | "The report records the executed suite, source commit and observed results." |
| Runbooks | Direct instructions | "Check the deployment revision before starting the smoke test." |
| Progress and release notes | Neutral status, with optional confirmed personal reflection | "The replay work is complete; cloud qualification remains open." |
| Pitch and demo narration | First person, grounded in the demonstrated build | "I will show the source events behind this explanation." |
| Tooling and attribution | Brief, factual and proportional | Name a development tool and its actual use only when supported by records. |

Use "I" and "my" for George's narrative. Do not invent a team by using "we" or "our". Use the product name for technical behaviour. Third person is appropriate in factual owner metadata, contributor lists and actual approval records, not as a recurring narrator referring to "the user" or "George's requirements".

## Ownership and personal voice

Attribute the initiative, goals and confirmed design direction to George. Do not present a coding assistant as the product's founder, architect of record, or approving authority.

Do not invent biographical details, customer interviews, professional broadcasting experience, motives, frustrations, dates, results or personal reflections. A proposed first-person passage is a draft for George's review, not proof that he has approved every sentence.

Use first-person past tense only when the action or decision is supported. "I selected PostgreSQL" needs a confirmed selection; otherwise use "The current proposal uses PostgreSQL." An automated test result is not evidence that George personally executed or reviewed it.

Prefer specific reasoning to promotional language. Explain the constraint, the decision, the alternative and the consequence. Avoid generic claims such as "revolutionary", "game-changing", "seamless", "best-in-class" or "production-ready" without scoped evidence.

## Public documentation and execution instructions

Publish a normal project specification at `docs/project-specification.md`. It should state the problem, users, requirements, scope, acceptance criteria, delivery milestones and current status. Do not publish the raw implementation prompt as the specification.

Keep session commands, coding-assistant instructions, conversation transcripts, speculative brainstorming, private deployment context and unapproved personal drafts outside the public documentation. The private execution brief is supplied directly to the implementing tool, not automatically committed.

Public documentation must not read like a response to a user. Avoid phrases such as "as requested", "I have now created the files for you", "the agent was instructed", "continue with the next task", and "awaiting your next prompt" in the project narrative.

Do not remove product-agent terminology. MatchDesk's Tactical Analyst, Narrative Composer, Editorial Reviewer and Audience Adapter are runtime components and must remain accurately documented. Their system prompts, tool contracts, execution traces, limitations and evaluations are part of the technical product, not development-session chatter.

## Status and evidence

Distinguish planned, in progress, implemented, tested, deployed and verified states. A planned feature must not be described as operational. A green local test must not become a claim of a verified cloud release.

Every published performance or quality claim needs a source: commit, run, environment, date, command or workflow, test scope and retained evidence. Report blocked, failed, skipped and unexecuted checks as such. Do not replace them with optimistic prose.

Raw reports and audit records retain their actual producers, timestamps, actor identities and content. Generated API references may identify their generator. Automated commits and CI runs must retain truthful provenance. Do not claim that a bot action was George's manual action.

A progress report may say "Ready for owner review". It must not say "Approved by George" until that approval exists. Record the approval reference and time when supplied.

Synthetic data, cached demonstration outputs, offline model stubs and controlled error injection remain clearly labelled. Tests with model stubs must not be described as live Foundry qualification.

## Development tools and attribution

Keep the product story focused on MatchDesk rather than on the tools used to implement it. Document actual engineering tools in `docs/engineering/development-workflow.md` where useful, and make any requested or applicable disclosures accurately.

Do not force a statement such as "AI built this application" into every document. Equally, do not invent statements such as "I wrote every line manually" or "no AI assistance was used". Do not fabricate GitHub Copilot usage to strengthen a submission.

Retain applicable licence notices, contributor credit, actual commit authorship, signatures, build provenance and required disclosures. This editorial standard is not permission to rewrite history, hide relevant evidence or misstate a tool's involvement.

If a tooling record already exists, review how it is presented rather than silently deleting it. A focused engineering-methods section can coexist with a personal project story.

## Writing conventions

Use British English, plain language and concrete examples. Keep the introduction personal, then move quickly to the actual design and working evidence. Do not force first person into schemas, formulas, API descriptions or test output.

Use descriptive headings, short paragraphs and tables where comparison helps. Keep diagrams connected to the implementation. Do not leave placeholder screenshots, broken links, empty sections or invented results in release documentation.

Comments and docstrings explain behaviour, invariants and trade-offs. They do not narrate the coding session or congratulate the implementation. Pull request descriptions and release notes explain what changed, why, tests and limitations.

## Review checklist

- Is the project story recognisably George's initiative without invented biography or an invented team?
- Does each decision and status reflect what is actually confirmed or evidenced?
- Does technical prose describe the system rather than a conversation with an assistant?
- Are runtime AI capabilities, limitations and evaluation methods still explicit?
- Are tool usage, licences, contributors, automation provenance and required disclosures accurate?
- Are measured claims linked to the correct evidence and are failures or gaps visible?
- Are private execution instructions and personal deployment identifiers excluded from public documents?

Automated documentation checks should find broken links, missing required documents and obvious session-text leakage in authored prose. They must not blindly ban words such as "AI", "agent", "Copilot" or "generated", because those can be legitimate technical or attribution terms. Human review remains necessary for personal voice and claimed experience.

## Code requirement

All authored code must follow the [coding standard](coding-standard.md), including explanatory comments and maintained docstrings.
