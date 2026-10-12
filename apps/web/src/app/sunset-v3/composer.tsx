/** Screen 09: local-only editorial composer.
 * Draft changes remain ephemeral UI proposals, not saved or authorised records.
 */
"use client";
import { useState, type ReactNode } from "react";
import { editorial } from "./demo-data";

type DraftChoice = "D-031 v3" | "D-029 v2";
const references = [
  { id: "CL-0213", text: "Okafor scored both Northbridge goals", state: "Reference verified", detail: "E-0688 · E-1366" },
  { id: "CL-0214", text: "Northbridge had 58% possession", state: "Reference verified only", detail: "Underlying event operands not supplied" },
  { id: "CL-0215", text: "Riverside's best spell was 30–45 minutes", state: "Pending", detail: "Interpretation; no qualified period comparison" },
  { id: "CL-0216", text: "Okafor's first brace of the season", state: "Failed", detail: "Season history unavailable" },
] as const;

/** Nothing in this component reaches the producer API or persistence layer. */
export function StoryCommentaryComposer({ score, onOpenEvidence, onOpenQueue }:{
  score: ReactNode; onOpenEvidence: () => void; onOpenQueue: () => void;
}) {
  const [draft, setDraft] = useState<DraftChoice>("D-031 v3");
  const [text, setText] = useState("Okafor scored twice as Northbridge moved 2–1 ahead in the synthetic replay.");
  const [included, setIncluded] = useState<readonly string[]>(["CL-0213", "CL-0214", "CL-0215", "CL-0216"]);
  const [notice, setNotice] = useState(false);
  const blocked = draft === "D-031 v3";
  const changed = text !== "Okafor scored twice as Northbridge moved 2–1 ahead in the synthetic replay." || included.length !== 4;

  return <div className="mdv3-content mdv3-composer">
    <div className="mdv3-page-heading"><div>
      <span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 09 · SYNTHETIC PREVIEW</span>
      <h1>Story &amp; Commentary Composer</h1>
      <p>Explore editorial changes locally. No draft is saved, reverified, approved or published.</p>
    </div><span className="mdv3-status mdv3-warning">! Editing simulation only</span></div>
    {score}
    <div className="mdv3-journey-summary" role="note"><strong>Human-governed workflow · inactive</strong><span>Every change would require a new immutable version and trusted verification before a human decision.</span></div>
    <div className="mdv3-composer-layout">
      <section className="mdv3-panel">
        <div className="mdv3-head"><h2>Editorial workspace</h2><span className="mdv3-muted">Unsaved local preview</span></div>
        <label className="mdv3-composer-field">Reference draft
          <select value={draft} onChange={e => { setDraft(e.target.value === "D-029 v2" ? "D-029 v2" : "D-031 v3"); setNotice(false); }}>
            <option value="D-031 v3">D-031 v3 · Not eligible</option>
            <option value="D-029 v2">D-029 v2 · Reference eligible only</option>
          </select>
        </label>
        <label className="mdv3-composer-field">Story text (local exploration only)
          <textarea rows={7} maxLength={1200} value={text} onChange={e => { setText(e.target.value); setNotice(false); }}/>
        </label>
        <span className="mdv3-muted">{text.length}/1200 characters · No autosave</span>
        <div className="mdv3-journey-actions">
          <button type="button" className="mdv3-secondary" onClick={() => {setText("Okafor scored twice as Northbridge moved 2–1 ahead in the synthetic replay.");setIncluded(["CL-0213","CL-0214","CL-0215","CL-0216"]);setNotice(false);}}>Reset local changes</button>
          <button type="button" className="mdv3-secondary" onClick={() => setNotice(true)}>Check demo limitations</button>
          <button type="button" className="mdv3-primary" disabled>Save version (Planned)</button>
        </div>
        {notice && <p className="mdv3-composer-warning" role="status">No server verification performed. {changed ? "Changes are local and will be lost on refresh. " : ""}Eligibility cannot be upgraded by editing this preview.</p>}
      </section>
      <section className="mdv3-panel">
        <div className="mdv3-head"><h2>Claims &amp; source limitations</h2><span className="mdv3-status mdv3-warning">{blocked ? "Not eligible" : "Reference eligible only"}</span></div>
        <p>{blocked ? editorial.blockingReason : "D-029 v2 is eligible only in the design reference; claim-level proof is unavailable here."}</p>
        <ul className="mdv3-composer-claims">
          {references.map(claim => <li key={claim.id}>
            <label><input type="checkbox" checked={included.includes(claim.id)}
              onChange={e => setIncluded(ids => e.target.checked ? [...ids, claim.id] : ids.filter(id => id !== claim.id))}/>
              <strong>{claim.id}</strong> {claim.text}</label>
            <small>{claim.state} · {claim.detail}</small>
          </li>)}
        </ul>
        <p className="mdv3-composer-warning" role="note">Removing or including a claim is only a UI example; it does not produce a revised draft, independent verdict or approval.</p>
        <div className="mdv3-journey-actions">
          <button type="button" className="mdv3-secondary" onClick={onOpenEvidence}>Inspect reference evidence →</button>
          <button type="button" className="mdv3-secondary" onClick={onOpenQueue}>Back to review queue →</button>
          <button type="button" className="mdv3-secondary" disabled>Approve (Planned)</button>
          <button type="button" className="mdv3-secondary" disabled>Publish (Planned)</button>
        </div>
      </section>
    </div>
  </div>;
}
