/** Screen 09: local-only editorial composer.
 * Draft changes remain ephemeral UI proposals, not saved or authorised records.
 */
"use client";
import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from "react";
import { editorial } from "./demo-data";

const references = [
  { id: "CL-0213", text: "Okafor scored both Northbridge goals", state: "Reference verified", detail: "E-0688 · E-1366" },
  { id: "CL-0214", text: "Northbridge had 58% possession", state: "Reference verified only", detail: "Underlying event operands not supplied" },
  { id: "CL-0215", text: "Riverside's best spell was 30–45 minutes", state: "Pending", detail: "Interpretation; no qualified period comparison" },
  { id: "CL-0216", text: "Okafor's first brace of the season", state: "Failed", detail: "Season history unavailable" },
] as const;

/** The approved D-031 v3 wording is illustration, never independent verification. */
const INITIAL_HEADLINE = "Okafor double restores Northbridge lead";
const INITIAL_STORY = "Okafor has scored both Northbridge goals to restore the lead in the second half. Northbridge have had 58% possession at the 67:12 replay point. Riverside's strongest pressure spell came before the interval, although that analysis remains pending. A claim that this is Okafor's first brace of the season is unsupported by the available events.";
type ComposerTab = "edit" | "history" | "claims";
type SessionPreview = { readonly revision: number; readonly headline: string; readonly text: string; readonly included: readonly string[] };
const originalClaims = ["CL-0213", "CL-0214", "CL-0215", "CL-0216"] as const;
const composerTabs: readonly { id: ComposerTab; label: string }[] = [
  { id: "edit", label: "Edit draft" },
  { id: "history", label: "Version history" },
  { id: "claims", label: "Claim evidence" },
];

