/** Sunset Studio v3 screens 03–04: event-derived, read-only synthetic views.
 *
 * No source in the approved fixture provides per-event coordinates, momentum
 * samples, pass maps, player locations or video. Never invent that evidence.
 */
"use client";

import { useState, type ReactNode } from "react";
import { fixture, matchStatistics, moments, type Moment } from "./demo-data";

type Team = "NBR" | "RIV";
type TeamFilter = Team | "all";
type EventGroup = "all" | "goals" | "set-pieces" | "bookings" | "substitutions" | "shots" | "final-third";
type FeedEvent = {
  readonly id: string;
  readonly event: string;
  readonly clock: string;
  readonly title: string;
  readonly details: string;
  readonly kind: string;
  readonly team: Team | null;
  readonly scoreAfter: string;
};

/** Only identities explicitly established in the approved synthetic script. */
const EVENT_TEAMS: Readonly<Record<string, Team>> = {
  "M-01": "RIV",
  "M-02": "NBR",
  "M-03": "RIV",
  "M-04": "NBR",
  "M-05": "NBR",
  "M-06": "NBR",
  "M-07": "RIV",
};
const SCORE_AT_HALF = "1–1";

function minute(clock: string): number {
  const [mm, ss] = clock.split(":").map(Number);
  return mm + ss / 60;
}

const feed: readonly FeedEvent[] = [
  ...moments.map((moment: Moment): FeedEvent => ({
    ...moment,
    team: EVENT_TEAMS[moment.id] ?? null,
  })),
  {
    id: "HT",
    clock: "45:00",
    event: "E-0841",
    title: "Half-time",
    details: "First-half interval recorded at 45:00.",
    kind: "Interval",
    team: null,
    scoreAfter: SCORE_AT_HALF,
  },
].sort((a, b) => minute(b.clock) - minute(a.clock));

/** Legend chips describe source status, not model-generated verification. */
function SourceStatus({ verified = false }: { verified?: boolean }) {
  return verified
    ? <span className="mdv3-status mdv3-success"><span aria-hidden="true">✓</span> Verified claim</span>
    : <span className="mdv3-status mdv3-planned"><span aria-hidden="true">ⓘ</span> Logged synthetic event</span>;
}

/** A schematic football pitch contains no point marker or inferred location. */
export function EmptyPitch({ title }: { title: string }) {
  return <div className="mdv3-pitch" role="group" aria-label={title + ". No event coordinates available"}>
    <div className="mdv3-pitch-boundary" aria-hidden="true">
      <div className="mdv3-pitch-mid"/><div className="mdv3-pitch-centre"/>
      <div className="mdv3-pitch-box mdv3-pitch-box-left"/>
      <div className="mdv3-pitch-box mdv3-pitch-box-right"/>
    </div>
    <div className="mdv3-pitch-empty"><strong>Coordinates unavailable</strong>
      <span>No tracking data. The synthetic script has no event x/y locations.</span></div>
  </div>;
}

/** Exact goal-time markers, NOT a synthetic quantitative momentum metric. */
function GoalEventMarkers() {
  const goals = moments.filter(item => item.kind === "Goal");
  return <div className="mdv3-event-chart">
    <svg viewBox="0 0 700 155" role="img" aria-label="Goal event timeline: Northbridge at 34:18, Riverside at 41:03, Northbridge at 58:17. No quantitative momentum measurements.">
      <line x1="30" y1="109" x2="675" y2="109" stroke="currentColor" opacity=".45"/>
      {[0, 15, 30, 45, 60, 67].map(t => {
        const x = 30 + (t / 67.2) * 645;
        return <g key={t}><line x1={x} y1="22" x2={x} y2="110" stroke="currentColor" opacity=".12"/>
          <text x={x} y="137" fill="currentColor" fontSize="12" textAnchor="middle">{t}&apos;</text></g>;
      })}
      {goals.map(item => {
        const x = 30 + (minute(item.clock) / 67.2) * 645;
        return <g key={item.id}>
          <line x1={x} y1="27" x2={x} y2="109" stroke="#ff9159" strokeDasharray="4 4"/>
          <circle cx={x} cy="62" r="10" fill="#ff9159" stroke="#10151c" strokeWidth="3"/>
          <text x={x} y="19" fill="#f5f7fa" textAnchor="middle" fontSize="12">{item.clock}</text>
        </g>;
      })}
    </svg>
    <p className="mdv3-muted">Goals at 34&apos;, 41&apos; and 58&apos; are recorded events. <strong>No measured momentum series is supplied.</strong></p>
  </div>;
}

