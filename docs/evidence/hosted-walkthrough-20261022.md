# Hosted judge-path walkthrough — 22 October 2026

A run of the judge path on the live site, in a real browser, rather than in CI.

- **Site:** https://matchdesk-seven.vercel.app, Vercel deployment `dpl_9Y4CU7N1tp26A8u1Ygfb5RTcjtN8`, built from
  `release/submission-2026-10` @ `76de6c4`. The deployment ID was read from the page's own asset URLs.
- **Browser:** Chromium 152 (the browser built into the Claude desktop app, Windows), signed out, with fresh demo
  data (**Reset demo data** in Settings first). Desktop at about 1024 × 768; phone at 375 × 812, emulated.
- **Who:** Claude drove the browser for the project owner. This is an automated walkthrough on the real site, not the
  human rehearsal, which is still to do.

Screenshots are in [`hosted-walkthrough-20261022/`](hosted-walkthrough-20261022/).

| Stop | What was done | What the page showed | Result |
| --- | --- | --- | --- |
| Overview | Clicked **Claim 59% instead** | "Recomputed from all 1,421 events: 57.96%. ✕ Rejected — 59% is not what the log says" ([01](hosted-walkthrough-20261022/01-overview-forged-claim.jpg)) | Pass |
| Moments | Opened the 58′ goal | M-05 · E-1366 · 58:17, preceding corner E-1359 at 58:03 "14 seconds earlier · verified", score 1–1 → 2–1 ([02](hosted-walkthrough-20261022/02-moments.jpg)) | Pass |
| AI insights | Recorded live run, then **Rehearsal** | Live: "Microsoft Foundry via Agent Framework · 2026-10-21", rejected answer retried, C-E1366GS verified, nine versions with the unchecked-tone label. Rehearsal: NC-02 "60% possession" failed (observed 57.96%), revised and passed ([03](hosted-walkthrough-20261022/03-insights-live-run.jpg), [04](hosted-walkthrough-20261022/04-insights-rehearsal.jpg)) | Pass |
| Evidence | Opened CL-0214 | "Checked twice: by the server, and again in your browser from 1,421 events. Both give 57.96%." The browser verifier, now loaded on demand, ran ([05](hosted-walkthrough-20261022/05-evidence.jpg)) | Pass |
| Composer | Removed CL-0216, marked CL-0215 as opinion, then changed 58% to 60% | Eligible after the two fixes. Then CL-0214 showed "Sentence doesn't match the claim · Claim text states a quantity that differs from its assertion" and the draft became Not eligible ([06](hosted-walkthrough-20261022/06-composer-edit-fails.jpg)) | Pass |
| Composer | Touched the CL-0213 sentence without changing its words (space, then backspace) | **It turned from Verified to "Sentence doesn't match the claim · Claim text states a detail the registered metric does not measure"** ([07](hosted-walkthrough-20261022/07-composer-cl0213-finding.jpg)) | **Finding, fixed below** |
| Ask MatchDesk | Asked "Who scored the second goal?" and "How many headers did Okafor score?" | "Lindqvist scored for Riverside at 41:03." Verified, with how it was checked. The header question was declined: "I can't check how a goal or shot was struck…" ([08](hosted-walkthrough-20261022/08-ask-matchdesk.jpg)) | Pass |
| Fan story | Switched to **Español** | The whole story and its checks in Spanish, with the AI-assisted translation notice ([09](hosted-walkthrough-20261022/09-fan-story-es.jpg)) | Pass |
| Phone | Overview at 375 × 812 | No sideways scrolling; bottom tab bar; the Search button wraps to a second header row ([10](hosted-walkthrough-20261022/10-overview-phone.jpg)) | Pass, cosmetic note |

The console was checked on the Moments page: no errors.

## Finding: a draft sentence said more than its claim

D-031's first sentence read "Okafor has scored both Northbridge goals, heading in from a corner at 58:17 to restore the
lead." Its claim, CL-0213, asserts only Okafor's goal count. The composer showed the server's verdict on the claim's own
text ("Okafor scored both Northbridge goals.") until the sentence was edited. Once anyone touched the sentence, the
browser re-checked the words actually shown, and the stricter binding from #145 rightly rejected the corner and header
detail. So the screen showed Verified on a sentence the verifier does not pass.

**Fix:** the draft sentence is now "Okafor has scored both Northbridge goals.", which verifies as written. The header and
corner remain where they are checked: the 58′ moment and the fan story's two event-fact checks. A new browser test
re-enters every factual sentence in the draft and requires it to stay Verified, so a sentence can no longer claim more
than its check.

## Notes

- Pages stream their content in after the first paint. In the desktop app's browser pane, while the pane was hidden,
  that reveal waited for the next drawn frame. A visible browser tab is unaffected: every CI browser run and every
  screenshot here rendered normally.
- Offline use after one visit was not re-tested here, because the pane cannot go offline. It is covered by the hosted
  runtime-browser check on `76de6c4`.
