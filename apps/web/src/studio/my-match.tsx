/** Settings › My match: favourite club and player, analyst or fan, language and one focus statistic. */
"use client";

import Link from "next/link";
import { matchExport, squads as SQUADS } from "./data";
import { FOCUS_METRICS, LANGUAGES, PERSONAS, useViewer, type FocusMetric, type Persona, type ViewerLanguage } from "./viewer";

const TEAMS = { nbr: matchExport.display_names.nbr ?? "Northbridge", riv: matchExport.display_names.riv ?? "Riverside" } as const;

export function MyMatchSettings() {
  const { viewer, ready, update } = useViewer();
  const clubs = viewer.club ? [viewer.club] : (["nbr", "riv"] as const);
  return (
    <section className="md-panel md-ds-wide" aria-labelledby="md-my-match-title" id="my-match">
      <h2 id="md-my-match-title">My match</h2>
      <p className="md-muted md-small">Shapes the replay overlays, the overview and Ask MatchDesk on this device. Nothing is sent anywhere.</p>
      <div className="md-form-grid" aria-busy={!ready}>
        <label className="md-field">
          <span>Favourite club</span>
          <select value={viewer.club ?? ""} onChange={(e) => update({ club: (e.target.value || null) as "nbr" | "riv" | null })}>
            <option value="">No favourite</option>
            <option value="nbr">{TEAMS.nbr}</option>
            <option value="riv">{TEAMS.riv}</option>
          </select>
        </label>
        <label className="md-field">
          <span>Favourite player</span>
          <select value={viewer.player ?? ""} onChange={(e) => update({ player: e.target.value || null })}>
            <option value="">No favourite</option>
            {clubs.map((club) => (
              <optgroup key={club} label={TEAMS[club]}>
                {SQUADS[club].map((p) => <option key={p.player_id} value={p.player_id}>{p.shirt}. {p.name} · {p.position}{p.starter ? "" : " (bench)"}</option>)}
              </optgroup>
            ))}
          </select>
        </label>
        <label className="md-field">
          <span>View as</span>
          <select value={viewer.persona} onChange={(e) => update({ persona: e.target.value as Persona })}>
            {PERSONAS.map((p) => <option key={p.id} value={p.id}>{p.label} · {p.hint}</option>)}
          </select>
        </label>
        <label className="md-field">
          <span>Overlay language</span>
          <select value={viewer.language} onChange={(e) => update({ language: e.target.value as ViewerLanguage })}>
            {LANGUAGES.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </select>
        </label>
        <label className="md-field">
          <span>Focus statistic</span>
          <select value={viewer.focus} onChange={(e) => update({ focus: e.target.value as FocusMetric })}>
            {FOCUS_METRICS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
        </label>
      </div>
      <div className="md-btn-row">
        <Link href="/match/nbr-riv/live" className="md-btn md-btn-primary">Watch the replay</Link>
        {viewer.player && <Link href={`/match/nbr-riv/player/${viewer.player}`} className="md-btn md-btn-secondary">Open player focus</Link>}
        <Link href="/match/nbr-riv/players" className="md-btn md-btn-secondary">All players</Link>
      </div>
    </section>
  );
}
