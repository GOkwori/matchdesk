/** Screen 14: synthetic-only defensive state catalogue.
 * Samples demonstrate safe UX copy, never actual service errors or permissions.
 * No API, storage, producer mutation or browser-native notifications are used.
 */
"use client";

import { useState } from "react";

type Level = "information" | "attention" | "blocked";
type StateExample = Readonly<{ id: string; title: string; description: string; next: string; level: Level; symbol: string }>;

const examples: readonly StateExample[] = [
  { id: "loading", title: "Loading skeleton", description: "Illustrative loading state. No request is running.", next: "Wait for a real request to complete before presenting data.", level: "information", symbol: "◌" },
  { id: "empty", title: "Empty results", description: "No review items match these example filters.", next: "Review the filters; never invent missing results.", level: "information", symbol: "□" },
  { id: "partial", title: "Partial data", description: "Some example metrics are unavailable.", next: "Keep missing metrics visibly unavailable, rather than estimating them.", level: "attention", symbol: "!" },
  { id: "offline", title: "Offline", description: "Illustrative connection loss. No offline persistence is enabled.", next: "Do not promise saved edits or retry privileged requests automatically.", level: "blocked", symbol: "×" },
  { id: "timeout", title: "API timeout", description: "A request could time out. No actual request was sent.", next: "Check the outcome before safely retrying an idempotent operation.", level: "attention", symbol: "◷" },
  { id: "stale", title: "Stale replay data", description: "A replay event could lag behind the expected clock.", next: "Show the last proven event and stop asserting freshness.", level: "attention", symbol: "◷" },
  { id: "duplicate", title: "Duplicate event", description: "Synthetic event E-1366 was previously recorded in this example.", next: "Avoid a second update and retain the original event reference.", level: "information", symbol: "▣" },
  { id: "invalid", title: "Invalid input", description: "The submitted example would fail schema validation.", next: "Explain the invalid field without echoing sensitive input.", level: "blocked", symbol: "!" },
  { id: "unexpected", title: "Unexpected response", description: "A response contract might not be recognised.", next: "Fail closed; show a safe correlation reference, not raw traces.", level: "blocked", symbol: "×" },
  { id: "session", title: "Expired session", description: "Illustrative session expiry; no login service is connected.", next: "Require fresh authentication; do not claim draft persistence.", level: "attention", symbol: "⌑" },
  { id: "permission", title: "Insufficient permission", description: "The example actor cannot authorise this operation.", next: "Respect server-owned permissions; never unlock an action in the UI.", level: "attention", symbol: "⌑" },
  { id: "conflict", title: "Concurrent edit", description: "Another revision could exist. No shared document is connected.", next: "Compare the authoritative versions before any write.", level: "attention", symbol: "↔" },
  { id: "verification", title: "Verification failed", description: "CL-0216 lacks independent season evidence in this fixture.", next: "Keep the claim failed; approval remains unavailable.", level: "blocked", symbol: "×" },
  { id: "publication", title: "Publication ineligible", description: "D-031 v3 has a pending claim and a failed claim.", next: "Request authenticated review, then independently re-evaluate eligibility.", level: "blocked", symbol: "⌑" },
  { id: "recoverable", title: "Recoverable error", description: "An evidence retrieval could fail. No retrieval occurred.", next: "Retain the source reference and offer a safe, bounded retry.", level: "blocked", symbol: "↻" },
  { id: "preview", title: "Read-only preview", description: "Approval and publishing are unavailable in this synthetic demo.", next: "Explore the sample without making privileged changes.", level: "information", symbol: "◉" },
];

