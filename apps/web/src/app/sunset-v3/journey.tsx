/** Sunset Studio v3 screens 05–07: transparent synthetic event-to-claim journey.
 *
 * These components never call an API, run a model, approve a draft, or assert
 * that the design reference's claim verdicts were reverified by the backend.
 * Source: docs/design-brief.md and docs/design/implementation-guardrails.md.
 */
"use client";

import { useState, type ReactNode } from "react";
import { editorial, fixture, moments, type Moment } from "./demo-data";

type MomentFilter = "all" | "goals" | "cards" | "corners" | "substitutions";
type ClaimId = "CL-0213" | "CL-0214" | "CL-0215" | "CL-0216";
type ReferenceVerdict = "Verified" | "Pending" | "Failed";
type ClaimReference = {
  readonly id: ClaimId;
  readonly statement: string;
  readonly referenceVerdict: ReferenceVerdict;
  readonly evidence: readonly string[];
  readonly metric: string;
  readonly method: string;
  readonly limitation: string;
};

/** The verdicts are from the approved design script, NOT a live verification API. */
const claimReferences: readonly ClaimReference[] = [
  {
    id: "CL-0213",
    statement: "Okafor scored both Northbridge goals",
    referenceVerdict: "Verified",
    evidence: ["E-0688", "E-1366"],
    metric: "Two listed Northbridge goals",
    method: "Compare Okafor's scorer name in E-0688 and E-1366.",
    limitation: "Only the seven named moments are present; the complete event log is not.",
  },
  {
    id: "CL-0214",
    statement: "Northbridge have had 58% possession",
    referenceVerdict: "Verified",
    evidence: [],
    metric: "58% whole-match possession in the approved design script",
    method: "Reference methodology: in-play event calculation, ±1% tolerance. The underlying event sequence was not supplied, so this demo cannot reproduce the calculation.",
    limitation: "Source events are unavailable. The reference verdict cannot be independently rechecked here.",
  },
  {
    id: "CL-0215",
    statement: "Riverside's best spell came from 30–45 minutes",
    referenceVerdict: "Pending",
    evidence: [],
    metric: "Interpretive period assessment",
    method: "Human evaluation and an appropriate time-window source are required.",
    limitation: "A best-spell conclusion is not established by isolated named moments.",
  },
  {
    id: "CL-0216",
    statement: "Okafor's first brace of the season",
    referenceVerdict: "Failed",
    evidence: [],
    metric: "Season-to-date scoring history",
    method: "No reproducible calculation: the synthetic replay contains no season history.",
    limitation: "Do not verify or publish this claim without separate season-level evidence.",
  },
];

const filters: readonly { value: MomentFilter; label: string }[] = [
  { value: "all", label: "All seven moments" },
  { value: "goals", label: "Goals" },
  { value: "cards", label: "Bookings" },
  { value: "corners", label: "Set pieces" },
  { value: "substitutions", label: "Substitutions" },
];

/** The filter only classifies events that actually occur in the reference. */
function matchesFilter(item: Moment, filter: MomentFilter): boolean {
  switch (filter) {
    case "goals": return item.kind === "Goal";
    case "cards": return item.kind === "Yellow card";
    case "corners": return item.kind === "Corner";
    case "substitutions": return item.kind === "Substitution";
    default: return true;
  }
}

/** Accessible status tags always include a text label, never colour alone. */
function ReferenceStatus({ verdict }: { verdict: ReferenceVerdict }) {
  const kind = verdict === "Verified" ? "success" : verdict === "Pending" ? "warning" : "failure";
  const icon = verdict === "Verified" ? "✓" : verdict === "Pending" ? "!" : "×";
  return <span className={`mdv3-status mdv3-${kind}`}>
    <span aria-hidden="true">{icon}</span> Reference: {verdict}
  </span>;
}

