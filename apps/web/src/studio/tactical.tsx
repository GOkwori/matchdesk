/** Tactical Analysis body: team and half filters over real shot locations, plus cited insights. */
"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "./icons";
import { Comparison, ShotMap } from "./pitchviz";
import { VerdictChip } from "./ui";
import { matchExport, possessionSeries, shots } from "./data";

type TeamFilter = "both" | "nbr" | "riv";
type HalfFilter = "all" | "1" | "2";

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: readonly { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} className="md-seg">
      <span className="md-seg-label">{label}</span>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function TacticalBody() {
  const [team, setTeam] = useState<TeamFilter>("both");
  const [half, setHalf] = useState<HalfFilter>("all");
  const shown = shots.filter((s) => (team === "both" || s.team === team) && (half === "all" || String(s.period) === half));
  const count = (t: string, onTarget = false) => shown.filter((s) => s.team === t && (!onTarget || s.outcome === "goal" || s.outcome === "saved")).length;
  const stats = matchExport.statistics;
  const lowest = possessionSeries.reduce((m, p) => (p.share < m.share ? p : m));
  const halfLabel = half === "all" ? "whole match" : half === "1" ? "first half" : "second half";

  return (
    <div className="md-split">
      <section className="md-panel md-split-main" aria-labelledby="md-tac-map">
        <div className="md-panel-head"><h2 id="md-tac-map">Shot map · {halfLabel}</h2><span className="md-muted">{shown.length} shots</span></div>
        <div className="md-filters">
          <Segmented label="Team" value={team} onChange={setTeam} options={[{ value: "both", label: "Both" }, { value: "nbr", label: "Northbridge" }, { value: "riv", label: "Riverside" }]} />
          <Segmented label="Half" value={half} onChange={setHalf} options={[{ value: "all", label: "All" }, { value: "1", label: "1st" }, { value: "2", label: "2nd" }]} />
        </div>
        <ShotMap shots={shown} caption={`Shots from the event log, ${halfLabel}`} />
        <h3 className="md-h3">Head to head · {halfLabel}</h3>
        <Comparison rows={[
          { label: "Shots", home: count("nbr"), away: count("riv") },
          { label: "On target", home: count("nbr", true), away: count("riv", true) },
        ]} />
        <p className="md-muted md-small">Event locations only. There is no player-tracking data, so no formations or defender positions are shown.</p>
      </section>
      <aside className="md-split-side" aria-label="Insights">
        <section className="md-panel" aria-labelledby="md-tac-cmp">
          <h2 id="md-tac-cmp">Whole match, from the log</h2>
          <Comparison rows={[
            { label: "Final-third entries", home: stats.nbr.final_third_entries, away: stats.riv.final_third_entries },
            { label: "Corners", home: stats.nbr.corners, away: stats.riv.corners },
            { label: "Fouls", home: stats.nbr.fouls, away: stats.riv.fouls },
          ]} />
        </section>
        <section className="md-panel md-insights" aria-labelledby="md-tac-ins">
          <h2 id="md-tac-ins">What the numbers suggest</h2>
          <article className="md-insight">
            <VerdictChip verdict="verified" label="From the log" />
            <strong>Northbridge got forward far more often</strong>
            <p>{stats.nbr.final_third_entries} final-third entries to {stats.riv.final_third_entries} (final_third_entries.v1).</p>
          </article>
          <article className="md-insight">
            <VerdictChip verdict="pending" label="Interpretation · needs review" />
            <strong>Riverside’s best spell came before half-time</strong>
            <p>Northbridge’s possession fell to {lowest.share}% between {lowest.minute}′ and {lowest.minute + 5}′, its lowest five-minute window. This backs CL-0215 only as an opinion.</p>
            <Link href="/match/nbr-riv/evidence/CL-0215" className="md-link">See CL-0215 <Icon name="arrow" size={14} /></Link>
          </article>
          <article className="md-insight">
            <VerdictChip verdict="pending" label="Interpretation · needs review" />
            <strong>Set pieces decided the second half</strong>
            <p>The 58′ header came 14 seconds after a Northbridge corner (E-1359 → E-1366).</p>
            <Link href="/match/nbr-riv/moments?moment=M-05" className="md-link">Open the moment <Icon name="arrow" size={14} /></Link>
          </article>
        </section>
      </aside>
    </div>
  );
}
