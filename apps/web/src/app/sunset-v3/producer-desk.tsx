/** Sunset Studio v3 screen 08: synthetic producer review queue.
 *
 * Reference eligibility is taken from the approved design, not from a
 * verifier, authenticated actor, durable draft store or publishing service.
 * Filtering and inspecting only change local React state.
 */
"use client";

import { useState, type ReactNode } from "react";
import { editorial } from "./demo-data";

type QueueFilter = "all" | "blocked" | "eligible" | "reviewed";
type QueueSort = "recent" | "eligibility";
type ReferenceEligibility = "blocked" | "eligible";
type ReferenceVerdict = "Verified" | "Pending" | "Failed";

type ReferenceClaim = {
  readonly id: string;
  readonly statement: string;
  readonly verdict: ReferenceVerdict;
  readonly evidence: string;
};

type ReferenceDraft = {
  readonly key: string;
  readonly title: string;
  readonly eligibility: ReferenceEligibility;
  readonly summary: string;
  readonly detail: string;
  readonly claims: readonly ReferenceClaim[] | null;
};

/** Only design-supplied claims appear here; no synthetic approval receipts,
 * imaginary evidence hashes or inferred matching event coordinates are added.
 */
const blockedClaims: readonly ReferenceClaim[] = [
  {
    id: "CL-0213",
    statement: "Okafor scored both Northbridge goals",
    verdict: "Verified",
    evidence: "Named events E-0688 and E-1366 appear in the synthetic fixture.",
  },
  {
    id: "CL-0214",
    statement: "Northbridge had 58% possession",
    verdict: "Verified",
    evidence: "Reference verdict only: source-event operands were not supplied.",
  },
  {
    id: "CL-0215",
    statement: "Riverside's best spell was 30–45 minutes",
    verdict: "Pending",
    evidence: "Interpretive claim awaiting a suitable source and human assessment.",
  },
  {
    id: "CL-0216",
    statement: "Okafor's first brace of the season",
    verdict: "Failed",
    evidence: "No season history is present; this claim cannot be established.",
  },
];

const drafts: readonly ReferenceDraft[] = [
  {
    key: editorial.blockedDraft,
    title: "Okafor double restores Northbridge lead",
    eligibility: "blocked",
    summary: "2 reference verified · 1 pending · 1 failed",
    detail: "Four named claims in the approved design reference. This version is not eligible for approval.",
    claims: blockedClaims,
  },
  {
    key: editorial.eligibleDraft,
    title: "Riverside level through Lindqvist",
    eligibility: "eligible",
    summary: "4 of 4 reference verified",
    detail: "The design marks this version eligible; its claim-level operands are not supplied here. It is neither approved nor published.",
    claims: null,
  },
];

const tabs: readonly { value: QueueFilter; label: string }[] = [
  { value: "all", label: "All drafts" },
  { value: "blocked", label: "Not eligible" },
  { value: "eligible", label: "Reference eligible" },
  { value: "reviewed", label: "Reviewed" },
];

/** Reference badges deliberately do not assert a backend verification result. */
function ReferencePill({ eligibility }: { eligibility: ReferenceEligibility }) {
  return <span className={`mdv3-producer-pill mdv3-producer-${eligibility}`}>
    <span aria-hidden="true">{eligibility === "eligible" ? "✓" : "!"}</span>
    {eligibility === "eligible" ? "Eligible in design only" : "Not eligible"}
  </span>;
}

function ClaimBadge({ verdict }: { verdict: ReferenceVerdict }) {
  const kind = verdict === "Verified" ? "eligible" : verdict === "Pending" ? "pending" : "blocked";
  return <span className={`mdv3-producer-pill mdv3-producer-${kind}`}>
    {verdict === "Verified" ? "Reference verified" : verdict === "Pending" ? "Pending" : "Failed"}
  </span>;
}

