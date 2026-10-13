/** Screen 13: local-only notification and dialogue design library.
 * A simulated UI action is never an authorised producer mutation.
 */
"use client";
import { useEffect, useRef, useState } from "react";
import { editorial } from "./demo-data";
type Kind = "success" | "information" | "warning" | "error";
type DialogKind = "discard" | "reject" | "approve" | "publish";
const banners: readonly { kind: Kind; title: string; detail: string }[] = [
  { kind: "success", title: "Success · demonstration", detail: "A local UI state was updated. No evidence was verified." },
  { kind: "information", title: "Information · replay context", detail: "You are viewing a recorded synthetic match, not a live fixture." },
  { kind: "warning", title: "Warning · verification needed", detail: "CL-0215 is pending. No editorial approval is available." },
  { kind: "error", title: "Error · recoverable example", detail: "An illustrative request failed. No real request was sent; no work was lost." },
];
const dialogues: readonly { id: DialogKind; title: string; description: string; safe: string; blocked: string }[] = [
  { id: "discard", title: "Discard changes?", description: "Discard the local example edit? Continue editing is the safe default.", safe: "Continue editing", blocked: "Discard local example" },
  { id: "reject", title: "Reject this draft?", description: "A reason would be required in an authenticated producer workflow. This is a preview only.", safe: "Cancel", blocked: "Reject · Unavailable" },
  { id: "approve", title: "Approve draft?", description: "Approval requires a verified actor, policy and evidence. No approval service is connected.", safe: "Review again", blocked: "Approve · Unavailable" },
  { id: "publish", title: "Confirm publication?", description: "Publication requires a separately authorised human decision. No destination is connected.", safe: "Cancel", blocked: "Publish · Unavailable" },
];
export function NotificationDialogueLibrary() {
  const [dismissed, setDismissed] = useState<Kind[]>([]);
  const [active, setActive] = useState<DialogKind | null>(null);
  const [example, setExample] = useState("Unsaved example");
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState("");
  const opener = useRef<HTMLButtonElement | null>(null);
  const dialog = useRef<HTMLDivElement | null>(null);
  const current = dialogues.find(item => item.id === active);
  function close() { setActive(null); setReason(""); }
  useEffect(() => {
    if (!active) return;
    const panel = dialog.current;
    const focusables = () => Array.from(panel?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), textarea:not(:disabled)') ?? []);
    focusables()[0]?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); close(); return; }
      if (event.key !== "Tab") return;
      const items = focusables(); if (!items.length) { event.preventDefault(); return; }
      const first = items[0], last = items[items.length - 1];
      if (!panel?.contains(document.activeElement)) { event.preventDefault(); first.focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", keydown);
    return () => { document.removeEventListener("keydown", keydown); opener.current?.focus(); };
  }, [active]);
  return <div className="mdv3-content mdv3-notifications">
    <header className="mdv3-page-heading"><div><span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 13 · SYNTHETIC PREVIEW</span><h1>Notification &amp; Dialogue Library</h1><p>Branded, accessible in-app feedback. No browser alerts or operating-system notifications.</p></div></header>
    <div className="mdv3-notice-grid">
      <section className="mdv3-panel"><div className="mdv3-head"><h2>Custom in-app notification banners</h2></div>
        <div className="mdv3-notice-stack">{banners.filter(item => !dismissed.includes(item.kind)).map(item =>
          <div key={item.kind} className={"mdv3-notice-card mdv3-notice-" + item.kind} role={item.kind === "error" ? "alert" : "status"}>
            <span aria-hidden="true">{item.kind === "success" ? "✓" : item.kind === "information" ? "ⓘ" : item.kind === "warning" ? "⚠" : "×"}</span>
            <div><strong>{item.title}</strong><p>{item.detail}</p></div>
            {item.kind === "success" || item.kind === "information" ? <button type="button" onClick={() => setDismissed(previous => [...previous, item.kind])} aria-label={"Dismiss " + item.kind + " example"}>Dismiss</button> : <span className="mdv3-notice-required">Acknowledgement required</span>}
          </div>)}</div>
        <button className="mdv3-secondary" type="button" onClick={() => setDismissed([])}>Reset banner examples</button>
        <p className="mdv3-muted">Critical warning and error examples remain visible. Colour is never the only status cue.</p>
      </section>
      <section className="mdv3-panel"><div className="mdv3-head"><h2>Light/dark semantic preview</h2></div>
        <p>These semantic banners inherit the active MatchDesk theme. The labels, icons and meanings remain unchanged.</p>
        <div className="mdv3-notice-legend">{banners.map(item => <span className={"mdv3-notice-legend-" + item.kind} key={item.kind}>{item.kind}</span>)}</div>
        <p className="mdv3-muted">Design-only components. No delivery, alerts, telemetry or account notifications are configured.</p>
      </section>
    </div>
    <section className="mdv3-panel"><div className="mdv3-head"><h2>Custom confirmation dialogue variants</h2></div>
      <div className="mdv3-notice-dialog-grid">{dialogues.map(item => <article key={item.id} className="mdv3-notice-dialog-card"><h3>{item.title}</h3><p>{item.description}</p>
        <button type="button" className="mdv3-secondary" onClick={event => { opener.current = event.currentTarget; setActive(item.id); }}>{item.id === "discard" ? "Try local discard" : "Inspect safe dialogue"}</button>
      </article>)}</div>
      <p className="mdv3-muted">The approve, reject and publish controls remain disabled even when a dialogue is opened. A UI confirmation is never an authorisation boundary.</p>
    </section>
    <div role="status" aria-live="polite" className="mdv3-notice-feedback">{feedback}</div>
    {current && <div className="mdv3-notice-backdrop"><div className="mdv3-notice-modal" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="mdv3-notice-title" aria-describedby="mdv3-notice-description">
      <h2 id="mdv3-notice-title">{current.title}</h2><p id="mdv3-notice-description">{current.description}</p>
      {active === "discard" && <label>Local example edit<input value={example} onChange={event => setExample(event.target.value)}/></label>}
      {active === "reject" && <label>Rejection reason (preview only)<textarea value={reason} onChange={event => setReason(event.target.value)} placeholder="Reason is required in a real workflow"/></label>}
      {active === "approve" && <p className="mdv3-muted">{editorial.blockedDraft} is ineligible; no authenticated approval is possible.</p>}
      <div className="mdv3-notice-actions"><button type="button" className="mdv3-secondary" onClick={close}>{current.safe}</button>
        {active === "discard" ? <button type="button" className="mdv3-primary" onClick={() => { setExample(""); setFeedback("Local example cleared. No saved draft was changed."); close(); }}>Discard local example</button>
          : <button type="button" className="mdv3-primary" disabled>{current.blocked}</button>}
      </div>
    </div></div>}
    <section className="mdv3-control-note"><strong>Security boundary</strong><p>All feedback and dialogues are local-only demonstrations. No browser-native confirmation, producer authorisation, review mutation, publishing or external notification service is invoked.</p></section>
  </div>;
}