/** A recorded event can be inspected locally but never approved or published. */
function RecordedFeed({ selectedId, onSelect }: { selectedId: string; onSelect: (id: string) => void }) {
  return <div role="group" className="mdv3-recorded-feed" aria-label="Recorded synthetic event feed">
    {feed.map(item => <button type="button" key={item.id}
        className={"mdv3-feed-button" + (selectedId === item.id ? " mdv3-feed-selected" : "")}
        aria-pressed={selectedId === item.id} onClick={() => onSelect(item.id)}>
      <span className="mdv3-mono">{item.clock}</span>
      <span><strong>{item.id === "HT" ? "Half-time" : item.id + " · " + item.title}</strong>
        <small>{item.event} · {item.kind} · Score {item.scoreAfter}</small></span>
      <span className="mdv3-event-type">{selectedId === item.id ? "Selected" : item.kind}</span>
    </button>)}
  </div>;
}

/** Source linkage is bounded to facts actually included in the design brief. */
function SelectedEvent({ value }: { value: FeedEvent }) {
  const linkedGoal = value.id === "M-05";
  const okaforGoal = value.id === "M-02" || linkedGoal;
  return <section className="mdv3-panel">
    <div className="mdv3-head"><h2>Selected event</h2><SourceStatus verified={okaforGoal}/></div>
    <p className="mdv3-mono">{value.id} · {value.event} · {value.clock}</p>
    <h3>{value.title}</h3><p>{value.details}</p>
    <p>Recorded score after event: <strong>{value.scoreAfter}</strong></p>
    {linkedGoal && <div className="mdv3-trace">
      <span>Corner <code>E-1359</code> at 58:03</span>
      <span aria-hidden="true">→</span>
      <span>Goal <code>E-1366</code> at 58:17</span>
      <p>14 seconds between events · score changed 1–1 → 2–1</p>
      <span className="mdv3-status mdv3-success"><span aria-hidden="true">✓</span> CL-0213 Verified</span>
      <small>Claim: Okafor scored both Northbridge goals (E-0688, E-1366).</small>
    </div>}
    {value.id === "M-02" && <div className="mdv3-trace">
      <span className="mdv3-status mdv3-success"><span aria-hidden="true">✓</span> CL-0213 Verified</span>
      <p>Okafor goals are supported by E-0688 and E-1366.</p>
    </div>}
    {!okaforGoal && <p className="mdv3-muted">No independently qualified claim verdict is attached to this event in the approved fixture.</p>}
  </section>;
}

export function CommandCentre({ score }: { score: ReactNode }) {
  const [selectedId, setSelectedId] = useState("M-05");
  const current = feed.find(event => event.id === selectedId) ?? feed[0];
  return <div className="mdv3-content">
    <div className="mdv3-page-heading"><div>
      <span className="mdv3-kicker">SUNSET STUDIO / SCREEN 03 OF 14</span>
      <h1>Match Intelligence Command Centre</h1>
      <p>Follow a recorded synthetic match event from its source to a verifiable claim.</p>
    </div><SourceStatus/></div>
    {score}
    <div className="mdv3-summary">
      <span><strong>{fixture.eventCount.toLocaleString("en-GB")}</strong> Synthetic events</span>
      <span><strong>{fixture.latestEvent}</strong> at {fixture.latestEventClock}</span>
      <span>Replay · {fixture.clock} · Not live</span>
    </div>
    <div className="mdv3-command-layout">
      <section className="mdv3-panel">
        <div className="mdv3-head"><h2>Significant events and narrative markers</h2><span className="mdv3-status mdv3-planned">ⓘ Synthetic log</span></div>
        <GoalEventMarkers/>
        <h3>Recorded event feed</h3>
        <RecordedFeed selectedId={selectedId} onSelect={setSelectedId}/>
        <p className="mdv3-muted">Each selection inspects local fixture data. No stream, AI inference, database writes or approval occurs.</p>
      </section>
      <div className="mdv3-column-stack">
        <SelectedEvent value={current}/>
        <section className="mdv3-panel"><div className="mdv3-head"><h2>Shot locations from event log</h2><span className="mdv3-status mdv3-planned">ⓘ No tracking data</span></div>
          <EmptyPitch title="Shot-location pitch schematic"/>
          <p className="mdv3-muted">The whole-match shot count is available, but the source contains no per-shot x/y coordinates. No heatmap or positions are inferred.</p>
        </section>
      </div>
    </div>
  </div>;
}

const groups: readonly { value: EventGroup; label: string }[] = [
  { value: "set-pieces", label: "Logged set pieces" },
  { value: "goals", label: "Recorded goals" },
  { value: "bookings", label: "Yellow cards" },
  { value: "substitutions", label: "Substitutions" },
  { value: "shots", label: "Shots (aggregate only)" },
  { value: "final-third", label: "Final-third passes (unavailable)" },
  { value: "all", label: "All known moments" },
];

