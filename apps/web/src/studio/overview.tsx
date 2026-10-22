/** Overview body: replay-driven score card, attention tiles, moments, next step and stats. */
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { Crest, KpiTile, NextStep, StatBars, VerdictChip } from "./ui";
import { TourStep } from "./shell";
import { YourMatch } from "./your-match";
import { clock, eventCountText, fixture, momentsUntil, moments, REPLAY_END_SECONDS, scoreAt, serverClaim, type Moment } from "./data";

const goalIcon = (m: Moment) => (m.kind === "Goal" ? "ball" : m.kind === "Corner" ? "flag" : m.kind === "Substitution" ? "swap" : "card");

/** Read the optional ?t=<seconds> deep link, clamped to the replay window. */
function initialSeconds(raw: string | null): number {
  const n = Number(raw);
  return Number.isFinite(n) && raw !== null ? Math.min(REPLAY_END_SECONDS, Math.max(0, Math.round(n))) : REPLAY_END_SECONDS;
}

export function OverviewBody() {
  const params = useSearchParams();
  const [seconds, setSeconds] = useState(() => initialSeconds(params.get("t")));
  const [playing, setPlaying] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const score = scoreAt(seconds);
  const lastScore = useRef(`${score.home}-${score.away}`);

  // Announce score changes only, never every tick of the replay.
  useEffect(() => {
    const key = `${score.home}-${score.away}`;
    if (key !== lastScore.current) {
      lastScore.current = key;
      setAnnouncement(`Score now Northbridge ${score.home}, Riverside ${score.away} at ${clock(seconds)}`);
    }
  }, [score.home, score.away, seconds]);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setSeconds((s) => {
        if (s >= REPLAY_END_SECONDS) { setPlaying(false); return REPLAY_END_SECONDS; }
        return Math.min(REPLAY_END_SECONDS, s + 30);
      });
    }, 250);
    return () => window.clearInterval(id);
  }, [playing]);

  const happened = momentsUntil(seconds);
  const keyMoments = happened.filter((m) => m.kind === "Goal").slice(0, 3);
  const prev = [...moments].reverse().find((m) => m.seconds < seconds);
  const next = moments.find((m) => m.seconds > seconds);
  const pct = (s: number) => `${(s / (90 * 60)) * 100}%`;
  const atEnd = seconds === REPLAY_END_SECONDS;

  return (
    <>
      <section className="md-hero" aria-label="Match score and replay">
        <div className="md-hero-row">
          <div className="md-team"><Crest team="NBR" size={56} /><span><span className="md-team-name">{fixture.home.name}</span><span className="md-team-sub">Home · 58% possession</span></span></div>
          <div className="md-scorebox">
            <span className="md-clock">{clock(seconds)}</span>
            <span className="md-score" aria-label={`Northbridge ${score.home}, Riverside ${score.away}`}>{score.home} – {score.away}</span>
            <span className="md-team-sub">{seconds < 45 * 60 ? "First Half" : "Second Half"} · Replay</span>
          </div>
          <div className="md-team md-team-away"><span><span className="md-team-name">{fixture.away.name}</span><span className="md-team-sub">Away · 42% possession</span></span><Crest team="RIV" size={56} /></div>
        </div>
        <div className="md-replay">
          <button type="button" className="md-round-btn" onClick={() => { if (atEnd) setSeconds(0); setPlaying((p) => !p); }} aria-label={playing ? "Pause replay" : "Play replay"}>
            <Icon name={playing ? "pause" : "play"} size={16} />
          </button>
          <div className="md-slider">
            <div className="md-slider-track" aria-hidden="true"><span style={{ width: pct(seconds) }} /></div>
            {moments.filter((m) => m.kind === "Goal").map((m) => (
              <span key={m.id} aria-hidden="true" className={`md-slider-mark md-mark-${m.team === "NBR" ? "home" : "away"}`} style={{ left: pct(m.seconds) }} title={`${clock(m.seconds)} ${m.title}`} />
            ))}
            <input
              type="range" min={0} max={REPLAY_END_SECONDS} step={1} value={seconds}
              aria-label="Replay time"
              aria-valuetext={`${clock(seconds)}, Northbridge ${score.home} Riverside ${score.away}`}
              onChange={(e) => { setPlaying(false); setSeconds(Number(e.target.value)); }}
              style={{ width: pct(REPLAY_END_SECONDS) }}
            />
          </div>
          <div className="md-replay-jumps">
            <button type="button" className="md-icon-btn" disabled={!prev} onClick={() => prev && setSeconds(prev.seconds)} aria-label={prev ? `Previous key moment, ${prev.title}` : "No earlier moment"}><Icon name="prev" size={16} /></button>
            <button type="button" className="md-icon-btn" disabled={!next} onClick={() => next && setSeconds(next.seconds)} aria-label={next ? `Next key moment, ${next.title}` : "No later moment"}><Icon name="next" size={16} /></button>
          </div>
        </div>
        <p className="md-visually-hidden" aria-live="polite">{announcement}</p>
      </section>

      <section className="md-kpis" aria-label="What needs attention">
        <KpiTile icon="shield" tone="success" value="2" unit="/4" label="Claims verified" />
        <KpiTile icon="sparkle" tone="warn" value="3" label="AI insights to review" />
        <KpiTile icon="inbox" tone="error" value="1" label="Draft blocked · D-031" />
        <KpiTile icon="pulse" tone="info" value={fixture.eventCount.toLocaleString("en-GB")} label="Events in the replay" />
      </section>

      <div className="md-split">
        <section className="md-panel md-split-main" aria-labelledby="md-moments-title">
          <div className="md-panel-head"><h2 id="md-moments-title">Latest significant moments</h2><Link href="/match/nbr-riv/moments" className="md-link">View all 7 <Icon name="arrow" size={14} /></Link></div>
          {keyMoments.length === 0 && <p className="md-empty">No goals yet at {clock(seconds)}. Drag the replay forward or press play.</p>}
          <ul className="md-moment-list">
            {keyMoments.map((m, i) => (
              <li key={m.id}>
                <Link href={`/match/nbr-riv/moments?moment=${m.id}`} className={`md-moment${i === 0 ? " md-moment-hot" : ""}`}>
                  <span className="md-mono md-moment-clock">{clock(m.seconds)}</span>
                  <span className={`md-moment-icon md-moment-${m.team === "NBR" ? "home" : "away"}${i === 0 ? " md-moment-icon-hot" : ""}`}><Icon name={goalIcon(m)} /></span>
                  <span className="md-moment-text"><strong>{m.title}</strong><span>{m.detail} · {scoreAt(m.seconds).home}–{scoreAt(m.seconds).away}</span></span>
                  <VerdictChip verdict="verified" />
                </Link>
                {m.id === "M-05" && <TourStep step={1} />}
              </li>
            ))}
          </ul>
        </section>
        <div className="md-split-side">
          <NextStep title="D-031 can’t be approved yet" body="One claim needs a decision and one has no supporting evidence. Fix both and the draft re-verifies instantly." href="/producer/compose/D-031" action="Fix in composer" />
          <YourMatch />
          <ForgedCheck />
          <StatBars />
        </div>
      </div>
    </>
  );
}

