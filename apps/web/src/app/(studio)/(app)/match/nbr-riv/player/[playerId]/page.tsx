/** Player focus: one player's match, every figure stated as a claim and verified while the page is built. */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { METRICS, type Metric } from "../../../../../../../studio/ask";
import { clock, findPlayer, POSITION_LABEL, squads } from "../../../../../../../studio/data";
import { FavouritePlayer } from "../../../../../../../studio/favourite";
import { playerFocus } from "../../../../../../../studio/insight-engine";
import { matchContext } from "../../../../../../../studio/match-context";
import { roundHalfUp } from "../../../../../../../studio/precision";
import { TopActions } from "../../../../../../../studio/shell";
import { PageHead, ScoreStrip } from "../../../../../../../studio/ui";
import type { VEvent } from "../../../../../../../studio/verifier";

export function generateStaticParams() {
  return [...squads.nbr, ...squads.riv].map((p) => ({ playerId: p.player_id }));
}
export const dynamicParams = false;

export async function generateMetadata({ params }: { params: Promise<{ playerId: string }> }): Promise<Metadata> {
  const { playerId } = await params;
  const player = findPlayer(playerId);
  return { title: player ? `${player.name} · Player focus` : "Player focus", robots: { index: false } };
}

const NOTES: Partial<Record<Metric, string>> = {
  "synthetic_xg.v1": "This demo's own chance-quality model, not a licensed xG feed.",
  "pass_difficulty.v1": "0–100 per attempt: 45% length, 30% forward ambition, 15% a target in the final sixth, 10% pressure.",
  "progressive_passes.v1": "Completed, at least 10 m forward and at least 25% closer to goal.",
};

function figure(metric: Metric, value: number): string {
  const unit = METRICS[metric].unit;
  if (unit === "ratio") return `${roundHalfUp(value * 100, 0)}%`;
  if (unit === "synthetic_xg") return roundHalfUp(value, 2);
  if (unit === "metres") return `${roundHalfUp(value, 1)} m`;
  if (unit === "rating") return roundHalfUp(value, 1);
  return String(value);
}

/** Display position: Northbridge attack right, Riverside attack left. */
function at(club: string, x: number, y: number): [number, number] {
  return club === "riv" ? [1 + ((100 - x) / 100) * 103, 1 + ((100 - y) / 100) * 66] : [1 + (x / 100) * 103, 1 + (y / 100) * 66];
}

function ActionMap({ events, club, name }: { events: readonly VEvent[]; club: string; name: string }) {
  const passes = events.filter((e) => e.type === "pass" && e.x != null && e.y != null && e.end_x != null && e.end_y != null);
  const shots = events.filter((e) => (e.type === "shot" || e.type === "goal") && e.x != null && e.y != null);
  const wins = events.filter((e) => e.type === "recovery" && e.x != null && e.y != null);
  const complete = passes.filter((e) => e.outcome === "complete").length;
  const summary = `${name}'s actions to the replay point: ${passes.length} passes drawn, ${complete} completed; ${shots.length} shots; ${wins.length} ball recoveries. ${club === "nbr" ? "Attacking right." : "Attacking left."}`;
  return (
    <figure className="md-shotmap">
      <svg viewBox="0 0 105 68" role="img" aria-label={summary}>
        <defs>
          <marker id="md-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3" markerHeight="3" orient="auto-start-reverse"><path d="M0 0 6 3 0 6z" fill="var(--md-accent-soft)" /></marker>
        </defs>
        <rect width="105" height="68" fill="var(--md-pitch)" rx="1.5" />
        <g fill="none" stroke="var(--md-pitch-line)" strokeWidth="0.35">
          <rect x="1" y="1" width="103" height="66" /><path d="M52.5 1v66" /><circle cx="52.5" cy="34" r="9.15" />
          <rect x="1" y="13.85" width="16.5" height="40.3" /><rect x="87.5" y="13.85" width="16.5" height="40.3" />
        </g>
        {passes.map((e) => {
          const [x1, y1] = at(club, e.x!, e.y!);
          const [x2, y2] = at(club, e.end_x!, e.end_y!);
          const ok = e.outcome === "complete";
          return <line key={e.event_id} x1={x1} y1={y1} x2={x2} y2={y2} stroke={ok ? "var(--md-accent-soft)" : "var(--md-error)"} strokeWidth="0.45" opacity={ok ? 0.75 : 0.9} strokeDasharray={ok ? undefined : "1 0.8"} markerEnd={ok ? "url(#md-arrow)" : undefined}><title>{`${e.event_id} · ${clock(Math.floor(e.match_clock_ms / 1000))} · pass ${e.outcome}${e.under_pressure ? " · under pressure" : ""}`}</title></line>;
        })}
        {wins.map((e) => {
          const [x, y] = at(club, e.x!, e.y!);
          return <rect key={e.event_id} x={x - 1} y={y - 1} width="2" height="2" transform={`rotate(45 ${x} ${y})`} fill="var(--md-warn)"><title>{`${e.event_id} · ${clock(Math.floor(e.match_clock_ms / 1000))} · ball recovery${e.tags.length ? ` (${e.tags.join(", ")})` : ""}`}</title></rect>;
        })}
        {shots.map((e) => {
          const [x, y] = at(club, e.x!, e.y!);
          const goal = e.type === "goal" || e.outcome === "goal";
          return <circle key={e.event_id} cx={x} cy={y} r={goal ? 2.1 : 1.5} fill={goal ? "var(--md-text)" : "none"} stroke={club === "nbr" ? "var(--md-home)" : "var(--md-away)"} strokeWidth="0.6"><title>{`${e.event_id} · ${clock(Math.floor(e.match_clock_ms / 1000))} · ${e.type} ${e.outcome ?? ""}`}</title></circle>;
        })}
      </svg>
      <figcaption className="md-legend">
        <span><i style={{ background: "var(--md-accent-soft)" }} />Completed pass</span>
        <span><i style={{ background: "var(--md-error)" }} />Incomplete pass</span>
        <span><i style={{ background: "var(--md-warn)" }} />Ball recovery</span>
        <span><i style={{ border: "1px solid var(--md-text)" }} />Shot</span>
      </figcaption>
    </figure>
  );
}