function matchesGroup(item: FeedEvent, group: EventGroup): boolean {
  if (group === "all") return item.id !== "HT";
  if (group === "goals") return item.kind === "Goal";
  if (group === "set-pieces") return item.kind === "Corner";
  if (group === "bookings") return item.kind === "Yellow card";
  if (group === "substitutions") return item.kind === "Substitution";
  // Only whole-match shot counts are supplied; there are no pass-level records.
  return false;
}

export function TacticalAnalysis({ score, onOpenCommand }: { score: ReactNode; onOpenCommand: () => void }) {
  const [team, setTeam] = useState<TeamFilter>("NBR");
  const [group, setGroup] = useState<EventGroup>("set-pieces");
  const [selectedId, setSelectedId] = useState("M-04");
  const matching = feed.filter(item => (team === "all" || item.team === team) && matchesGroup(item, group));
  const selected = matching.find(item => item.id === selectedId) ?? matching[0] ?? null;
  const stat = (label: string) => matchStatistics.find(item => item.label === label);
  return <div className="mdv3-content">
    <div className="mdv3-page-heading"><div>
      <span className="mdv3-kicker">SUNSET STUDIO / SCREEN 04 OF 14</span>
      <h1>Tactical Analysis</h1>
      <p>Event-derived context without invented tracking, player positions or formations.</p>
    </div><span className="mdv3-status mdv3-planned">ⓘ No tracking data</span></div>
    {score}
    <div className="mdv3-tactical-filters">
      <label>Team <select aria-label="Team" value={team} onChange={e => setTeam(e.target.value as TeamFilter)}>
        <option value="NBR">{fixture.home}</option><option value="RIV">{fixture.away}</option><option value="all">Both teams</option>
      </select></label>
      <label>Event group <select aria-label="Event group" value={group} onChange={e => setGroup(e.target.value as EventGroup)}>
        {groups.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
      </select></label>
    </div>
    <div className="mdv3-command-layout">
      <section className="mdv3-panel">
        <div className="mdv3-head"><h2>Event-location analysis</h2><span className="mdv3-status mdv3-planned">ⓘ Coordinates unavailable</span></div>
        <EmptyPitch title="Event-location pitch schematic"/>
        <p className="mdv3-muted">Pitch lines are schematic. Location markers would invent x/y data, so none are plotted.</p>
        <div className="mdv3-aggregate-grid" aria-label="Whole match aggregate figures">
          {["Shots", "On target", "Corners"].map(label => {
            const item = stat(label);
            return <div key={label}><span>{label}</span><strong>{item?.home} / {item?.away}</strong><small>Whole match · NBR / RIV</small></div>;
          })}
        </div>
        <h3>Known events in this filter</h3>
        {matching.length
          ? <div className="mdv3-recorded-feed">{matching.map(item =>
              <button type="button" key={item.id}
                className={"mdv3-feed-button" + (selected?.id === item.id ? " mdv3-feed-selected" : "")}
                onClick={() => setSelectedId(item.id)} aria-pressed={selected?.id === item.id}>
                <span className="mdv3-mono">{item.clock}</span><span><strong>{item.title}</strong><small>{item.id} · {item.event}</small></span>
              </button>)}</div>
          : <p role="status" className="mdv3-empty-result">{group === "shots"
              ? "Individual shot records and coordinates were not supplied; only aggregate counts are available."
              : group === "final-third"
                ? "No final-third pass records or event coordinates were supplied."
                : "No matching recorded moments for this team and event group."}</p>}
      </section>
      <div className="mdv3-column-stack">
        <section className="mdv3-panel"><div className="mdv3-head"><h2>Selected event</h2><SourceStatus/></div>
          {selected ? <><p className="mdv3-mono">{selected.id} / {selected.event}</p>
            <h3>{selected.title}</h3><p>{selected.clock}, score {selected.scoreAfter}. {selected.details}</p>
            {selected.id === "M-04" && <p>Next logged goal: <code>E-1366</code> at 58:17, 14 seconds later.</p>}
            <button type="button" className="mdv3-secondary" onClick={onOpenCommand}>Open command centre →</button>
          </> : <p className="mdv3-muted">No individual event can be selected from this source view.</p>}
        </section>
        <section className="mdv3-panel"><h2>Tactical interpretation</h2>
          <div className="mdv3-status mdv3-warning"><span aria-hidden="true">!</span> Interpretation · Needs human review</div>
          <h3>Corner preceding Northbridge&apos;s second goal</h3>
          <p>The recorded 14-second corner-to-goal sequence could be useful for analysis, but no tactical conclusion can be verified from a missing spatial data set.</p>
          <p className="mdv3-mono">E-1359 → E-1366</p>
        </section>
        <section className="mdv3-panel"><h2>Data limits</h2>
          <p>Formation shapes, player locations, defensive positions, shot maps and computer-vision confidence are unavailable. They cannot be inferred from these synthetic event descriptions.</p>
        </section>
      </div>
    </div>
  </div>;
}
