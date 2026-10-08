/** A functional contract workbench, not a simulated completed producer console. */
"use client";

import { useRef, useState, type FormEvent } from "react";

/** The response mirrors the exported foundation API; generated typing is a gate item. */
type ValidationResult = {
  event_id: string;
  structurally_valid: true;
  evidence_verified: false;
  content_digest: string;
};

// This invented input demonstrates structure only. It is never a live match result.
const example = JSON.stringify({
  event_id: "m001-e0001", match_id: "m001", sequence: 1,
  period: 1, match_clock_ms: 1000, type: "pass", team_id: "demo-a",
  player_id: "a-08", possession_id: 1, location: { x: 50, y: 30 },
  end_location: { x: 65, y: 35 }, outcome: "complete", tags: ["contract_fixture"],
  synthetic: true,
}, null, 2);

/** Runtime-check the tiny response contract instead of trusting a TypeScript cast. */
function isValidationResult(value: unknown): value is ValidationResult {
  if (typeof value !== "object" || value === null) return false;
  const data = value as Record<string, unknown>;
  return typeof data.event_id === "string" && data.structurally_valid === true &&
    data.evidence_verified === false && typeof data.content_digest === "string" &&
    /^[a-f0-9]{64}$/.test(data.content_digest);
}

/** Validate user-edited synthetic event JSON against the actual Python boundary. */
export default function Workbench() {
  const [input, setInput] = useState(example);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Editing while a request is pending must invalidate that request's eventual result.
  const inputRevision = useRef(0);

  /** Clear stale output and bound the HTTP wait so an unreachable API stays visible. */
  async function validate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submittedRevision = inputRevision.current;
    setError(""); setResult(null); setBusy(true);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      JSON.parse(input); // Catch malformed JSON locally without changing its content.
      const response = await fetch("/api/contracts/event/validate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: input, signal: controller.signal,
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(`Validation failed (HTTP ${response.status}). Check the event contract.`);
      if (!isValidationResult(payload)) throw new Error("The API returned an unexpected response contract.");
      // A response describes only the exact input revision submitted with this request.
      if (inputRevision.current === submittedRevision) setResult(payload);
    } catch (cause) {
      if (inputRevision.current === submittedRevision) {
        setError(cause instanceof Error ? cause.message : "The request could not be completed.");
      }
    } finally {
      clearTimeout(timer); setBusy(false);
    }
  }

  return <main>
    <header><a href="/" className="wordmark" aria-label="MatchDesk home">MatchDesk<span> / FOUNDATION</span></a>
      <p className="stage">Local development · No models connected</p></header>
    <section className="introduction">
      <p className="eyebrow">THE EVIDENCE STARTS HERE</p>
      <h1>Every story starts<br />with an event.</h1>
      <p>MatchDesk is my football production desk. I am building the boundary between
        what happened, what the data supports and what a producer can publish.</p>
    </section>
    <section className="workspace" aria-label="Event contract workbench">
      <form onSubmit={validate}>
        <div className="panel-heading"><h2>Synthetic event</h2><span>Schema 1.0</span></div>
        <label htmlFor="event-json">Edit the JSON and validate its structure</label>
        <textarea id="event-json" spellCheck={false} value={input}
          onChange={(event) => { inputRevision.current += 1; setInput(event.target.value); setResult(null); setError(""); }} />
        <button type="submit" disabled={busy}>{busy ? "Validating…" : "Validate event"}</button>
      </form>
      <aside aria-label="Validation result">
        <h2>Boundary checks</h2>
        <p>Strict identifiers, event-specific fields, clock semantics, immutable content
          and request-size limits.</p>
        <div aria-live="polite" aria-atomic="true" className="result">
          {result ? <><h3>Structure accepted</h3><p>{result.event_id}</p>
            <p className="notice">Not evidence verified. No statistics or narrative have been generated.</p>
            <label>Content SHA-256</label><code>{result.content_digest}</code></> :
            <p>No accepted event selected.</p>}
        </div>
        {error && <p role="alert" className="error">{error}</p>}
        <p className="notice">The simulator, producer queue, evidence verifier and broadcast outputs
          are planned work. This screen does not simulate those features.</p>
      </aside>
    </section>
    <footer>George Okwori · Original synthetic data only · Foundation build, not a production release</footer>
  </main>;
}
