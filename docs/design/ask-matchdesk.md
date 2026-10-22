# Ask MatchDesk

A question box in the studio that guides people around the app and answers questions about the match, and shows the proof for every factual answer.

## Principles

1. **The engine writes every number.** Facts come from the registered metrics over the canonical event log. A language model, when one is used, only translates the question into a structured query plan; it never writes a figure or a sentence a reader sees.
2. **Every factual sentence is a claim.** Each one is built as a `Claim` with its assertion or event fact, checked by the parity-tested verifier (`verifier.ts`, identical to `verify_claim` on every fixture case), and shown with its status and the events it cites. A sentence that does not verify is shown as not verified; nothing is hidden or reworded.
3. **Guidance never guesses.** Questions about the app are answered from a fixed help index, with a link to the screen or tour stop. No model is involved.
4. **Honest about scope.** It answers questions about this synthetic match only, up to the replay point (67:12). It declines predictions, other matches, real players and anything it cannot check, and says why.

## What it answers

| Kind | Examples | How |
|---|---|---|
| Measured stats | "How many shots did Northbridge have in the second half?" "Possession after 60 minutes?" "Okafor's shots" | Metric × subject × window, computed and verified |
| Comparisons | "Who had more shots?" | One verified line per team, then a comparison derived from those two lines and labelled as such |
| Score and scorers | "What's the score?" "Who scored?" | `goals.v1` per team; one `goal_scorer.v1` fact per goal |
| Guidance | "What does Eligible mean?" "How do I approve a draft?" "Start the tour" | Help index with a link |
| Out of scope | "Who will win?" "What about Arsenal?" | A clear refusal with what it can do instead |

Metrics: goals, shots, pass accuracy, synthetic xG, final-third entries, possession (teams only). Windows: whole match so far, first or second half, before/after/between minute marks, last N minutes.

## Optional: understanding free-form questions with Azure AI Foundry

When the host enables it (`MATCHDESK_ASSISTANT_FOUNDRY_ENABLED=true`, off by default), a question the built-in parser cannot read is sent to `POST /api/assistant/plan`. The service asks a Foundry model to return only a JSON query plan in a fixed schema. The plan is validated on the server and again in the browser, then answered by the same deterministic engine. Limits: questions of at most 300 characters, a small output token cap, a per-session request budget and a global switch. If the service is off, slow or fails, the assistant says it can't read that question and offers the suggested ones.

## Accessibility

Native modal dialog for focus containment and Escape; a labelled question field; answers in a polite live region; every status shown as text, not colour alone; 24 px minimum targets; reduced motion respected; covered by the WCAG 2.2 axe pass and keyboard tests.

## Performance

The panel and the engine load only when the assistant is opened, so the per-page budget is unchanged until then. The event log is the same lazily loaded file the composer and evidence screens already use.