export default async function PlayerPage({ params }: { params: Promise<{ playerId: string }> }) {
  const { playerId } = await params;
  const player = findPlayer(playerId);
  if (!player) notFound();
  const ctx = matchContext();
  const focus = playerFocus(ctx, player.player_id, player.club);
  const team = ctx.teams[player.club];
  const verified = focus.lines.filter((l) => l.result.status === "verified").length;
  const key = focus.events.filter((e) => ["shot", "goal", "card", "substitution"].includes(e.type) || (e.type === "recovery" && e.tags.length > 0));
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Overview", href: "/match/nbr-riv" }, { label: "Players", href: "/match/nbr-riv/players" }, { label: player.name }]} />
      <PageHead title={player.name} sub={`#${player.shirt} · ${POSITION_LABEL[player.position]} · ${team} · ${player.starter ? "Started" : "On the bench at kick-off"} · ${focus.events.length} logged actions to ${clock(ctx.replayEndMs / 1000)}`}><TopActions /></PageHead>
      <FavouritePlayer id={player.player_id} name={player.name} />
      <div className="md-split">
        <section className="md-panel md-split-main" aria-labelledby="md-player-figures">
          <div className="md-panel-head"><h2 id="md-player-figures">Figures to {clock(ctx.replayEndMs / 1000)}</h2><span className="md-muted md-small">{verified} of {focus.lines.length} sentences verified</span></div>
          <ul className="md-player-lines">
            {focus.lines.map((l) => {
              const metric = l.claim.assertion!.metric as Metric;
              const ok = l.result.status === "verified";
              return (
                <li key={metric}>
                  <span className="md-player-label">{METRICS[metric].label.charAt(0).toUpperCase() + METRICS[metric].label.slice(1)}</span>
                  <strong className="md-player-value md-mono">{figure(metric, l.claim.assertion!.value as number)}</strong>
                  <span className="md-player-sentence">{l.claim.text}</span>
                  <span className={`md-chip md-chip-${ok ? "verified" : "failed"}`}><span aria-hidden="true">{ok ? "✓" : "✕"}</span> {ok ? "Verified" : "Not verified"}</span>
                  {NOTES[metric] && <span className="md-muted md-small md-player-note">{NOTES[metric]}</span>}
                </li>
              );
            })}
          </ul>
          {focus.skipped.length > 0 && <p className="md-muted md-small">No passes logged, so there is no pass accuracy, length or difficulty to state.</p>}
          <p className="md-muted md-small">Each sentence is a claim built from a registered metric and checked by the same verifier the newsroom uses, while this page was built. Nothing here is written by a model.</p>
        </section>
        <aside className="md-split-side" aria-label="Where and when">
          <section className="md-panel" aria-labelledby="md-player-map">
            <h2 id="md-player-map">Action map</h2>
            <ActionMap events={focus.events} club={player.club} name={player.name} />
          </section>
          <section className="md-panel" aria-labelledby="md-player-key">
            <h2 id="md-player-key">Key actions</h2>
            {key.length ? (
              <ol className="md-ticker">
                {key.map((e) => (
                  <li key={e.event_id}>
                    <span className="md-mono md-moment-clock">{clock(Math.floor(e.match_clock_ms / 1000))}</span>
                    <span>{e.type === "recovery" ? e.tags.join(", ") : `${e.type}${e.outcome && e.outcome !== e.type ? ` · ${e.outcome}` : ""}${e.tags.length ? ` · ${e.tags.join(", ")}` : ""}`}</span>
                    <span className="md-mono md-subtle">{e.event_id}</span>
                  </li>
                ))}
              </ol>
            ) : <p className="md-muted md-small">No shots, cards, substitutions, tackles or interceptions logged.</p>}
            <Link href="/match/nbr-riv/players" className="md-link">All players</Link>
          </section>
        </aside>
      </div>
    </div>
  );
}
