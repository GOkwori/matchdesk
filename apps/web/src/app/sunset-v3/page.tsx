/** Sunset Studio v3 screens 01–02, synthetic-only read-only frontend. */
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CommandCentre, TacticalAnalysis } from "./dashboard";
import { editorial, fixture, latestMoments, matchStatistics } from "./demo-data";
import "./tokens.css";
import "./sunset.css";

type Page = "welcome" | "overview" | "command" | "tactical";
type Notice = "success" | "information" | "warning";

const nav = [
  "Overview", "Matches", "Live Intelligence", "Moments & Timeline",
  "Tactical Analysis", "Evidence & Verification", "Producer Desk",
  "Editorial Review", "Audience Outputs", "Activity & Audit", "Settings & Help",
] as const;

/** Surface a status label with its icon; do not rely on colour alone. */
function Status({ label, kind }: { label: string; kind: "success" | "warning" | "planned" }) {
  const sign = kind === "success" ? "✓" : kind === "warning" ? "!" : "○";
  return <span className={`mdv3-status mdv3-${kind}`}><span aria-hidden="true">{sign}</span> {label}</span>;
}

/** Shared fixture header, never presented as a live or authenticated match. */
function ScoreHeader() {
  return <section className="mdv3-score" aria-label="Synthetic replay score">
    <div className="mdv3-team"><span className="mdv3-crest" aria-hidden="true">N</span>
      <div><strong>{fixture.home}</strong><small>Home · {fixture.homeCode}</small></div></div>
    <div className="mdv3-score-mid"><span className="mdv3-clock">{fixture.clock}</span>
      <strong>{fixture.scoreHome} – {fixture.scoreAway}</strong><small>{fixture.half} · Replay {fixture.replaySpeed}</small></div>
    <div className="mdv3-team mdv3-away"><div><strong>{fixture.away}</strong><small>Away · {fixture.awayCode}</small></div>
      <span className="mdv3-crest mdv3-riv" aria-hidden="true">R</span></div>
  </section>;
}

/** The banner is local dismissible UI, never an operating-system notification. */
function ReplayBanner({ dismiss }: { dismiss: () => void }) {
  return <div className="mdv3-banner" role="status"><span aria-hidden="true">ⓘ</span>
    <div><strong>Synthetic replay</strong><p>Northbridge FC v Riverside United is invented test data replayed from a recorded event log. Not a live match.</p></div>
    <button type="button" className="mdv3-dismiss" onClick={dismiss} aria-label="Dismiss synthetic replay banner">×</button>
  </div>;
}

/** Fixture-driven progress bars cannot imply player-tracking evidence. */
function Statistics() {
  return <section className="mdv3-panel"><div className="mdv3-head"><h2>Match statistics</h2><span className="mdv3-muted">At {fixture.clock} · synthetic</span></div>
    {matchStatistics.map(s => <div className="mdv3-stat" key={s.label}>
      <span>{s.home}{s.suffix ?? ""}</span><span>{s.label}</span><span>{s.away}{s.suffix ?? ""}</span>
      <div className="mdv3-meter" aria-hidden="true"><span style={{width:`${s.home + s.away ? s.home / (s.home + s.away) * 100 : 50}%`}} /></div>
    </div>)}
    <p className="mdv3-muted mdv3-note">Event-log summary only · No tracking data · No xG</p>
  </section>;
}

