/** "Your match" on the overview: the viewer's club, player and focus statistic, each line verified in this browser. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { matchExport, playerName } from "./data";
import { FOCUS_METRICS, useViewer, type Viewer } from "./viewer";
import type { CheckedLine } from "./ask";
import type { CompactLog } from "./verifier";

const NAMES = matchExport.display_names;
const TEAMS: Record<string, string> = { nbr: NAMES.nbr ?? "Northbridge", riv: NAMES.riv ?? "Riverside" };

/** Build and verify the personal lines once the log and the reader have loaded. */
function usePersonalLines(viewer: Viewer, ready: boolean): CheckedLine[] | null {
  const [lines, setLines] = useState<CheckedLine[] | null>(null);
  useEffect(() => {
    if (!ready || (!viewer.club && !viewer.player)) { setLines(null); return; }
    let live = true;
    Promise.all([import("./generated/nbr-riv-events.json"), import("./verifier"), import("./ask")]).then(([log, verifier, ask]) => {
      const ctx = { events: verifier.expandLog(log.default as unknown as CompactLog), names: NAMES, teams: TEAMS, replayEndMs: matchExport.replay_end_ms, matchId: matchExport.match_id };
      const resolved = ask.resolveWindow({}, ctx.replayEndMs);
      if ("error" in resolved) return;
      const evidence = { match_id: ctx.matchId, event_ids: ctx.events.map((e) => e.event_id), window: { from_ms: 0, to_ms: ctx.replayEndMs } };
      const subjects = [viewer.club, viewer.player].filter((s): s is string => Boolean(s));
      const metrics = (subject: string) => [...new Set(subject === viewer.player ? ["goals.v1", viewer.focus] : [viewer.focus])] as (keyof typeof ask.METRICS)[];
      const out = subjects.flatMap((subject) => metrics(subject).map((m) => ask.measuredLine(m, subject, resolved, ctx, evidence)));
      if (live) setLines(out);
    }, () => { if (live) setLines([]); });
    return () => { live = false; };
  }, [viewer, ready]);
  return lines;
}

export function YourMatch() {
  const { viewer, ready } = useViewer();
  const lines = usePersonalLines(viewer, ready);
  const focus = FOCUS_METRICS.find((m) => m.id === viewer.focus)?.label ?? "";
  if (!ready) return null;
  if (!viewer.club && !viewer.player) {
    return (
      <section className="md-panel" aria-labelledby="md-yours-title">
        <span className="md-eyebrow">Make it your match</span>
        <h2 id="md-yours-title" className="md-sel-title">Follow a club, a player or one statistic</h2>
        <p className="md-muted">Pick them once and the replay overlays, this card and player focus follow you, in English, Spanish or French.</p>
        <Link href="/workspace/settings#my-match" className="md-btn md-btn-secondary">Set up My match</Link>
      </section>
    );
  }
  return (
    <section className="md-panel" aria-labelledby="md-yours-title">
      <span className="md-eyebrow">Your match · {focus}</span>
      <h2 id="md-yours-title" className="md-sel-title">{[viewer.club && TEAMS[viewer.club], viewer.player && playerName(viewer.player)].filter(Boolean).join(" · ")}</h2>
      {lines === null ? <p className="md-muted md-small" role="status">Checking against the log…</p> : (
        <ul className="md-phase-lines">
          {lines.map((l) => (
            <li key={l.claim.claim_id}>
              <span className={`md-chip md-chip-${l.result.status === "verified" ? "verified" : "failed"}`}><span aria-hidden="true">{l.result.status === "verified" ? "✓" : "✕"}</span> {l.result.status === "verified" ? "Verified" : "Not verified"}</span>
              <span>{l.claim.text}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="md-btn-row">
        <Link href="/match/nbr-riv/live" className="md-btn md-btn-primary">Watch with overlays</Link>
        {viewer.player && <Link href={`/match/nbr-riv/player/${viewer.player}`} className="md-btn md-btn-secondary">Player focus</Link>}
      </div>
    </section>
  );
}