/** Nothing in this component reaches the producer API or persistence layer. */
export function StoryCommentaryComposer({ score, onOpenEvidence, onOpenQueue }:{
  score: ReactNode; onOpenEvidence: () => void; onOpenQueue: () => void;
}) {
  const [headline, setHeadline] = useState(INITIAL_HEADLINE);
  const [text, setText] = useState(INITIAL_STORY);
  const [included, setIncluded] = useState<readonly string[]>(originalClaims);
  const [activeTab, setActiveTab] = useState<ComposerTab>("edit");
  const [preview, setPreview] = useState<SessionPreview | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [discardOpen, setDiscardOpen] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  // Never promote reference claim statuses to the new local content/version.
  const changed = headline !== INITIAL_HEADLINE || text !== INITIAL_STORY ||
    originalClaims.some(id => !included.includes(id));
  const unrecorded = headline !== (preview?.headline ?? INITIAL_HEADLINE) ||
    text !== (preview?.text ?? INITIAL_STORY) ||
    originalClaims.some(id => included.includes(id) !== (preview?.included ?? originalClaims).includes(id));

  /** Focus stays within the custom confirmation dialog; Escape and close restore focus. */
  useEffect(() => {
    if (!discardOpen) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const buttons = Array.from(modalRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
    buttons[0]?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setDiscardOpen(false);
        return;
      }
      if (event.key !== "Tab" || buttons.length === 0) return;
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (!modalRef.current?.contains(document.activeElement)) {
        event.preventDefault(); first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [discardOpen]);

  /** In-memory snapshots are not server saves, canonical draft versions or approval receipts. */
  function capturePreview() {
    if (!unrecorded) return;
    if (!headline.trim() || !text.trim()) {
      setNotice("Headline and story text must not be empty. Nothing was captured.");
      return;
    }
    const revision = (preview?.revision ?? 0) + 1;
    setPreview({ revision, headline, text, included: [...included] });
    setNotice("Local preview r" + revision + " captured in memory. Changes are local, not saved, verified or approved.");
  }

  function confirmDiscard() {
    setHeadline(INITIAL_HEADLINE);
    setText(INITIAL_STORY);
    setIncluded(originalClaims);
    setPreview(null);
    setDiscardOpen(false);
    setNotice("Local edits discarded and reference D-031 v3 restored. No server data changed.");
  }

  function onTabKey(event: ReactKeyboardEvent<HTMLButtonElement>) {
    const keys = composerTabs.map(item => item.id);
    const current = keys.indexOf(activeTab);
    const next = event.key === "ArrowRight" ? (current + 1) % keys.length :
      event.key === "ArrowLeft" ? (current + keys.length - 1) % keys.length :
      event.key === "Home" ? 0 : event.key === "End" ? keys.length - 1 : -1;
    if (next === -1) return;
    event.preventDefault();
    setActiveTab(keys[next]);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }

  return <div className="mdv3-content mdv3-composer">
    <header className="mdv3-page-heading">
      <div><span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 09 · SYNTHETIC PREVIEW</span>
        <h1>Story &amp; Commentary Composer</h1>
        <p>Edit illustrative commentary locally, compare reference versions and inspect claim limitations.</p>
      </div><span className="mdv3-status mdv3-warning">! Editing simulation only</span>
    </header>
    {score}
    <div className="mdv3-composer-warning" role="note">
      <strong>Reverification required</strong>
      <p>{editorial.blockingReason} No approval or publishing action is available.</p>
    </div>
    {notice && <div className="mdv3-composer-message" role="status">
      <p>{notice}</p><button type="button" aria-label="Dismiss composer message" onClick={() => setNotice(null)}>×</button>
    </div>}
    <div className="mdv3-composer-tabs" role="tablist" aria-label="Composer panels">
      {composerTabs.map(item => <button key={item.id} type="button" role="tab"
        id={"mdv3-compose-tab-" + item.id} aria-controls="mdv3-composer-tabpanel"
        aria-selected={activeTab === item.id} tabIndex={activeTab === item.id ? 0 : -1}
        className={activeTab === item.id ? "active" : ""}
        onClick={() => setActiveTab(item.id)} onKeyDown={onTabKey}>{item.label}</button>)}
    </div>
    <div className="mdv3-composer-layout">
      <section className="mdv3-panel mdv3-composer-workspace" id="mdv3-composer-tabpanel"
        role="tabpanel" aria-labelledby={"mdv3-compose-tab-" + activeTab} tabIndex={0}>
        {activeTab === "edit" ? <>
          <div className="mdv3-head"><h2>Commentary draft · {editorial.blockedDraft}</h2></div>
          <div className="mdv3-composer-meta">
            <span className="mdv3-composer-pill">4 design reference claims</span>
            <span className="mdv3-composer-pill mdv3-composer-pending">
              {changed ? (unrecorded ? "Unsaved local edits" : "Captured in memory only") : "Design reference · unchanged"}
            </span>
          </div>
          <label className="mdv3-composer-field">Headline
            <input type="text" maxLength={180} value={headline} onChange={event => {setHeadline(event.target.value);setNotice(null);}}/>
          </label>
          <label className="mdv3-composer-field">Story text (local exploration only)
            <textarea rows={7} maxLength={2400} value={text} onChange={event => {setText(event.target.value);setNotice(null);}}/>
          </label>
          <span className="mdv3-muted">{text.length}/2400 characters · No autosave · All changes require reverification</span>
          <ul className="mdv3-composer-chips" aria-label="Four claim reference statuses">
            {references.map(claim => <li key={claim.id}>
              <span className="mdv3-composer-pill">{claim.id} · {claim.state}</span>
            </li>)}
          </ul>
          <div className="mdv3-journey-actions mdv3-composer-actions">
            <button type="button" className="mdv3-secondary" disabled={!changed} onClick={() => setDiscardOpen(true)}>Discard local changes</button>
            <button type="button" className="mdv3-secondary" onClick={() => setNotice(
              "No server verification performed. Changes are local and will be lost on refresh. Eligibility cannot be upgraded by editing this preview."
            )}>Check demo limitations</button>
            <button type="button" className="mdv3-primary" disabled={!unrecorded} onClick={capturePreview}>Capture session preview</button>
            <button type="button" className="mdv3-secondary" disabled>Save version (Planned)</button>
          </div>
          {preview && <div className="mdv3-composer-capture" role="status">
            <strong>Local preview r{preview.revision}</strong>
            <span>In memory only; refresh discards this snapshot. Reference version remains {editorial.blockedDraft}.</span>
          </div>}
        </> : activeTab === "history" ? <>
          <div className="mdv3-head"><h2>Version history · design reference only</h2></div>
          <p>No durable draft history or verified version transition is loaded in this preview.</p>
          <ol className="mdv3-composer-versions">
            <li><strong>v2 · prior design excerpt</strong><p>The reference describes Riverside dominance, but the claim was unsupported.</p></li>
            <li><strong>v3 · current design reference</strong><p>{INITIAL_HEADLINE}. Four named claims: two reference-verified, one pending and one failed.</p></li>
            {preview && <li><strong>Local preview r{preview.revision}</strong><p>Captured in this browser tab only, not D-031 v4 and not approved.</p></li>}
          </ol>
        </> : <>
          <div className="mdv3-head"><h2>Claim evidence · illustrative references</h2></div>
          <p>These design verdicts do not establish eligibility for any edited text.</p>
          <ul className="mdv3-composer-claims">
            {references.map(claim => <li key={claim.id}>
              <label><input type="checkbox" checked={included.includes(claim.id)}
                onChange={event => {setIncluded(ids => event.target.checked ? [...ids,claim.id] : ids.filter(id => id !== claim.id));setNotice(null);}}/>
                <strong>{claim.id}</strong> {claim.text}</label>
              <small>{claim.state} · {claim.detail}</small>
            </li>)}
          </ul>
          <p className="mdv3-composer-warning" role="note">Including or excluding claims is local UI exploration only. No new verdict or authorisation is created.</p>
        </>}
      </section>
      <aside className="mdv3-panel mdv3-composer-comparison" aria-label="Design reference version comparison">
        <div className="mdv3-head"><h2>Version comparison</h2></div>
        <div className="mdv3-composer-version-row"><span>v2 · prior reference</span><span aria-hidden="true">→</span><span>v3 · current reference</span></div>
        <p className="mdv3-composer-diff">Northbridge have <del>dominated Riverside throughout the match.</del>{" "}
          <ins>scored twice through Okafor to lead 2–1.</ins></p>
        <p className="mdv3-muted">Illustrative approved design excerpt; not a real persisted version diff.</p>
        <h3>Evidence impact · reference only</h3>
        <ul className="mdv3-composer-verdicts">
          <li><span>Goals by scorer</span><span>Reference verified</span></li>
          <li><span>Possession share</span><span>Reference verified</span></li>
          <li><span>Best pressure spell</span><span>Pending</span></li>
          <li><span>Season record</span><span>Failed</span></li>
        </ul>
        <div className="mdv3-composer-warning" role="note"><strong>Reverification required</strong>
          <p>Editing changes the exact content and would require a new immutable source version and independent verification. Previous verdicts do not transfer.</p>
        </div>
        <div className="mdv3-journey-actions">
          <button type="button" className="mdv3-secondary" onClick={onOpenEvidence}>Inspect reference evidence →</button>
          <button type="button" className="mdv3-secondary" onClick={onOpenQueue}>Back to review queue →</button>
          <button type="button" className="mdv3-secondary" disabled>Approve (Planned)</button>
          <button type="button" className="mdv3-secondary" disabled>Publish (Planned)</button>
        </div>
      </aside>
    </div>
    <section className="mdv3-control-note" aria-label="Composer security boundary">
      <strong>AI-assisted. Verified. Human-led.</strong>
      <p>A backend must independently authenticate, authorise and bind every action to the exact version and verified actor. The composer cannot approve, publish, call models or write to a database.</p>
    </section>
    {discardOpen && <div className="mdv3-composer-backdrop">
      <div className="mdv3-composer-dialog" ref={modalRef} role="dialog" aria-modal="true"
        aria-labelledby="mdv3-compose-discard-title" aria-describedby="mdv3-compose-discard-desc">
        <h2 id="mdv3-compose-discard-title">Discard your changes?</h2>
        <p id="mdv3-compose-discard-desc">This will discard local edits and browser-only preview snapshots. No server changes will occur.</p>
        <div className="mdv3-composer-dialog-actions">
          <button type="button" className="mdv3-secondary" onClick={() => setDiscardOpen(false)}>Continue editing</button>
          <button type="button" className="mdv3-composer-danger" onClick={confirmDiscard}>Discard local edits</button>
        </div>
      </div>
    </div>}
  </div>;
}
