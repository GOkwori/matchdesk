/** Sunset Studio v3 Screen 10 — approval and publication FUTURE-STATE preview.
 *
 * The approved design illustrates a human-governed journey. It does not
 * establish a verified producer, evidence digest, authorisation, approval,
 * destination selection or publication service. This client-only component
 * neither invokes a network API nor performs a privileged action.
 */
"use client";

import { useState, type ReactNode } from "react";
import { editorial, moments } from "./demo-data";

/** A step represents a design diagram, never a backend state transition. */
const conceptSteps = [
  { key: "ready", label: "Ready", kind: "reference", description: "Reference-only condition; not confirmed by a backend" },
  { key: "eligible", label: "Eligible", kind: "highlight", description: "Illustrative eligibility of D-029 v2 only" },
  { key: "approved", label: "Approved", kind: "future", description: "No authenticated human approval" },
  { key: "destination", label: "Destination", kind: "future", description: "No publication destination selected" },
  { key: "published", label: "Published", kind: "future", description: "Nothing published" },
] as const;

/** Use the named synthetic event rather than the mock-up's inconsistent 34' label. */
const equaliser = moments.find(moment => moment.id === "M-03");

export function ReviewPublicationJourney({
  score,
  onBackToComposer,
}: {
  score: ReactNode;
  onBackToComposer: () => void;
}) {
  const [showLimitations, setShowLimitations] = useState(false);

  return <div className="mdv3-content mdv3-publication">
    <header className="mdv3-page-heading">
      <div>
        <span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 10 · SYNTHETIC PREVIEW</span>
        <h1>Review &amp; Publication Journey</h1>
        <p>Visualise the separate human-governed gates from a reference draft to publication.</p>
      </div>
      <span className="mdv3-publication-stamp">Concept · Not live</span>
    </header>
    {score}
    <section className="mdv3-publication-info" role="note" aria-label="Unavailable live workflow">
      <span aria-hidden="true" className="mdv3-publication-info-icon">ⓘ</span>
      <div>
        <strong>Future-state design only</strong>
        <p>Authentication, approval and publication are not connected in the MatchDesk synthetic demo. No workflow decision is recorded.</p>
      </div>
    </section>

    <section className="mdv3-panel mdv3-publication-steps" aria-labelledby="mdv3-publication-steps-title">
      <div className="mdv3-head">
        <h2 id="mdv3-publication-steps-title">Human-governed publication workflow</h2>
        <span className="mdv3-publication-concept">Future state · visual concept</span>
      </div>
      <ol className="mdv3-publication-rail" aria-label="Future-state publication steps — not operational">
        {conceptSteps.map((step, index) =>
          <li key={step.key} className={"mdv3-publication-step mdv3-publication-" + step.kind}
            aria-label={"Step " + (index + 1) + ": " + step.label + ". " + step.description}>
            <span className="mdv3-publication-dot" aria-hidden="true">{index + 1}</span>
            <span className="mdv3-publication-step-label">{step.label}</span>
          </li>)}
      </ol>
      <p className="mdv3-publication-legend">All five stages are illustrative. No stage has been completed in the application.</p>
    </section>

    <div className="mdv3-publication-layout">
      <section className="mdv3-panel mdv3-publication-draft" aria-labelledby="mdv3-publication-draft-title">
        <div className="mdv3-head"><h2 id="mdv3-publication-draft-title">Eligible commentary · {editorial.eligibleDraft}</h2></div>
        <div className="mdv3-publication-draft-heading">
          <div>
            <h3>Riverside level through Lindqvist</h3>
            <p className="mdv3-muted">
              {equaliser
                ? "Synthetic event " + equaliser.event + " · " + equaliser.clock + " · v2 design reference"
                : "Named synthetic source event unavailable · v2 design reference"}
            </p>
          </div>
          <span className="mdv3-publication-label">Reference eligible · Not approved</span>
        </div>
        <div className="mdv3-publication-metrics" aria-label="Illustrative eligibility metrics">
          <div className="mdv3-publication-metric">
            <span>Claims in approved design</span>
            <strong>4 / 4</strong>
            <small>Illustrative, not reverified</small>
          </div>
          <div className="mdv3-publication-metric">
            <span>Evidence digest</span>
            <strong className="mdv3-publication-unavailable">Not computed</strong>
            <small>No authenticated source digest</small>
          </div>
        </div>
        <dl className="mdv3-publication-checklist" aria-label="Current implementation gates">
          <div><dt>Claim verification</dt><dd className="mdv3-publication-reference">Reference only</dd></div>
          <div><dt>Producer authorisation</dt><dd className="mdv3-publication-blocked">Not authenticated</dd></div>
          <div><dt>Human approval</dt><dd className="mdv3-publication-blocked">Not performed</dd></div>
          <div><dt>Publication service</dt><dd className="mdv3-publication-planned">Not deployed</dd></div>
        </dl>
        <button type="button" className="mdv3-primary mdv3-publication-disabled"
          disabled aria-label="Confirm approval unavailable — future state">
          <span aria-hidden="true">🔒</span> Confirm approval · Future state
        </button>
      </section>

      <section className="mdv3-panel mdv3-publication-confirmation" aria-labelledby="mdv3-publication-confirm-title">
        <div className="mdv3-head"><h2 id="mdv3-publication-confirm-title">Custom approval confirmation · design example</h2></div>
        <div className="mdv3-publication-preview" role="group" aria-label="Non-operational approval confirmation example">
          <h3><span aria-hidden="true">◇</span> Approve this commentary?</h3>
          <p>The approved design depicts <strong>{editorial.eligibleDraft}</strong> as eligible with four reference claims. An actual approval would require independent source verification and an authenticated human. <strong>Approval is not publication.</strong></p>
          <div className="mdv3-publication-digest">
            <span>Version-bound evidence digest</span>
            <strong>Unavailable</strong>
          </div>
          <div className="mdv3-publication-preview-actions">
            <button type="button" className="mdv3-secondary"
              aria-expanded={showLimitations}
              aria-controls={showLimitations ? "mdv3-publication-reference-details" : undefined}
              onClick={() => setShowLimitations(value => !value)}>
              {showLimitations ? "Hide evidence requirements" : "Review evidence requirements"}
            </button>
            <button type="button" className="mdv3-primary" disabled>Confirm · Future state</button>
          </div>
          {showLimitations && <div id="mdv3-publication-reference-details"
            className="mdv3-publication-limits" role="note">
            <strong>Missing execution prerequisites</strong>
            <p>No D-029 v2 claim-level verification record, source digest, authenticated producer identity or exact-version approval grant is available. Reviewing this concept cannot create any of them.</p>
          </div>}
        </div>
        <div className="mdv3-publication-info mdv3-publication-second-gate" role="note">
          <span aria-hidden="true" className="mdv3-publication-info-icon">ⓘ</span>
          <div>
            <strong>Publication confirmation is a separate gate</strong>
            <p>Even after authorised human approval, destinations and publication require a further independent policy check and explicit permission. Neither is available here.</p>
          </div>
        </div>
        <button type="button" className="mdv3-secondary mdv3-publication-back" onClick={onBackToComposer}>
          <span aria-hidden="true">←</span> Back to commentary composer
        </button>
      </section>
    </div>
    <section className="mdv3-control-note" aria-label="Publication security boundary">
      <strong>Reference eligibility is not execution authority.</strong>
      <p>This preview cannot authenticate actors, compute an evidence digest, approve a version, select destinations, publish, change a record, or invoke an AI model. Every future server action must independently enforce identity, resource scope, version, permissions and audit.</p>
    </section>
  </div>;
}
