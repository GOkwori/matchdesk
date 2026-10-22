/**
 * Live replay: the event log plays out at real time or faster, the registered metrics recompute
 * as it goes, and timed broadcast overlays from the machine-readable feed appear at their
 * moments. Each overlay's claims are re-verified in this browser before it is shown, in the
 * viewer's persona and language. Loaded on demand so the page itself stays light.
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "./icons";
import { clock, matchExport, playerName } from "./data";
import { roundHalfUp } from "./precision";
import { FOCUS_METRICS, LANGUAGES, PERSONAS, useViewer, type Persona, type ViewerLanguage } from "./viewer";
import type { Claim, CompactLog, VEvent } from "./verifier";

type Cue = {
  cue_id: string; t_ms: number; clock: string; duration_ms: number; kind: string; team: string | null;
  players: string[]; event_ids: string[]; status: "verified" | "logged" | "failed"; claim_ids: string[];
  text: Record<Persona, Record<ViewerLanguage, string>>;
};
type FeedClaim = { claim_id: string; text: string; status: string; claim: Claim };
type Feed = { schema: string; replay_end_ms: number; cues: Cue[]; claims: FeedClaim[] };
type Verifier = typeof import("./verifier");
type Loaded = { events: VEvent[]; feed: Feed; verifier: Verifier; recheck: Record<string, boolean> };

const SPEEDS = [1, 10, 30, 60] as const;
const TICK_MS = 100;
const END = matchExport.replay_end_ms;
const NAMES = matchExport.display_names;
const TEAMS = { nbr: NAMES.nbr ?? "Northbridge", riv: NAMES.riv ?? "Riverside" } as const;

const PROOF: Record<ViewerLanguage, { verified: string; logged: string; failed: string }> = {
  en: { verified: "Verified in this browser", logged: "Logged event", failed: "Not verified" },
  es: { verified: "Verificado en este navegador", logged: "Evento registrado", failed: "No verificado" },
  fr: { verified: "Vérifié dans ce navigateur", logged: "Événement enregistré", failed: "Non vérifié" },
};
const TYPE_LABEL: Record<string, string> = {
  pass: "Pass", carry: "Carry", recovery: "Recovery", clearance: "Clearance", shot: "Shot", goal: "Goal", foul: "Foul",
  card: "Card", substitution: "Substitution", kickoff: "Kick-off", corner: "Corner", throw_in: "Throw-in", free_kick: "Free kick",
};

/** Load the log, the verifier and the overlay feed, then re-verify every claim the feed carries. */
function useReplayData(): Loaded | "loading" | "failed" {
  const [state, setState] = useState<Loaded | "loading" | "failed">("loading");
  useEffect(() => {
    let live = true;
    Promise.all([import("./generated/nbr-riv-events.json"), import("./verifier"), import("../../public/overlays/nbr-riv.json")]).then(
      ([log, verifier, feedModule]) => {
        const events = verifier.expandLog(log.default as unknown as CompactLog);
        const feed = feedModule.default as unknown as Feed;
        const evidence = { match_id: matchExport.match_id, event_ids: events.map((e) => e.event_id), window: { from_ms: 0, to_ms: feed.replay_end_ms } };
        const recheck: Record<string, boolean> = {};
        for (const record of feed.claims) {
          const result = verifier.verifyClaim(record.claim, evidence, events, NAMES);
          recheck[record.claim_id] = result.status === "verified" && record.status === "verified" && record.claim.text === record.text;
        }
        if (live) setState({ events, feed, verifier, recheck });
      },
      () => { if (live) setState("failed"); },
    );
    return () => { live = false; };
  }, []);
  return state;
}

function shown(unit: string, value: number): string {
  if (unit === "ratio") return `${roundHalfUp(value * 100, 0)}%`;
  if (unit === "synthetic_xg") return roundHalfUp(value, 2);
  if (unit === "metres") return `${roundHalfUp(value, 1)} m`;
  if (unit === "km_per_hour") return `${roundHalfUp(value, 1)} km/h`;
  if (unit === "rating") return roundHalfUp(value, 1);
  return String(value);
}

/** Display position: Northbridge attack right, Riverside attack left (event x/y are per team). */
function spot(e: VEvent): { x: number; y: number } | null {
  if (e.x == null || e.y == null) return null;
  return e.team_id === "riv" ? { x: 1 + ((100 - e.x) / 100) * 103, y: 1 + ((100 - e.y) / 100) * 66 } : { x: 1 + (e.x / 100) * 103, y: 1 + (e.y / 100) * 66 };
}

