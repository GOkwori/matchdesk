/** Sunset Studio v3 screen 11: audience story as an unpublished synthetic preview.
 *
 * The approved visual concept is recreated without invented player coordinates,
 * tracking data, a verified publisher, or a real public delivery route. Only
 * events present in demo-data.ts may support the narrative. The source-details
 * disclosure is local UI state and cannot access any privileged API.
 */
"use client";

import { useState } from "react";
import { fixture, moments } from "./demo-data";

/** A named source record is deliberately not represented as a server verdict. */
const openingGoal = moments.find(event => event.event === "E-0688");
const corner = moments.find(event => event.event === "E-1359");
const secondGoal = moments.find(event => event.event === "E-1366");

/** Calculate elapsed time from the literal event clocks; fail closed on bad data. */
function clockSeconds(value: string | undefined): number | null {
  if (!value || !/^\d{1,3}:[0-5]\d$/.test(value)) return null;
  const [minutes, seconds] = value.split(":").map(Number);
  return minutes * 60 + seconds;
}
const cornerSeconds = clockSeconds(corner?.clock);
const goalSeconds = clockSeconds(secondGoal?.clock);
const interval = cornerSeconds !== null && goalSeconds !== null && goalSeconds > cornerSeconds
  ? goalSeconds - cornerSeconds : null;
const sourceComplete = Boolean(
  openingGoal?.kind === "Goal" && openingGoal.title.includes("Okafor") &&
  corner?.kind === "Corner" &&
  secondGoal?.kind === "Goal" && secondGoal.title.includes("Okafor") &&
  secondGoal.scoreAfter === "2–1" && interval === 14
);

/** Abstract context, not a shot map. No markings imply actual event positions. */
function PitchSchematic() {
  return <div className="mdv3-audience-pitch" role="group"
    aria-label="Decorative football pitch schematic: no positional, tracking or shot-location data">
    <svg viewBox="0 0 610 240" aria-hidden="true" focusable="false"
      preserveAspectRatio="xMidYMid meet" className="mdv3-audience-pitch-lines">
      <rect x="10" y="10" width="590" height="220" rx="7"/>
      <rect x="27" y="24" width="556" height="192"/>
      <path d="M305 24V216"/>
      <circle cx="305" cy="120" r="39"/>
      <circle cx="305" cy="120" r="2" fill="currentColor"/>
      <path d="M27 65H107V175H27M583 65H503V175H583M27 91H57V149H27M583 91H553V149H583"/>
      <path d="M27 24A12 12 0 0 1 39 36M583 24A12 12 0 0 0 571 36M27 216A12 12 0 0 0 39 204M583 216A12 12 0 0 1 571 204"/>
    </svg>
    <div className="mdv3-audience-pitch-caption">
      <strong>Event sequence only</strong>
      <span>No tracking or event-position data</span>
    </div>
  </div>;
}

/** Small labels indicate source completeness rather than executable eligibility. */
function EvidenceStatus({ status }: { status: "recorded" | "unsupported" }) {
  return <span className={"mdv3-audience-status mdv3-audience-" + status}>
    {status === "recorded" ? "Recorded" : "Not verifiable"}
  </span>;
}