/** ScoreHeader is a shared source-labelled fixture component from the shell. */
export function ProducerReviewQueue({
  score, onOpenEvidence,
}: {
  score: ReactNode;
  onOpenEvidence: () => void;
}) {
  const [filter, setFilter] = useState<QueueFilter>("all");
  const [sort, setSort] = useState<QueueSort>("recent");
  const [selectedKey, setSelectedKey] = useState<string>(editorial.blockedDraft);

  const visible = drafts
    .filter(draft => filter === "all" ||
      (filter === "blocked" && draft.eligibility === "blocked") ||
      (filter === "eligible" && draft.eligibility === "eligible"))
    .sort((a, b) => sort === "recent" ? 0 :
      Number(b.eligibility === "eligible") - Number(a.eligibility === "eligible"));
  // A filtered-out selection may not remain visible in the inspection pane.
  const selected = visible.find(draft => draft.key === selectedKey) ?? visible[0];

  return <div className="mdv3-content mdv3-producer">
    <header className="mdv3-page-heading">
      <div><span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 08 · SYNTHETIC PREVIEW</span>
        <h1>Producer Review Queue</h1>
        <p>Inspect draft versions and reference eligibility, without granting producer authority.</p></div>
      <span className="mdv3-producer-pill mdv3-producer-pending">Read-only concept</span>
    </header>
    {score}
    <section className="mdv3-producer-summary" aria-label="Reference draft summary">
      <article className="mdv3-panel"><span>Awaiting consideration</span>
        <strong>{drafts.length}</strong><small>Illustrative producer drafts</small></article>
      <article className="mdv3-panel"><span>Eligible in reference</span>
        <strong>{drafts.filter(draft => draft.eligibility === "eligible").length}</strong>
        <small>No authenticated approval</small></article>
      <article className="mdv3-panel"><span>Not eligible</span>
        <strong>{drafts.filter(draft => draft.eligibility === "blocked").length}</strong>
        <small>Pending or unsupported claims</small></article>
    </section>
    <div className="mdv3-producer-grid">
      <section className="mdv3-panel" aria-labelledby="mdv3-producer-queue-title">
        <div className="mdv3-head"><h2 id="mdv3-producer-queue-title">Review queue</h2>
          <span className="mdv3-muted">Local selection only</span></div>
        <div className="mdv3-producer-tabs" role="group" aria-label="Filter producer drafts">
          {tabs.map(tab => <button key={tab.value} type="button"
            className={filter === tab.value ? "active" : ""}
            aria-pressed={filter === tab.value} onClick={() => setFilter(tab.value)}>
            {tab.label}</button>)}
        </div>
        <div className="mdv3-producer-queue-tools">
          <span className="mdv3-muted" role="status">Showing {visible.length} synthetic drafts</span>
          <label>Sort <select aria-label="Sort producer drafts" value={sort}
            onChange={event => setSort(event.target.value === "eligibility" ? "eligibility" : "recent")}>
            <option value="recent">Reference order</option>
            <option value="eligibility">Reference eligibility</option>
          </select></label>
        </div>
        {visible.length === 0 ? <p className="mdv3-producer-empty" role="status">
          No reviewed drafts are supplied by this synthetic fixture. Nothing has been approved.
        </p> : <div className="mdv3-producer-table-scroll">
          <table className="mdv3-producer-table" role="table" aria-label="Synthetic producer review queue">
            <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Draft</th><th scope="col" role="columnheader">Verification reference</th>
              <th scope="col" role="columnheader">Eligibility</th><th scope="col" role="columnheader">Inspect</th></tr></thead>
            <tbody role="rowgroup">{visible.map(draft => <tr role="row" key={draft.key} data-selected={selected?.key === draft.key}>
              <th scope="row" role="rowheader"><strong>{draft.key}</strong>
                <span>{draft.title}</span></th>
              <td role="cell" data-label="Verification reference">{draft.summary}</td>
              <td role="cell" data-label="Eligibility"><ReferencePill eligibility={draft.eligibility}/></td>
              <td role="cell" data-label="Action"><button type="button" className="mdv3-secondary"
                aria-label={`Inspect ${draft.key}`}
                onClick={() => setSelectedKey(draft.key)}>Inspect</button></td>
            </tr>)}</tbody>
          </table>
        </div>}
      </section>
      <section className="mdv3-panel mdv3-producer-inspector" role="region"
        aria-label="Selected draft inspection">
        {selected ? <>
          <div className="mdv3-head"><h2>Draft inspection · {selected.key}</h2></div>
          <div className="mdv3-producer-selection"><strong>{selected.title}</strong>
            <ReferencePill eligibility={selected.eligibility}/></div>
          <p>{selected.detail}</p>
          {selected.claims ? <>
            <h3>Claim reference register</h3>
            <ul className="mdv3-producer-claims">
              {selected.claims.map(claim => <li key={claim.id}>
                <div><strong>{claim.id}</strong><span>{claim.statement}</span></div>
                <ClaimBadge verdict={claim.verdict}/>
                <small>{claim.evidence}</small>
              </li>)}
            </ul>
            <div className="mdv3-producer-warning" role="note">
              <strong>Approval blocked</strong>
              <p>{editorial.blockingReason} Reference verdicts do not substitute for independent server verification.</p>
            </div>
          </> : <div className="mdv3-producer-warning" role="note">
            <strong>Design-only eligibility</strong>
            <p>No claim-level source records or version-bound authorisation were supplied for {selected.key}.</p>
          </div>}
          <div className="mdv3-producer-actions">
            <button type="button" className="mdv3-secondary"
              disabled={!selected.claims} onClick={onOpenEvidence}>
              Inspect reference evidence</button>
            <button type="button" className="mdv3-primary" disabled>
              Approve · Unavailable</button>
          </div>
          <p className="mdv3-muted">No edit, approval, rejection, publication or persistence is enabled.</p>
        </> : <p className="mdv3-producer-empty">Choose an available draft to inspect its reference state.</p>}
      </section>
    </div>
    <section className="mdv3-control-note" aria-label="Producer review safety boundary">
      <strong>Reference eligibility is not execution authority.</strong>
      <p>Approval requires authenticated human identity, exact draft version, independently checked evidence,
        write-time server authorisation and an auditable decision. Publication is a separate gated operation.</p>
    </section>
  </div>;
}