/** The selected state is a local design inspection, not an error event. */
export function DefensiveStates({ onOpenNotifications }: { onOpenNotifications: () => void }) {
  const [selected, setSelected] = useState(examples[0].id);
  const [filter, setFilter] = useState<"all" | Level>("all");
  const [note, setNote] = useState("Local note only — not saved to an account");
  const active = examples.find(example => example.id === selected) ?? examples[0];
  const visible = examples.filter(example => filter === "all" || example.level === filter);

  /** Keep the selected detail inside the currently visible state set. */
  function changeFilter(next: "all" | Level) {
    setFilter(next);
    setSelected(current => {
      const currentExample = examples.find(example => example.id === current);
      if (next === "all" || currentExample?.level === next) return current;
      return examples.find(example => example.level === next)?.id ?? examples[0].id;
    });
  }

  return <div className="mdv3-content mdv3-defensive">
    <header className="mdv3-page-heading">
      <div><span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 14 · SYNTHETIC PREVIEW</span>
        <h1>Defensive States</h1>
        <p>Recoverable, explainable responses for failure, uncertainty, conflict and restricted operations.</p>
      </div>
      <button type="button" className="mdv3-secondary" onClick={onOpenNotifications}>View notification library</button>
    </header>
    <section className="mdv3-panel mdv3-defensive-panel" aria-label="Defensive interface scenarios">
      <div className="mdv3-head"><h2>Defensive interface scenarios · 16 states</h2>
        <label className="mdv3-defensive-filter">Show states
          <select aria-label="Filter defensive states" value={filter} onChange={event => changeFilter(event.target.value as "all" | Level)}>
            <option value="all">All 16</option><option value="information">Information</option>
            <option value="attention">Attention</option><option value="blocked">Blocked</option>
          </select>
        </label>
      </div>
      <div className="mdv3-defensive-grid">
        {visible.map(example => <button type="button" key={example.id}
          className={"mdv3-defensive-card mdv3-defensive-" + example.level}
          aria-pressed={active.id === example.id} onClick={() => setSelected(example.id)}>
          <span className="mdv3-defensive-card-title"><span aria-hidden="true">{example.symbol}</span><strong>{example.title}</strong></span>
          <span className="mdv3-defensive-description">{example.description}</span>
          <span className="mdv3-defensive-tag">{example.level === "information" ? "Information" : example.level === "attention" ? "Attention" : "Blocked / recoverable"}</span>
        </button>)}
      </div>
    </section>
    <section className="mdv3-panel mdv3-defensive-panel" aria-labelledby="mdv3-defensive-selected-title">
      <div className="mdv3-head"><h2 id="mdv3-defensive-selected-title">Inspect a safe recovery response</h2><span className="mdv3-muted">Selected example · No operation executed</span></div>
      <div className={"mdv3-defensive-inspection mdv3-defensive-" + active.level}>
        <strong>{active.title}</strong><p>{active.description}</p>
        <p><b>Safe next step:</b> {active.next}</p>
        <button type="button" disabled className="mdv3-secondary">Execute privileged recovery · Unavailable</button>
      </div>
      <label className="mdv3-defensive-note">Unsaved local example note
        <textarea value={note} onChange={event => setNote(event.target.value)} rows={2} />
      </label>
      <p className="mdv3-muted">The note exists only in this in-memory preview. It is not autosaved, synchronised or transmitted.</p>
    </section>
    <section className="mdv3-panel mdv3-defensive-panel" aria-label="User-centred defensive behaviour">
      <div className="mdv3-head"><h2>User-centred defensive behaviour</h2></div>
      <div className="mdv3-defensive-principles">
        <article><strong>ⓘ Explain the problem</strong><p>Use plain language; never expose raw traces, tokens or implementation secrets.</p></article>
        <article><strong>✓ Preserve work</strong><p>Never claim saved drafts or successful operations without verified persistence evidence.</p></article>
        <article><strong>⚠ Provide a safe next step</strong><p>Retry only when idempotent; do not accidentally repeat privileged actions.</p></article>
      </div>
    </section>
    <section className="mdv3-control-note"><strong>Security boundary</strong><p>Every scenario is a labelled, local-only design example. There are no live service calls, authentication, stored drafts, approval actions, publishing operations or system notifications.</p></section>
  </div>;
}