export function AudienceExperience({ onOpenEvidence }: { onOpenEvidence: () => void }) {
  const [sourceOpen, setSourceOpen] = useState(false);

  return <div className="mdv3-content mdv3-audience">
    <header className="mdv3-page-heading">
      <div>
        <span className="mdv3-kicker">SUNSET STUDIO V3 · SCREEN 11 · SYNTHETIC PREVIEW</span>
        <h1>Audience Experience</h1>
        <p>A mobile-first football story explaining what the recorded events show and what they do not.</p>
      </div>
      <span className="mdv3-audience-stamp">Concept · Not live</span>
    </header>

    <div className="mdv3-audience-layout">
      <article className="mdv3-panel mdv3-audience-story" aria-labelledby="mdv3-audience-story-title">
        <span className="mdv3-kicker">SYNTHETIC REPLAY · {sourceComplete ? "58′ · EXPLAINED MOMENT" : "SOURCE DETAILS UNAVAILABLE"}</span>
        <h2 id="mdv3-audience-story-title">
          {sourceComplete ? <>Okafor&apos;s second goal <em>puts Northbridge ahead.</em></> :
            <>An event-based story <em>is not available.</em></>}
        </h2>
        <p className="mdv3-audience-lede">
          {sourceComplete
            ? "A recorded corner was followed 14 seconds later by Okafor's goal. Northbridge lead Riverside United 2–1 in this invented match."
            : "The required named synthetic records are missing or inconsistent. We cannot substantiate the proposed audience story."}
        </p>
        <div className="mdv3-audience-pills" aria-label="Source and publication limitations">
          <span className="mdv3-audience-pill mdv3-audience-source">{sourceComplete ? "Recorded fixture facts" : "Evidence unavailable"}</span>
          <span className="mdv3-audience-pill mdv3-audience-future">Audience view · Future state</span>
        </div>

        <section className="mdv3-audience-score" aria-label="Synthetic match score">
          <div className="mdv3-audience-team">
            <span className="mdv3-audience-crest" aria-hidden="true">{fixture.homeCode[0]}</span>
            <span><strong>{fixture.home}</strong><small>Home · {fixture.homeCode}</small></span>
          </div>
          <div className="mdv3-audience-score-middle">
            <span className="mdv3-audience-clock">{fixture.clock}</span>
            <strong>{fixture.scoreHome} – {fixture.scoreAway}</strong>
            <small>{fixture.half} · Replay {fixture.replaySpeed}</small>
          </div>
          <div className="mdv3-audience-team mdv3-audience-away">
            <span><strong>{fixture.away}</strong><small>Away · {fixture.awayCode}</small></span>
            <span className="mdv3-audience-crest mdv3-audience-away-crest" aria-hidden="true">{fixture.awayCode[0]}</span>
          </div>
        </section>

        <PitchSchematic/>
        <div className="mdv3-audience-moment">
          <strong>{secondGoal?.clock.split(":")[0] ?? "—"}′</strong>
          <span>{sourceComplete ? "Okafor · Northbridge FC" : "Event attribution unavailable"}</span>
          <small>{sourceComplete
            ? "Goal event " + secondGoal?.event + " · Corner event " + corner?.event
            : "No source-backed sequence established"}</small>
        </div>
      </article>

      <section className="mdv3-panel mdv3-audience-evidence" aria-labelledby="mdv3-audience-checks-title">
        <div className="mdv3-head"><h2 id="mdv3-audience-checks-title">How we checked this</h2></div>
        <div className="mdv3-audience-source-intro">
          <span aria-hidden="true">◇</span>
          <strong>{sourceComplete ? "Recorded events, clearly sourced" : "Source sequence incomplete"}</strong>
        </div>
        <p className="mdv3-audience-evidence-copy">
          {sourceComplete
            ? "The signed-off synthetic fixture records a goal attributed to Okafor. Its corner event precedes the goal by 14 seconds; no location or tracking evidence was supplied."
            : "The signed-off synthetic fixture does not provide the complete event sequence required for this explanation."}
        </p>

        <dl className="mdv3-audience-checklist">
          <div><dt>Goal scorer in fixture</dt><dd><EvidenceStatus status={sourceComplete ? "recorded" : "unsupported"}/></dd></div>
          <div><dt>Timing of recorded events</dt><dd><EvidenceStatus status={sourceComplete ? "recorded" : "unsupported"}/></dd></div>
          <div><dt>Defender positions</dt><dd><EvidenceStatus status="unsupported"/></dd></div>
        </dl>
        <div className="mdv3-audience-info" role="note">
          <span aria-hidden="true">ⓘ</span>
          <div><strong>Why some claims are excluded</strong>
            <p>These source events do not include defender positions. We do not present positional or tactical interpretations as verified facts.</p>
          </div>
        </div>
        <p className="mdv3-audience-boundary">This is an unpublished preview derived from a frozen demonstration fixture, not an independently certified claim or a live audience feed.</p>
        <button type="button" className="mdv3-secondary mdv3-audience-detail-button"
          aria-expanded={sourceOpen}
          aria-controls={sourceOpen ? "mdv3-audience-source-details" : undefined}
          onClick={() => setSourceOpen(open => !open)}>
          <span aria-hidden="true">◇</span> {sourceOpen ? "Hide source details" : "View source details"}
        </button>
        {sourceOpen && <section id="mdv3-audience-source-details"
          className="mdv3-audience-detail-panel" role="region" aria-label="Synthetic source event details">
          <h3>Named synthetic source events</h3>
          <p>These are fixture records, not a production verification receipt or proof of match footage.</p>
          <dl>
            <div><dt>Earlier Okafor goal</dt><dd>{openingGoal ? openingGoal.event + " · " + openingGoal.clock : "Unavailable"}</dd></div>
            <div><dt>Corner</dt><dd>{corner ? corner.event + " · " + corner.clock : "Unavailable"}</dd></div>
            <div><dt>Following goal</dt><dd>{secondGoal ? secondGoal.event + " · " + secondGoal.clock : "Unavailable"}</dd></div>
            <div><dt>Elapsed interval</dt><dd>{interval !== null ? interval + " seconds" : "Not computable"}</dd></div>
            <div><dt>Location / defender tracking</dt><dd>Not provided</dd></div>
          </dl>
          <button type="button" className="mdv3-secondary" onClick={onOpenEvidence}>
            Open Evidence Explorer <span aria-hidden="true">→</span>
          </button>
        </section>}
      </section>
    </div>
    <section className="mdv3-control-note" aria-label="Audience preview security boundary">
      <strong>Audience experience · visual concept only.</strong>
      <p>No public delivery, real footage, player tracking, authenticated publication or backend action is enabled. Record-level evidence must be independently verified before a separately authorised publication decision.</p>
    </section>
  </div>;
}
