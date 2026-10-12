/** Sunset Studio v3 screens 01–11: synthetic-only, independently gated frontend. */
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { CommandCentre, TacticalAnalysis } from "./dashboard";
import { AIIntelligenceWorkspace, EvidenceVerificationExplorer, MomentsTimeline } from "./journey";
import { ProducerReviewQueue } from "./producer-desk";
import { StoryCommentaryComposer } from "./composer";
import { ReviewPublicationJourney } from "./publication";
import { AudienceExperience } from "./audience";
import { editorial, fixture, latestMoments, matchStatistics } from "./demo-data";
import "./tokens.css";
import "./sunset.css";
import "./journey.css";
import "./producer-desk.css";
import "./composer.css";
import "./publication.css";
import "./audience.css";

type Page = "welcome" | "overview" | "command" | "tactical" | "moments" | "ai" | "evidence" | "producer" | "composer" | "publication" | "audience";
type Notice = "success" | "information" | "warning";

const nav = [
  "Overview", "Matches", "Live Intelligence", "Moments & Timeline",
  "Tactical Analysis", "Evidence & Verification", "AI Intelligence Workspace", "Producer Desk",
  "Editorial Review", "Audience Outputs", "Activity & Audit", "Settings & Help",
] as const;

/** Map approved, implemented demo screens to local client-only views.
 * Unmapped features have no clickable placeholder links or API permissions.
 */
const demoDestinations: Partial<Record<(typeof nav)[number], Page>> = {
  "Overview": "overview",
  "Live Intelligence": "command",
  "Moments & Timeline": "moments",
  "Tactical Analysis": "tactical",
  "Evidence & Verification": "evidence",
  "AI Intelligence Workspace": "ai",
  "Producer Desk": "producer",
  "Editorial Review": "composer",
  "Audience Outputs": "audience",
};