export default function ReplayPlayer() {
  const data = useReplayData();
  const { viewer, update } = useViewer();
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(30);
  const [onlyMine, setOnlyMine] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => {
      setT((now) => {
        const next = Math.min(END, now + TICK_MS * speed);
        if (next >= END) setPlaying(false);
        return next;
      });
    }, TICK_MS);
    return () => { if (timer.current != null) window.clearInterval(timer.current); };
  }, [playing, speed]);

  const second = Math.floor(t / 1000);
  const loaded = typeof data === "object" ? data : null;
  const live = useMemo(() => {
    if (!loaded) return null;
    const upTo = { from_ms: 0, to_ms: second * 1000 + 1 };
    const metric = (id: string, subject: { team_id?: string; player_id?: string }) => {
      try { return loaded.verifier.computeMetric(id, loaded.events, subject, upTo); } catch { return null; }
    };
    const hasPasses = (team: string) => loaded.events.some((e) => e.type === "pass" && e.team_id === team && e.match_clock_ms < upTo.to_ms);
    const team = (id: string, side: "nbr" | "riv") => (id.startsWith("pass_") || id === "ball_speed.v1") && !hasPasses(side) ? null : metric(id, { team_id: side });
    const recent = loaded.events.filter((e) => e.match_clock_ms <= second * 1000).slice(-8);
    return {
      score: { nbr: metric("goals.v1", { team_id: "nbr" }) ?? 0, riv: metric("goals.v1", { team_id: "riv" }) ?? 0 },
      possession: second > 0 ? metric("possession_time.v1", { team_id: "nbr" }) : null,
      shots: { nbr: metric("shots.v1", { team_id: "nbr" }) ?? 0, riv: metric("shots.v1", { team_id: "riv" }) ?? 0 },
      accuracy: { nbr: team("pass_accuracy.v1", "nbr"), riv: team("pass_accuracy.v1", "riv") },
      focus: { nbr: team(viewer.focus, "nbr"), riv: team(viewer.focus, "riv"), player: viewer.player ? metric(viewer.focus, { player_id: viewer.player }) : null },
      recent,
    };
  }, [loaded, second, viewer.focus, viewer.player]);

  const hold = 8000 * speed;
  const cues = loaded ? loaded.feed.cues.filter((c) => !onlyMine || !viewer.club || c.team === viewer.club) : [];
  const active = [...cues].reverse().find((c) => c.t_ms <= t && t - c.t_ms < hold) ?? null;
  const proof = (cue: Cue): "verified" | "logged" | "failed" => {
    if (!loaded || cue.status === "logged") return cue.status === "logged" ? "logged" : "failed";
    return cue.claim_ids.length > 0 && cue.claim_ids.every((id) => loaded.recheck[id]) ? "verified" : "failed";
  };
  const verifiedCount = loaded ? loaded.feed.claims.filter((c) => loaded.recheck[c.claim_id]).length : 0;
  const unit = (id: string) => loaded?.verifier.METRIC_UNITS[id] ?? "count";
  const focusLabel = FOCUS_METRICS.find((m) => m.id === viewer.focus)?.label ?? viewer.focus;
  const lang = viewer.language;
  const jumps = [{ label: "Kick-off", ms: 0 }, ...(loaded?.feed.cues.filter((c) => c.kind === "goal").map((c) => ({ label: `Goal ${c.clock}`, ms: c.t_ms })) ?? []), { label: "Half-time", ms: 2_700_000 }, { label: "Replay point", ms: END - 30_000 }];

  if (data === "failed") return <p className="md-muted" role="status">The replay could not load. The rest of this page still works.</p>;

  return (
    <section className="md-panel md-lr" aria-labelledby="md-lr-title">
      <div className="md-panel-head">
        <h2 id="md-lr-title">Replay the match</h2>
        <span className="md-muted md-small">{loaded ? `${loaded.feed.cues.length} timed overlays · ${verifiedCount} of ${loaded.feed.claims.length} claims re-verified here` : "Loading the event log…"}</span>
      </div>

      <div className={`md-bcast${viewer.club ? ` md-bcast-fan-${viewer.club}` : ""}`}>
        <svg viewBox="0 0 105 68" className="md-bcast-pitch" role="img" aria-label={`Pitch at ${clock(second)}: the last ${live?.recent.length ?? 0} logged events.`}>
          <rect width="105" height="68" fill="var(--md-pitch)" rx="1.5" />
          <g fill="none" stroke="var(--md-pitch-line)" strokeWidth="0.35">
            <rect x="1" y="1" width="103" height="66" /><path d="M52.5 1v66" /><circle cx="52.5" cy="34" r="9.15" />
            <rect x="1" y="13.85" width="16.5" height="40.3" /><rect x="87.5" y="13.85" width="16.5" height="40.3" />
          </g>
          {live?.recent.map((e, i, all) => {
            const p = spot(e);
            if (!p) return null;
            const last = i === all.length - 1;
            return <circle key={e.event_id} cx={p.x} cy={p.y} r={last ? 1.8 : 1} opacity={0.35 + (i / all.length) * 0.65}
              fill={last ? "var(--md-text)" : e.team_id === "nbr" ? "var(--md-home)" : "var(--md-away)"} />;
          })}
        </svg>
        <div className="md-bcast-bug" aria-label={`Score at ${clock(second)}`}>
          <span className={viewer.club === "nbr" ? "md-bug-mine" : undefined}>NBR</span>
          <strong className="md-mono">{live ? `${live.score.nbr}–${live.score.riv}` : "0–0"}</strong>
          <span className={viewer.club === "riv" ? "md-bug-mine" : undefined}>RIV</span>
          <span className="md-mono md-bug-clock">{clock(second)}</span>
        </div>
        <div className="md-bcast-third" aria-live="polite" aria-atomic="true">
          {active && (
            <div key={active.cue_id} className={`md-lt md-lt-${active.team ?? "neutral"} md-lt-${active.kind}`}>
              <span className="md-lt-text" lang={lang}>{active.text[viewer.persona][lang]}</span>
              <span className="md-lt-meta">
                <span className={`md-chip md-chip-${proof(active) === "verified" ? "verified" : proof(active) === "logged" ? "not-yet" : "failed"}`}>
                  <span aria-hidden="true">{proof(active) === "verified" ? "✓" : proof(active) === "logged" ? "•" : "✕"}</span> {PROOF[lang][proof(active)]}
                </span>
                {(viewer.club && active.team === viewer.club) || (viewer.player && active.players.includes(viewer.player)) ? (
                  <span className="md-chip md-chip-pill">{viewer.player && active.players.includes(viewer.player) ? "Your player" : "Your club"}</span>
                ) : null}
                <span className="md-mono md-subtle">{active.cue_id}</span>
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="md-lr-controls">
        <button type="button" className="md-btn md-btn-primary md-lr-play" onClick={() => { if (t >= END) setT(0); setPlaying((p) => !p); }} disabled={!loaded} aria-label={playing ? "Pause replay" : "Play replay"}>
          <Icon name={playing ? "pause" : "play"} size={16} /> {playing ? "Pause" : t >= END ? "Replay again" : "Play"}
        </button>
        <label className="md-lr-scrub">
          <span className="md-visually-hidden">Match clock</span>
          <input type="range" min={0} max={END} step={1000} value={second * 1000} disabled={!loaded}
            aria-valuetext={`${clock(second)} of ${clock(END / 1000)}`} onChange={(e) => setT(Number(e.target.value))} />
        </label>
        <div role="group" aria-label="Replay speed" className="md-seg">
          {SPEEDS.map((s) => <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>{s}×</button>)}
        </div>
      </div>
      <div className="md-lr-jumps" role="group" aria-label="Jump to">
        {jumps.map((j) => <button key={j.label} type="button" className="md-btn md-btn-secondary md-btn-sm" disabled={!loaded} onClick={() => { setT(Math.max(0, j.ms)); }}>{j.label}</button>)}
      </div>

      <div className="md-lr-prefs">
        <div role="group" aria-label="Overlay style" className="md-seg">
          {PERSONAS.map((p) => <button key={p.id} type="button" aria-pressed={viewer.persona === p.id} title={p.hint} onClick={() => update({ persona: p.id })}>{p.label}</button>)}
        </div>
        <div role="group" aria-label="Overlay language" className="md-seg">
          {LANGUAGES.map((l) => <button key={l.id} type="button" aria-pressed={lang === l.id} onClick={() => update({ language: l.id })}>{l.label}</button>)}
        </div>
        {viewer.club && (
          <div role="group" aria-label="Which overlays" className="md-seg">
            <button type="button" aria-pressed={!onlyMine} onClick={() => setOnlyMine(false)}>All overlays</button>
            <button type="button" aria-pressed={onlyMine} onClick={() => setOnlyMine(true)}>Only {TEAMS[viewer.club]}</button>
          </div>
        )}
      </div>

      <div className="md-lr-body">
        <div>
          <h3 className="md-h3">As it stands · recomputed from the log</h3>
          <table className="md-table md-lr-stats">
            <caption className="md-visually-hidden">Statistics from kick-off to {clock(second)}</caption>
            <thead><tr><th scope="col">Statistic</th><th scope="col" className={viewer.club === "nbr" ? "md-mine" : undefined}>{TEAMS.nbr}</th><th scope="col" className={viewer.club === "riv" ? "md-mine" : undefined}>{TEAMS.riv}</th></tr></thead>
            <tbody>
              <tr><th scope="row">Possession</th><td className="md-mono">{live?.possession != null ? shown("ratio", live.possession) : "–"}</td><td className="md-mono">{live?.possession != null ? shown("ratio", 1 - live.possession) : "–"}</td></tr>
              <tr><th scope="row">Shots</th><td className="md-mono">{live?.shots.nbr ?? 0}</td><td className="md-mono">{live?.shots.riv ?? 0}</td></tr>
              <tr><th scope="row">Pass accuracy</th><td className="md-mono">{live?.accuracy.nbr != null ? shown("ratio", live.accuracy.nbr) : "–"}</td><td className="md-mono">{live?.accuracy.riv != null ? shown("ratio", live.accuracy.riv) : "–"}</td></tr>
              {!["possession_time.v1", "shots.v1", "pass_accuracy.v1"].includes(viewer.focus) && (
                <tr className="md-focus-row"><th scope="row">{focusLabel} <span className="md-chip md-chip-pill">Your focus</span></th>
                  <td className="md-mono">{live?.focus.nbr != null ? shown(unit(viewer.focus), live.focus.nbr) : "–"}</td>
                  <td className="md-mono">{live?.focus.riv != null ? shown(unit(viewer.focus), live.focus.riv) : "–"}</td></tr>
              )}
            </tbody>
          </table>
          {viewer.player && (
            <p className="md-small">
              <Link className="md-link" href={`/match/nbr-riv/player/${viewer.player}`}>{playerName(viewer.player)}</Link>, your player · {focusLabel.toLowerCase()}: <strong className="md-mono">{live?.focus.player != null ? shown(unit(viewer.focus), live.focus.player) : "–"}</strong>
            </p>
          )}
          <p className="md-muted md-small">Figures come from the registered metrics over every event up to the clock. Change your focus statistic, club and player in <Link className="md-link" href="/workspace/settings#my-match">Settings</Link>.</p>
        </div>
        <div>
          <h3 className="md-h3">Event ticker</h3>
          <ol className="md-ticker" reversed>
            {[...(live?.recent ?? [])].reverse().slice(0, 6).map((e) => (
              <li key={e.event_id} className={viewer.player && e.player_id === viewer.player ? "md-mine" : undefined}>
                <span className="md-mono md-moment-clock">{clock(Math.floor(e.match_clock_ms / 1000))}</span>
                <span className={`md-feed-team md-feed-${e.team_id}`}>{e.team_id === "nbr" ? "NBR" : e.team_id === "riv" ? "RIV" : "—"}</span>
                <span>{TYPE_LABEL[e.type] ?? e.type.replace(/_/g, " ")}{e.player_id ? ` · ${playerName(e.player_id)}` : ""}{e.outcome && e.outcome !== "complete" ? ` · ${e.outcome}` : ""}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="md-lr-feed">
        <a className="md-btn md-btn-secondary" href="/overlays/nbr-riv.json" download>Download the overlay feed (JSON)</a>
        <p className="md-muted md-small">
          The same cues any graphics engine can read: time, kind, team, players, event ids, the claims behind every number, and text for each persona in English, Spanish and French. Cards and substitutions are logged events with no checking query yet, and are marked so. Spanish and French are AI-assisted templates awaiting native review.
        </p>
      </div>
    </section>
  );
}