/** The first two screens deliberately do not call privileged backend APIs. */
export default function SunsetStudioPreview() {
  const [page, setPage] = useState<Page>("welcome");
  const [showBanner, setShowBanner] = useState(true);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [showDialog, setShowDialog] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  /** Keep keyboard focus inside a modal and restore it to its opener on close. */
  useEffect(() => {
    if (!showDialog) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const buttons = Array.from(dialog?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
    buttons[0]?.focus();

    function onDialogKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setShowDialog(false);
        return;
      }
      if (event.key !== "Tab" || buttons.length === 0 || !dialog) return;
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      // A blocked action must never allow focus to leak behind its dialog.
      if (!dialog.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onDialogKey);
    return () => {
      document.removeEventListener("keydown", onDialogKey);
      opener?.focus();
    };
  }, [showDialog]);

  const attention = [
    { icon: "✦", label: "AI insights", number: String(editorial.insightsNeedingReview), state: "Needs human review", kind: "warning" as const },
    { icon: "◇", label: "Verification queue", number: String(editorial.pendingClaims), state: "1 pending claim", kind: "warning" as const },
    { icon: "▦", label: "Producer drafts", number: String(editorial.draftCount), state: "1 not eligible", kind: "warning" as const },
    { icon: "◉", label: "Audience outputs", number: "—", state: "Planned", kind: "planned" as const },
  ];
  return <div className="mdv3" data-theme={theme}>
    <a className="mdv3-skip-link" href="#mdv3-main">Skip to main content</a>
    <div className="mdv3-shell">
      <aside className="mdv3-side" aria-label="Main navigation">
        <Link href="/sunset-v3" className="mdv3-logo" aria-label="MatchDesk Sunset Studio home">Match<span>Desk</span><sup>™</sup></Link>
        <span className="mdv3-side-label">WORKSPACES</span>
        <nav>{nav.map((label, index) => {
          const available = index === 0 || index === 2 || index === 4;
          return available
            ? <button key={label} type="button" aria-label={label} className={`mdv3-nav ${(index === 0 && page === "overview") || (index === 2 && page === "command") || (index === 4 && page === "tactical") ? "active" : ""}`}
                aria-current={(index === 0 && page === "overview") || (index === 2 && page === "command") || (index === 4 && page === "tactical") ? "page" : undefined}
                onClick={() => setPage(index === 0 ? "overview" : index === 2 ? "command" : "tactical")}><span aria-hidden="true">{index === 0 ? "⌂" : "◈"}</span>{label}</button>
            : <div key={label} className="mdv3-nav mdv3-nav-unavailable"><span aria-hidden="true">○</span>{label}
                <span className="mdv3-nav-tag">{index >= 7 ? "Planned" : "Preview"}</span></div>;
        })}</nav>
        <div className="mdv3-side-bottom">✧<p>AI-assisted.<br/>Verified.<br/>Human-led.</p></div>
      </aside>
      <main id="mdv3-main" className="mdv3-main" tabIndex={-1}>
        <header className="mdv3-top">
          <div className="mdv3-top-left"><strong className="mdv3-mobile-brand">Match<span>Desk</span></strong><span>FOOTBALL INTELLIGENCE. EXPLAINED. VERIFIED. READY FOR BROADCAST.</span></div>
          <div className="mdv3-top-right"><span className="mdv3-demo-dot" aria-hidden="true"/>Demo · {fixture.replayDate}
            <label className="mdv3-theme-label">Theme <select aria-label="Display theme" value={theme} onChange={e => setTheme(e.target.value === "light" ? "light" : "dark")}><option value="dark">Dark</option><option value="light">Light</option></select></label></div>
        </header>
        {showBanner && <ReplayBanner dismiss={() => setShowBanner(false)}/>}
        {notice && <div className={`mdv3-inapp mdv3-${notice}`} role="status"><strong>{notice === "success" ? "Demo view updated" : notice === "warning" ? "Approval unavailable" : "Read-only preview"}</strong>
          <span>{notice === "warning" ? "A verified, authenticated producer workflow is required. No change was made." : "These are design-only synthetic values. No server data changed."}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss message">×</button></div>}
        {page === "command" ? <CommandCentre score={<ScoreHeader/>}/> : page === "tactical" ? <TacticalAnalysis score={<ScoreHeader/>} onOpenCommand={() => setPage("command")}/> : page === "welcome" ? <div className="mdv3-content">
          <section className="mdv3-hero"><div className="mdv3-hero-copy"><span className="mdv3-kicker">MATCHDESK · SUNSET STUDIO V3 · SYNTHETIC DEMO</span>
              <h1>Turn football<br/>moments into<br/><em>verifiable stories.</em></h1>
              <p>AI-assisted analysis. Deterministic verification. Human control. Ready for broadcast.</p>
              <div className="mdv3-actions"><button className="mdv3-primary" type="button" onClick={() => {setPage("overview"); setNotice("information");}}>▶ Explore synthetic demo <span aria-hidden="true">→</span></button>
                <button className="mdv3-secondary" type="button" disabled title="Authentication is not enabled">🔒 Sign in (Planned)</button></div>
              <span className="mdv3-muted">Illustrative fixture · {fixture.eventCount.toLocaleString("en-GB")} synthetic events · No live connectivity</span>
            </div><div className="mdv3-hero-graphic" aria-label="Abstract tactical pitch illustration, not player tracking">
              <div className="mdv3-pitch-outline"><div className="mdv3-centre-circle"/><i className="mdv3-node one"/><i className="mdv3-node two"/><i className="mdv3-node three"/><svg viewBox="0 0 320 180" aria-hidden="true"><path d="M55 135 Q105 45 157 100 T270 36" fill="none" stroke="#ff9159" strokeWidth="2" strokeDasharray="6 5"/><path d="M80 58 L178 35 L245 115" fill="none" stroke="#70d8a9" strokeWidth="1.5" opacity=".7"/></svg></div>
              <div className="mdv3-visual-caption">Synthetic event intelligence <span>· No tracking data</span></div>
            </div></section>
          <ScoreHeader/>
          <section className="mdv3-process" aria-label="The human-governed workflow">{[
            {label:"Detect",number:"01",detail:"Inspect recorded synthetic match events"},
            {label:"Verify",number:"02",detail:"Recompute claims from event evidence"},
            {label:"Approve",number:"03",detail:"Reserved for authorised human producers · Planned"},
          ].map(s=><article className="mdv3-panel" key={s.label}><span className="mdv3-kicker">STEP {s.number}</span><h2>{s.label}</h2><p>{s.detail}</p>{s.label==="Approve" && <Status label="Planned" kind="planned"/>}</article>)}</section>
          <div className="mdv3-control-note"><strong>AI-assisted. Verified. Human-led.</strong><p>AI suggestions are not evidence. Publishing and privileged decisions are disabled in this demo.</p></div>
        </div>: <div className="mdv3-content">
          <div className="mdv3-page-heading"><div><span className="mdv3-kicker">MATCH INTELLIGENCE · PREVIEW</span><h1>Intelligence Overview</h1><p>Key events, editorial attention and recorded statistics — all from one synthetic fixture.</p></div>
            <button type="button" className="mdv3-secondary" onClick={()=>setNotice("success")}>↻ Refresh demo view</button></div>
          <ScoreHeader/>
          <div className="mdv3-summary"><span><b>{fixture.eventCount.toLocaleString("en-GB")}</b> Synthetic events</span><span><b>{fixture.latestEvent}</b> Latest at {fixture.latestEventClock}</span><span><Status label="Replay · Not live" kind="warning"/></span></div>
          <div className="mdv3-attention">{attention.map(a=><article className="mdv3-panel mdv3-attention-card" key={a.label}><div className="mdv3-atten-icon" aria-hidden="true">{a.icon}</div><h2>{a.label}</h2><strong className="mdv3-count">{a.number}</strong><Status label={a.state} kind={a.kind}/></article>)}</div>
          <div className="mdv3-grid">
            <section className="mdv3-panel"><div className="mdv3-head"><h2>Attention now</h2><Status label="Human action required" kind="warning"/></div>
              <div className="mdv3-alert-row"><span>1</span><div><strong>Verification pending · CL-0215</strong><p>Riverside’s best spell is an interpretation awaiting producer review.</p></div></div>
              <div className="mdv3-alert-row"><span>2</span><div><strong>Evidence unavailable · CL-0216</strong><p>The event log does not establish Okafor’s first brace of the season.</p></div></div>
              <div className="mdv3-alert-row"><span>3</span><div><strong>{editorial.blockedDraft} · Not eligible</strong><p>{editorial.blockingReason}</p></div></div>
              <button className="mdv3-secondary" type="button" onClick={()=>setShowDialog(true)}>Why is approval blocked?</button>
            </section>
            <section className="mdv3-panel"><div className="mdv3-head"><h2>Latest significant moments</h2><Status label="Synthetic event log" kind="planned"/></div>
              {latestMoments.map(m=><div className="mdv3-moment" key={m.id}><span className="mdv3-mono">{m.clock}</span><div><strong>{m.title}</strong><p>{m.id} · {m.event} · Score {m.scoreAfter}</p></div><span className="mdv3-event-type">{m.kind}</span></div>)}
            </section>
          </div><div className="mdv3-grid"><Statistics/><section className="mdv3-panel"><div className="mdv3-head"><h2>Producer workflow</h2><Status kind="planned" label="No publication enabled"/></div>
            <div className="mdv3-draft"><span className="mdv3-mono">{editorial.blockedDraft}</span><strong>Okafor double restores Northbridge lead</strong><Status kind="warning" label="Not eligible"/></div>
            <div className="mdv3-draft"><span className="mdv3-mono">{editorial.eligibleDraft}</span><strong>Lindqvist levels for Riverside before the break</strong><Status kind="success" label="Eligible · not approved · not published"/></div>
            <p className="mdv3-muted">Eligibility is illustrative. A backend-authorised producer is required before any approval or publication.</p>
            <button type="button" disabled className="mdv3-secondary">🔒 Approve (Planned)</button></section></div>
        </div>}
        <footer className="mdv3-footer"><span>MatchDesk · Synthetic demo · Football intelligence platform</span><span>Analyse · Verify · Create · Inform</span><Link href="/">Original event workbench ↗</Link></footer>
      </main>
    </div>
    <nav className="mdv3-mobile-nav" aria-label="Mobile demo navigation"><button type="button" aria-current={page==="welcome"?"page":undefined} onClick={()=>setPage("welcome")}>⌂<small>Welcome</small></button><button type="button" aria-current={page==="overview"?"page":undefined} onClick={()=>setPage("overview")}>◈<small>Overview</small></button><button type="button" aria-current={page==="command"?"page":undefined} onClick={()=>setPage("command")}>◇<small>Command</small></button><button type="button" aria-current={page==="tactical"?"page":undefined} onClick={()=>setPage("tactical")}>▦<small>Tactical</small></button></nav>
    {showDialog && <div className="mdv3-dialog-backdrop" role="presentation"><div className="mdv3-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="mdv3-dialog-title" aria-describedby="mdv3-dialog-desc">
      <h2 id="mdv3-dialog-title">Approval blocked</h2><p id="mdv3-dialog-desc">{editorial.blockingReason}</p><p>Your work hasn’t been lost. <code>ref: req-7f3a</code></p>
      <div className="mdv3-actions"><button type="button" className="mdv3-primary" onClick={()=>{setShowDialog(false);setNotice("warning");}}>Understood</button><button type="button" className="mdv3-secondary" onClick={()=>setShowDialog(false)}>Close</button></div>
    </div></div>}
  </div>;
}