/** Every quick destination is an implemented local synthetic-only screen. */
const mobileDestinations: readonly { label: string; target: Page }[] = [
  { label: "Welcome & Access", target: "welcome" },
  { label: "Intelligence Overview", target: "overview" },
  { label: "Match Intelligence", target: "command" },
  { label: "Moments & Timeline", target: "moments" },
  { label: "Tactical Analysis", target: "tactical" },
  { label: "AI Intelligence Workspace", target: "ai" },
  { label: "Evidence Verification", target: "evidence" },
  { label: "Producer Review Queue", target: "producer" },
  { label: "Story & Commentary Composer", target: "composer" },
  { label: "Review & Publication Journey", target: "publication" },
  { label: "Audience Experience", target: "audience" },
];

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
  const [moreOpen, setMoreOpen] = useState(false);
  const moreTriggerRef = useRef<HTMLButtonElement>(null);
  const morePanelRef = useRef<HTMLElement>(null);

  /** Dismiss the optional navigation region on Escape or outside click.
   * It is not modal: background navigation is still available.
   */
  useEffect(() => {
    if (!moreOpen) return;
    morePanelRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setMoreOpen(false);
      }
    }
    function onOutside(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (!morePanelRef.current?.contains(target) && !moreTriggerRef.current?.contains(target)) {
        setMoreOpen(false);
      }
    }
    document.addEventListener("keydown", onEscape);
    document.addEventListener("pointerdown", onOutside);
    return () => {
      document.removeEventListener("keydown", onEscape);
      document.removeEventListener("pointerdown", onOutside);
      // A dismissed menu must not strand the keyboard focus.
      if (document.activeElement === document.body) moreTriggerRef.current?.focus();
    };
  }, [moreOpen]);

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
        <Link href="/sunset-v3" className="mdv3-logo" aria-label="MatchDesk Sunset Studio home"><span className="mdv3-brand-emblem" aria-hidden="true">⌃</span>Match<span>Desk</span><sup>™</sup></Link>
        <span className="mdv3-side-label">WORKSPACES</span>
        <nav>{nav.map(label => {
          const destination = demoDestinations[label];
          return destination
            ? <button key={label} type="button" aria-label={label}
                className={`mdv3-nav ${page === destination || (page === "publication" && destination === "composer") ? "active" : ""}`}
                aria-current={page === destination || (page === "publication" && destination === "composer") ? "page" : undefined}
                onClick={() => setPage(destination)}>
                <span aria-hidden="true">{label === "Overview" ? "⌂" : "◈"}</span>{label}
              </button>
            : <div key={label} className="mdv3-nav mdv3-nav-unavailable">
                <span aria-hidden="true">○</span>{label}<span className="mdv3-nav-tag">Planned</span>
              </div>;
        })}</nav>
        <div className="mdv3-side-bottom">✧<p>AI-assisted.<br/>Verified.<br/>Human-led.</p></div>
      </aside>
      <main id="mdv3-main" className="mdv3-main" tabIndex={-1}>
        <header className="mdv3-top">
          <div className="mdv3-top-left"><strong className="mdv3-mobile-brand"><span className="mdv3-brand-emblem" aria-hidden="true">⌃</span>Match<span>Desk</span></strong><span>FOOTBALL INTELLIGENCE. EXPLAINED. VERIFIED. READY FOR BROADCAST.</span></div>
          <div className="mdv3-top-right"><span className="mdv3-demo-dot" aria-hidden="true"/>Demo · {fixture.replayDate}
            <label className="mdv3-theme-label">Theme <select aria-label="Display theme" value={theme} onChange={e => setTheme(e.target.value === "light" ? "light" : "dark")}><option value="dark">Dark</option><option value="light">Light</option></select></label></div>
        </header>
        {showBanner && <ReplayBanner dismiss={() => setShowBanner(false)}/>}
        {notice && <div className={`mdv3-inapp mdv3-${notice}`} role="status"><strong>{notice === "success" ? "Demo view updated" : notice === "warning" ? "Approval unavailable" : "Read-only preview"}</strong>
          <span>{notice === "warning" ? "A verified, authenticated producer workflow is required. No change was made." : "These are design-only synthetic values. No server data changed."}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss message">×</button></div>}
        {page === "audience" ? <AudienceExperience onOpenEvidence={() => setPage("evidence")}/>
          : page === "publication" ? <ReviewPublicationJourney score={<ScoreHeader/>} onBackToComposer={() => setPage("composer")}/>
          : page === "composer" ? <StoryCommentaryComposer score={<ScoreHeader/>} onOpenEvidence={() => setPage("evidence")} onOpenQueue={() => setPage("producer")} onOpenPublication={() => setPage("publication")}/> : page === "moments" ? <MomentsTimeline score={<ScoreHeader/>}
          onOpenIntelligence={() => setPage("ai")} onOpenEvidence={() => setPage("evidence")}/>
          : page === "ai" ? <AIIntelligenceWorkspace score={<ScoreHeader/>}
            onOpenEvidence={() => setPage("evidence")} onOpenTimeline={() => setPage("moments")}/>
          : page === "evidence" ? <EvidenceVerificationExplorer score={<ScoreHeader/>}
            onOpenTimeline={() => setPage("moments")}/>
          : page === "producer" ? <ProducerReviewQueue score={<ScoreHeader/>} onOpenEvidence={() => setPage("evidence")}/>
          : page === "command" ? <CommandCentre score={<ScoreHeader/>}/> : page === "tactical" ? <TacticalAnalysis score={<ScoreHeader/>} onOpenCommand={() => setPage("command")}/> : page === "welcome" ? <div className="mdv3-content">
          <section className="mdv3-hero"><div className="mdv3-hero-copy"><span className="mdv3-kicker">MATCHDESK · SUNSET STUDIO V3 · SYNTHETIC DEMO</span>
              <h1>Turn football<br/>moments into<br/><em>verifiable stories.</em></h1>
              <p>AI-assisted analysis. Deterministic verification. Human control. Ready for broadcast.</p>
              <div className="mdv3-actions"><button className="mdv3-primary" type="button" onClick={() => {setPage("overview"); setNotice("information");}}>▶ Explore synthetic demo <span aria-hidden="true">→</span></button>
                <button className="mdv3-secondary" type="button" disabled title="Authentication is not enabled">🔒 Sign in (Planned)</button></div>
              <span className="mdv3-muted">Illustrative fixture · {fixture.eventCount.toLocaleString("en-GB")} synthetic events · No live connectivity</span>
            </div><div className="mdv3-hero-graphic" role="group" aria-label="Illustrative pitch and recorded synthetic event; no tracking data">
              <div className="mdv3-graphic-heading"><span className="mdv3-kicker">SOURCE-LED INTELLIGENCE</span><span className="mdv3-graphic-clock">{fixture.clock} · REPLAY</span></div>
              <div className="mdv3-pitch-outline" aria-hidden="true">
                <div className="mdv3-centre-circle"/>
                <div className="mdv3-pitch-end mdv3-pitch-end-left"/>
                <div className="mdv3-pitch-end mdv3-pitch-end-right"/>
              </div>
              {latestMoments.filter(moment => moment.id === "M-05").map(moment => <div className="mdv3-hero-event" key={moment.id}>
                <span className="mdv3-hero-event-icon" aria-hidden="true">↗</span>
                <div><span className="mdv3-kicker">RECORDED MATCH EVENT</span><strong>{moment.id} · {moment.event} · {moment.clock}</strong><small>{moment.title}</small></div>
              </div>)}
              <div className="mdv3-visual-caption"><span><strong>Illustrative pitch</strong> · No tracking data, player positions or shot coordinates</span><span className="mdv3-illustration-chip">SYNTHETIC</span></div>
            </div></section>
          <ScoreHeader/>
          <section className="mdv3-process" aria-label="The human-governed workflow">{[
            {label:"Detect",number:"01",detail:"Inspect recorded synthetic match events"},
            {label:"Verify",number:"02",detail:"Recompute claims from event evidence"},
            {label:"Approve",number:"03",detail:"Reserved for authorised human producers · Planned"},
          ].map(step => <article className="mdv3-panel mdv3-step" key={step.number}>
            <span className="mdv3-step-number" aria-hidden="true">{step.number}</span>
            <div><span className="mdv3-kicker">STEP {step.number}</span><h2>{step.label}</h2><p>{step.detail}</p>
              {step.label === "Approve" && <Status label="Planned" kind="planned"/>}</div>
          </article>)}</section>
          <div className="mdv3-control-note"><strong>AI-assisted. Verified. Human-led.</strong><p>AI suggestions are not evidence. Publishing and privileged decisions are disabled in this demo.</p></div>
        </div>: <div className="mdv3-content">
          <div className="mdv3-page-heading"><div><span className="mdv3-kicker">MATCH INTELLIGENCE · PREVIEW</span><h1>Intelligence Overview</h1><p>Key events, editorial attention and recorded statistics — all from one synthetic fixture.</p></div>
            <button type="button" className="mdv3-secondary" onClick={()=>setNotice("success")}>↻ Refresh demo view</button></div>
          <ScoreHeader/>
          <div className="mdv3-summary"><span><b>{fixture.eventCount.toLocaleString("en-GB")}</b> Synthetic events</span><span><b>{fixture.latestEvent}</b> Latest at {fixture.latestEventClock}</span><span><Status label="Replay · Not live" kind="warning"/></span></div>
          <div className="mdv3-attention">{attention.map(a=><article className={`mdv3-panel mdv3-attention-card mdv3-attention-${a.kind}`} key={a.label}><div className="mdv3-atten-icon" aria-hidden="true">{a.icon}</div><h2>{a.label}</h2><strong className="mdv3-count">{a.number}</strong><Status label={a.state} kind={a.kind}/></article>)}</div>
          <div className="mdv3-grid">
            <section className="mdv3-panel mdv3-editorial-watch"><div className="mdv3-head"><h2>Attention now</h2><Status label="Human action required" kind="warning"/></div>
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
    <nav className="mdv3-mobile-nav" aria-label="Mobile demo navigation">
      <div className="mdv3-mobile-nav-scroll" aria-label="Swipeable demo shortcuts">
        <button type="button" aria-current={page==="welcome"?"page":undefined} onClick={()=>setPage("welcome")}>⌂<small>Welcome</small></button><button type="button" aria-current={page==="overview"?"page":undefined} onClick={()=>setPage("overview")}>◈<small>Overview</small></button><button type="button" aria-current={page==="command"?"page":undefined} onClick={()=>setPage("command")}>◇<small>Command</small></button><button type="button" aria-current={page==="tactical"?"page":undefined} onClick={()=>setPage("tactical")}>▦<small>Tactical</small></button>
      <button type="button" aria-current={page==="moments"?"page":undefined} onClick={()=>setPage("moments")}>◷<small>Moments</small></button>
      <button type="button" aria-current={page==="ai"?"page":undefined} onClick={()=>setPage("ai")}>✦<small>AI Desk</small></button>
      <button type="button" aria-current={page==="evidence"?"page":undefined} onClick={()=>setPage("evidence")}>◇<small>Evidence</small></button>
      </div>
      <button type="button" className="mdv3-mobile-more-trigger" ref={moreTriggerRef}
        aria-expanded={moreOpen} aria-controls="mdv3-mobile-more-panel"
        onClick={() => setMoreOpen(open => !open)}>
        <span aria-hidden="true">⋯</span><small>More</small>
      </button>
    </nav>
    {moreOpen && <section id="mdv3-mobile-more-panel" role="region"
      aria-label="More demo destinations" className="mdv3-mobile-more-panel" ref={morePanelRef}>
      <div className="mdv3-mobile-more-heading"><strong>Explore MatchDesk</strong>
        <span>Read-only demo</span></div>
      <div className="mdv3-mobile-more-options">
        {mobileDestinations.map(destination => <button type="button" key={destination.target}
          aria-current={page === destination.target ? "page" : undefined}
          onClick={() => {setPage(destination.target); setMoreOpen(false);}}>
          {destination.label}<span>{page === destination.target ? "Current" : "Open"}</span>
        </button>)}
      </div>
      <p>Producer approvals, publishing and live data are not available in this synthetic preview.</p>
    </section>}
    {showDialog && <div className="mdv3-dialog-backdrop" role="presentation"><div className="mdv3-dialog" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="mdv3-dialog-title" aria-describedby="mdv3-dialog-desc">
      <h2 id="mdv3-dialog-title">Approval blocked</h2><p id="mdv3-dialog-desc">{editorial.blockingReason}</p><p>Your work hasn’t been lost. <code>ref: req-7f3a</code></p>
      <div className="mdv3-actions"><button type="button" className="mdv3-primary" onClick={()=>{setShowDialog(false);setNotice("warning");}}>Understood</button><button type="button" className="mdv3-secondary" onClick={()=>setShowDialog(false)}>Close</button></div>
    </div></div>}
  </div>;
}
