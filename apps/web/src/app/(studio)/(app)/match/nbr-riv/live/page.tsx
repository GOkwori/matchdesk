/** Live Intelligence: the latest logged events, every shot on the pitch and rule-based detections. */
import type { Metadata } from "next";
import Link from "next/link";
import { Icon, type IconName } from "../../../../../../studio/icons";
import { Comparison, ShotMap } from "../../../../../../studio/pitchviz";
import { TopActions } from "../../../../../../studio/shell";
import { PageHead, ScoreStrip, StatBars } from "../../../../../../studio/ui";
import { clock, eventCountText, fixture, matchExport, playerName, recentEvents, shots } from "../../../../../../studio/data";

export const metadata: Metadata = { title: "Live Intelligence", robots: { index: false } };

const TYPE_ICON: Record<string, IconName> = { shot: "ball", goal: "ball", foul: "flag", card: "card", substitution: "swap" };
const TYPE_LABEL: Record<string, string> = {
  pass: "Pass", carry: "Carry", recovery: "Recovery", clearance: "Clearance", shot: "Shot", goal: "Goal",
  foul: "Foul", card: "Card", substitution: "Substitution", kickoff: "Kick-off", interception: "Interception",
};

export default function LivePage() {
  const stats = matchExport.statistics;
  const detected = matchExport.detected_moments;
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Overview", href: "/match/nbr-riv" }, { label: "Live Intelligence" }]} />
      <PageHead title="Live Intelligence" sub={`The newest events in the log, every shot, and what the detection rules found across ${eventCountText} events.`}><TopActions /></PageHead>
      <div className="md-three">
        <section className="md-panel md-feed" aria-labelledby="md-feed-title">
          <div className="md-panel-head"><h2 id="md-feed-title">Latest events</h2><span className="md-muted md-mono">to {fixture.latestEvent}</span></div>
          <ol className="md-feed-list" reversed>
            {[...recentEvents].reverse().map((e) => (
              <li key={e.id} className={e.type === "substitution" || e.type === "card" ? "md-feed-key" : undefined}>
                <span className="md-mono md-moment-clock">{clock(e.clock_ms / 1000)}</span>
                <span className={`md-feed-team md-feed-${e.team}`}>{e.team === "nbr" ? "NBR" : "RIV"}</span>
                <span className="md-feed-text">
                  <strong>{e.type === "substitution" ? "Substitution: Barros off, Kovac on" : TYPE_LABEL[e.type] ?? e.type}</strong>
                  <span className="md-mono">{e.id}{e.player && e.type !== "substitution" ? ` · ${playerName(e.player)}` : ""}{e.outcome && e.outcome !== "complete" ? ` · ${e.outcome}` : ""}</span>
                </span>
                {TYPE_ICON[e.type] && <Icon name={TYPE_ICON[e.type]} size={16} />}
              </li>
            ))}
          </ol>
        </section>
        <section className="md-panel md-proof" aria-labelledby="md-shots-title">
          <div className="md-panel-head"><h2 id="md-shots-title">Every shot so far</h2><Link href="/match/nbr-riv/tactical" className="md-link">Tactical view <Icon name="arrow" size={14} /></Link></div>
          <ShotMap shots={shots} caption="Shot locations from the event log" />
          <Comparison rows={[
            { label: "Shots", home: stats.nbr.shots, away: stats.riv.shots },
            { label: "On target", home: stats.nbr.on_target, away: stats.riv.on_target },
            { label: "Final-third entries", home: stats.nbr.final_third_entries, away: stats.riv.final_third_entries },
          ]} />
        </section>
        <aside className="md-impact" aria-label="Detections and statistics">
          <section className="md-panel">
            <h2>What the rules detected</h2>
            <ul className="md-check-list">
              {Object.entries(detected.by_kind).map(([kind, count]) => (
                <li key={kind}><span>{kind === "big_chance" ? "Big chance (xG ≥ 0.35)" : kind === "goal" ? "Goal" : kind.replace(/_/g, " ")}</span><strong>{count}</strong></li>
              ))}
            </ul>
            <p className="md-muted md-small">Deterministic detectors over the log, not AI judgements.</p>
            <Link href="/match/nbr-riv/moments?moment=M-05" className="md-btn md-btn-primary">Open key moments <Icon name="arrow" size={16} /></Link>
          </section>
          <StatBars />
        </aside>
      </div>
    </div>
  );
}
