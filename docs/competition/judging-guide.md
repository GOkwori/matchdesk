# MatchDesk judge demonstration readiness

Status: **SYNTHETIC LOCAL WORKBENCH IMPLEMENTED; SUBMISSION ACCEPTANCE NOT COMPLETE**.

The `/judge` page and opt-in loopback host support a fictional deterministic football walkthrough, registered metric verification, a real negative-claim verdict, scripted specialist text, and nine unreviewed language/persona examples. The judge host is disabled by default; it is not a live model run, authenticated producer approval, publication, or production service.

## Reproducible operator walkthrough

1. Follow [local-only setup](judge-loopback-workbench.md) on a trusted workstation.
2. Open `/judge` and choose **Start demo**. Inspect source events and detected match moments.
3. Compare the verified measured claim with the deliberately incorrect `needs_revision` claim. Explain that specialist wording is scripted.
4. Inspect English, Spanish and French examples for the three personas. Fluent human-language acceptance is **NOT RUN**.
5. Choose **Reset**, **Replay** and **End session** to demonstrate revocation and deterministic replay.

[PR #80](https://github.com/GOkwori/matchdesk/pull/80) previously qualified the merged loopback feature with all five exact-head CI groups, including the dedicated localhost browser workflow. Subsequent changes require fresh qualification. No human demo rehearsal or official submission acceptance is recorded.

The remaining release gates include independent assistive-technology/WCAG acceptance, seven exact original Batch 1 PNGs and manifest, live workforce identity/BFF approval, and explicit production or protected-main authorization. No public deployment or video URL is asserted.

See [the demo script](demo-script.md), [traceability](traceability-matrix.md), and [project progress](../PROGRESS.md).
