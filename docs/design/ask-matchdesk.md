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
| Comparisons | "Who had more shots?" | One verified line per team, then a comparison from the unrounded figures, labelled as derived |
| Score in a window | "Score after 40 minutes?" "Score in the second half?" | A lead or a draw only for windows that start at kick-off; otherwise "goals in this window only, not the score" |
| Score and scorers | "What's the score?" "Who scored?" "Who scored the second goal?" "Who won?" | `goals.v1` per team; one `goal_scorer.v1` fact per goal, or only the nth goal in order. A whole-match score notes that the replay stops before full time, so there is no result yet |
| Team rankings | "Which team had the most shots?" | Both teams, verified, then the derived comparison. Player rankings stay declined |
| Guidance | "What does Eligible mean?" "How do I approve a draft?" "Start the tour" | Help index with a link |
| Player leaders | "Who made the most tackles?" "Which player had the most shots for Riverside?" | The top three players, each line verified, then who led or who is joint top. Pass averages only rank players with at least 10 passes |
| Out of scope | "Who will win?" "What about Arsenal?" "Shots on target?" "Who was man of the match?" | A clear refusal with what it can do instead. Statistics outside the eighteen registered metrics (pass counts, touches, heat maps, positions), the speed of a single shot (shown on its overlay instead), judgements such as "best player", unknown players or record ids ("nbr-99"), qualifiers no metric records (header, foot, inside or outside the box, counter-attack or set piece, season or other games, "when losing", "after the equaliser") and time phrases it cannot read exactly are declined, never answered as a nearby question |

Metrics: goals, shots, synthetic xG, final-third entries, pass accuracy, average pass length, progressive passes, pass difficulty, passes under pressure, estimated ball speed, tackles, interceptions, ball recoveries, possession (teams only), and from the log's synthetic tracking shot speed, top speed, distance covered and sprints ("Who ran the furthest?", "Who was the fastest player?" rank players). Windows: whole match so far, first or second half, before/after/between minute marks, last N minutes.

## Optional: understanding free-form questions with Azure AI Foundry

When the host enables it (`MATCHDESK_ASSISTANT_FOUNDRY_ENABLED=true`, off by default), a question the built-in parser cannot read is sent to `POST /api/assistant/plan`. The service asks a Foundry model to return only a JSON query plan in a fixed schema. The plan is validated on the server and again in the browser, then answered by the same deterministic engine. The answer shows how the question was read (for example "shots · Riverside · second half"), so a misreading is visible. Limits: questions of at most 300 characters, 200 output tokens, a 7-second timeout (shorter than the browser's 8-second wait), at most 20 calls a minute and 400 a day per API replica, and a global switch. The budget is shared by everyone using that replica: it bounds cost, not fairness. Any model or client fault returns the "not understood" plan, with no error detail. If the service is off, slow or fails, the assistant says it can't read that question and offers the suggested ones.

## Accessibility

Native modal dialog for focus containment and Escape; a labelled question field; answers in a polite live region; every status shown as text, not colour alone; 24 px minimum targets; reduced motion respected; covered by the WCAG 2.2 axe pass and keyboard tests.

## Performance

The panel and the engine load only when the assistant is opened, so the per-page budget is unchanged until then. The event log is the same lazily loaded file the composer and evidence screens already use.