/** One-click proof on the landing screen: a forged statistic is recomputed and rejected.
 * Both verdicts are the backend verifier's own results from the export. */
function ForgedCheck() {
  const [forged, setForged] = useState(false);
  const real = serverClaim("CL-0214");
  const fake = serverClaim("CL-0214", true);
  const shown = forged ? fake : real;
  const claimed = Math.round((shown.claim.assertion?.value ?? 0) * 100);
  const observed = ((real.result.observed ?? 0) * 100).toFixed(2);
  return (
    <section className="md-panel" aria-labelledby="md-forge-title">
      <span className="md-eyebrow">Try to fool the verifier</span>
      <h2 id="md-forge-title" className="md-sel-title">“Northbridge have had {claimed}% possession”</h2>
      <p className="md-muted">Recomputed from all {eventCountText} events: {observed}%.</p>
      <div aria-live="polite">
        {forged
          ? <p><VerdictChip verdict="failed" label="Rejected" /> {claimed}% is not what the log says, so it can’t reach approval.</p>
          : <p><VerdictChip verdict="verified" /> {claimed}% matches the log at whole-percent precision.</p>}
      </div>
      <button type="button" className="md-btn md-btn-secondary" aria-pressed={forged} onClick={() => setForged((f) => !f)}>{forged ? "Restore 58%" : "Claim 59% instead"}</button>
    </section>
  );
}