/** Screen 05: seven supplied moments, with explanatory detection signals only. */
export function MomentsTimeline({
  score, onOpenIntelligence, onOpenEvidence,
}: {
  score: ReactNode;
  onOpenIntelligence: () => void;
  onOpenEvidence: () => void;
}) {
  const [filter, setFilter] = useState<MomentFilter>("all");
  const [selectedId, setSelectedId] = useState("M-05");
  const visible = moments.filter(item => matchesFilter(item, filter));
  const selected = visible.find(item => item.id === selectedId) ?? visible[0];

  return <div className="mdv3-content">
    <div className="mdv3-page-heading"><div>
      <span className="mdv3-kicker">SUNSET STUDIO / SCREEN 05 OF 14 · SOURCE EVENTS</span>
      <h1>Moments &amp; Timeline</h1>
      <p>Explore the seven named events in this synthetic replay. A detected moment is not a verified tactical interpretation.</p>
    </div><span className="mdv3-status mdv3-planned">ⓘ Recorded synthetic moments</span></div>
    {score}
    <div className="mdv3-journey-summary" role="note">
      <strong>67:12 · Second half · Not live</strong>
      <span>Seven named moments from the reference script; the remaining {fixture.eventCount.toLocaleString("en-GB")} event records are not included in this frontend fixture.</span>
    </div>
    <div className="mdv3-journey-layout">
      <section className="mdv3-panel" aria-label="Recorded match moment timeline">
        <div className="mdv3-head"><h2>Recorded match moments</h2><span className="mdv3-status mdv3-planned">ⓘ 7 named events</span></div>
        <label className="mdv3-journey-filter">Event type
          <select aria-label="Timeline event type" value={filter} onChange={event => setFilter(event.target.value as MomentFilter)}>
            {filters.map(entry => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
          </select>
        </label>
        <ol className="mdv3-timeline" aria-label="Seven canonical moments">
          {visible.map(item => <li key={item.id}>
            <button type="button" className={`mdv3-timeline-entry${selected?.id === item.id ? " mdv3-timeline-selected" : ""}`}
              aria-pressed={selected?.id === item.id} onClick={() => setSelectedId(item.id)}>
              <span className="mdv3-timeline-marker" aria-hidden="true">{item.kind === "Goal" ? "⚽" : item.kind === "Yellow card" ? "▣" : item.kind === "Corner" ? "↗" : "⇄"}</span>
              <span className="mdv3-timeline-clock">{item.clock}<small>{item.id} · {item.event}</small></span>
              <span className="mdv3-timeline-title"><strong>{item.title}</strong><small>{item.kind} · Score {item.scoreAfter}</small></span>
            </button>
          </li>)}
        </ol>
        <p className="mdv3-muted">Named source moments only. No invented intermediate events, player locations, video or confidence scores.</p>
      </section>
      <div className="mdv3-journey-stack">
        <section className="mdv3-panel" role="region" aria-label="Selected synthetic moment details">
          <div className="mdv3-head"><h2>Selected moment</h2><span className="mdv3-status mdv3-planned">ⓘ Source description</span></div>
          {selected ? <>
            <span className="mdv3-mono">{selected.id} · {selected.event} · {selected.clock}</span>
            <h3>{selected.title}</h3><p>{selected.details}</p>
            <p>Recorded score after this moment: <strong>{selected.scoreAfter}</strong></p>
          </> : <p role="status">No named moment matches this filter.</p>}
        </section>
        <section className="mdv3-panel" aria-label="Rule-based moment detection explanation">
          <div className="mdv3-head"><h2>Why this moment was detected</h2><span className="mdv3-status mdv3-planned">ⓘ Deterministic rules</span></div>
          {selected?.id === "M-05" ? <>
            <ol className="mdv3-proof-list">
              <li><strong>Goal event</strong><span>E-1366 · Okafor header at 58:17</span></li>
              <li><strong>Preceding corner</strong><span>E-1359 · Right-side Northbridge corner at 58:03</span></li>
              <li><strong>Temporal relation</strong><span>14 seconds between the named events (within a 15-second review window)</span></li>
              <li><strong>Score change</strong><span>1–1 → 2–1</span></li>
            </ol>
            <p className="mdv3-muted">This is a deterministic explanation of the supplied event sequence, not a measured AI confidence score.</p>
          </> : <p>No additional rule-chain evidence is supplied for this selected moment. Only its logged event type, time and score are shown.</p>}
          <div className="mdv3-journey-actions">
            <button type="button" className="mdv3-secondary" onClick={onOpenEvidence}>Inspect claim evidence →</button>
            <button type="button" className="mdv3-secondary" onClick={onOpenIntelligence}>AI workspace preview →</button>
          </div>
        </section>
        <section className="mdv3-panel mdv3-journey-limits"><h2>Data limits</h2>
          <p>No video, tracking coordinates, defender positions, audio data or CV confidence values are present. Those representations are intentionally excluded.</p>
        </section>
      </div>
    </div>
  </div>;
}

/** Screen 06: five planned workflow stages, without running AI agents. */
export function AIIntelligenceWorkspace({
  score, onOpenEvidence, onOpenTimeline,
}: {
  score: ReactNode;
  onOpenEvidence: () => void;
  onOpenTimeline: () => void;
}) {
  const [attemptedRetry, setAttemptedRetry] = useState(false);
  const stages = ["Analyse", "Compose", "Review", "Adapt", "Human decision"];
  return <div className="mdv3-content">
    <div className="mdv3-page-heading"><div>
      <span className="mdv3-kicker">SUNSET STUDIO / SCREEN 06 OF 14 · OFFLINE PREVIEW</span>
      <h1>AI Intelligence Workspace</h1>
      <p>See how evidence would guide candidate analysis. No model, tool or publication endpoint is connected to this view.</p>
    </div><span className="mdv3-status mdv3-planned">ⓘ Workflow illustration</span></div>
    {score}
    <section className="mdv3-panel mdv3-journey-process" aria-label="Illustrative AI workflow">
      <div className="mdv3-head"><h2>From event to human decision</h2><span className="mdv3-status mdv3-warning">! No agent execution</span></div>
      <ol className="mdv3-journey-steps">{stages.map((stage, index) =>
        <li key={stage}><span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><strong>{stage}</strong><small>{index === 4 ? "Human gate · unavailable" : "Illustrative · not run"}</small></li>
      )}</ol>
    </section>
    <div className="mdv3-journey-layout">
      <section className="mdv3-panel">
        <div className="mdv3-head"><h2>Evidence-linked insight candidates</h2><span className="mdv3-status mdv3-warning">! Needs human review</span></div>
        <div className="mdv3-insight-card">
          <span className="mdv3-kicker">DETERMINISTIC EVENT LINK</span>
          <h3>Okafor's header follows a Northbridge corner</h3>
          <p>E-1359 at 58:03 → E-1366 at 58:17. The goal moves the synthetic score from 1–1 to 2–1.</p>
          <span className="mdv3-status mdv3-planned">ⓘ Source facts, not an AI-generated insight</span>
        </div>
        <div className="mdv3-insight-card">
          <span className="mdv3-kicker">INTERPRETIVE CLAIM · CL-0215</span>
          <h3>Riverside's strongest period</h3>
          <p>A proposed 30–45-minute interpretation is pending human review. The fixture does not supply a validated period-by-period comparison.</p>
          <ReferenceStatus verdict="Pending"/>
        </div>
        <div className="mdv3-insight-card">
          <span className="mdv3-kicker">UNSUPPORTED CLAIM · CL-0216</span>
          <h3>First brace of the season</h3>
          <p>Season-level history is absent; this claim cannot be inferred from the current match event descriptions.</p>
          <ReferenceStatus verdict="Failed"/>
        </div>
        <div className="mdv3-journey-actions">
          <button type="button" className="mdv3-secondary" onClick={onOpenTimeline}>Review source moments →</button>
          <button type="button" className="mdv3-secondary" onClick={onOpenEvidence}>Open evidence explorer →</button>
        </div>
      </section>
      <div className="mdv3-journey-stack">
        <section className="mdv3-panel">
          <div className="mdv3-head"><h2>Draft eligibility</h2><span className="mdv3-status mdv3-warning">! Not approved</span></div>
          <p><strong>{editorial.blockedDraft}</strong> · Okafor double restores Northbridge lead</p>
          <p>{editorial.blockingReason}</p>
          <p><strong>{editorial.eligibleDraft}</strong> · Eligible in design reference; neither approved nor published.</p>
          <button type="button" className="mdv3-secondary" disabled>🔒 Run agent / Approve (Planned)</button>
        </section>
        <section className="mdv3-panel mdv3-journey-issue" role="status" aria-live="polite">
          <div className="mdv3-head"><h2>Temporary issue</h2><span className="mdv3-status mdv3-warning">! Provider unavailable</span></div>
          <p>No AI provider is connected to this local synthetic preview. Existing source facts remain visible, and no data is lost.</p>
          <button type="button" className="mdv3-secondary" onClick={() => setAttemptedRetry(true)}>
            Try again (demo)
          </button>
          {attemptedRetry && <p className="mdv3-journey-retry">Retry request not sent. A trusted backend provider must be configured and tested before this action is enabled.</p>}
        </section>
        <section className="mdv3-panel mdv3-journey-limits"><h2>Human authority</h2>
          <p>Only a separately authenticated producer can make a version-bound decision. This local illustration cannot approve, publish or trigger tools.</p>
        </section>
      </div>
    </div>
  </div>;
}

/** Screen 07: expand immutable source claims while separating verdict layers. */
export function EvidenceVerificationExplorer({
  score, onOpenTimeline,
}: {
  score: ReactNode;
  onOpenTimeline: () => void;
}) {
  const [selectedId, setSelectedId] = useState<ClaimId>("CL-0214");
  const selected = claimReferences.find(claim => claim.id === selectedId) ?? claimReferences[0];

  return <div className="mdv3-content">
    <div className="mdv3-page-heading"><div>
      <span className="mdv3-kicker">SUNSET STUDIO / SCREEN 07 OF 14 · CLAIM PROVENANCE</span>
      <h1>Evidence Verification Explorer</h1>
      <p>Reference claims and their evidence limits. Design-script verdicts do not mean this page has run a server verifier.</p>
    </div><span className="mdv3-status mdv3-planned">ⓘ Read-only evidence reference</span></div>
    {score}
    <div className="mdv3-journey-summary" role="note">
      <strong>{editorial.blockedDraft} · Not eligible</strong>
      <span>{editorial.blockingReason}</span>
    </div>
    <section className="mdv3-panel">
      <div className="mdv3-head"><h2>Claim reference register</h2><span className="mdv3-status mdv3-planned">ⓘ Four design-script claims</span></div>
      <div className="mdv3-claim-scroll">
        <table className="mdv3-claims-table">
          <thead><tr><th scope="col">Claim</th><th scope="col">Reference verdict</th><th scope="col">Named event evidence</th><th scope="col">Inspect</th></tr></thead>
          <tbody>{claimReferences.map(claim => <tr key={claim.id} data-selected={claim.id === selectedId}>
            <th scope="row"><span className="mdv3-mono">{claim.id}</span><small>{claim.statement}</small></th>
            <td><ReferenceStatus verdict={claim.referenceVerdict}/></td>
            <td>{claim.evidence.length ? claim.evidence.join(" · ") : "Not supplied for local replay"}</td>
            <td><button type="button" className="mdv3-secondary" aria-pressed={claim.id === selectedId}
              onClick={() => setSelectedId(claim.id)}>Inspect {claim.id}</button></td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
    {selected && <section className="mdv3-panel mdv3-journey-evidence" role="region" aria-label="Selected claim evidence details">
      <div className="mdv3-head"><h2>Expanded proof chain · {selected.id}</h2><ReferenceStatus verdict={selected.referenceVerdict}/></div>
      <ol className="mdv3-proof-list">
        <li><strong>Claim</strong><span>{selected.statement}</span></li>
        <li><strong>Metric</strong><span>{selected.metric}</span></li>
        <li><strong>Source events</strong><span>{selected.evidence.length
          ? selected.evidence.join(" · ")
          : "Event-level evidence not available in this frontend fixture."}</span></li>
        <li><strong>Calculation</strong><span className="mdv3-proof-calculation">{selected.method}</span></li>
        <li><strong>Result</strong><span>Design-reference verdict: {selected.referenceVerdict}. No independent runtime calculation has been executed.</span></li>
      </ol>
      <div className="mdv3-verdict-grid">
        <div><strong>Structurally valid</strong><span>Typed local claim fixture only; no server validation took place.</span></div>
        <div><strong>Factually verified</strong><span>Not independently evaluated in this preview. Do not infer approval from the reference verdict.</span></div>
      </div>
      <p className="mdv3-journey-limitation"><strong>Evidence limit:</strong> {selected.limitation}</p>
      <div className="mdv3-journey-actions">
        <button type="button" className="mdv3-secondary" onClick={onOpenTimeline}>Back to recorded moments →</button>
        <button type="button" className="mdv3-secondary" disabled>🔒 Approve or publish (Planned)</button>
      </div>
    </section>}
  </div>;
}
