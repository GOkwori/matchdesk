/**
 * Broadcast overlay: the timed cues from the overlay feed drawn as lower-thirds, with a score
 * bug, on a transparent page that OBS, vMix or a vision mixer loads as a browser source. Every
 * cue's claims are re-verified in this browser first; a cue that does not verify is never
 * drawn. Settings come from the address: style, lang, speed, from, bg, bug, and voice=1 to read
 * each graphic aloud (OBS can capture the browser source's audio).
 */
"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { clock, matchExport } from "./data";
import type { Claim, CompactLog, VEvent } from "./verifier";
import { speak } from "./voice";

type Style = "fan" | "analyst" | "caption";
type Lang = "en" | "es" | "fr";
type Cue = {
  cue_id: string; t_ms: number; kind: string; team: string | null; status: string; claim_ids: string[];
  text: Record<Style, Record<Lang, string>>;
};
type Feed = { replay_end_ms: number; cues: Cue[]; claims: { claim_id: string; text: string; status: string; claim: Claim }[] };
type Loaded = { events: VEvent[]; cues: Cue[]; verified: Set<string> };

const END = matchExport.replay_end_ms;
const NAMES = matchExport.display_names;
const HOLD_SECONDS = 8;
const TICK_MS = 100;
const SPEEDS = [1, 2, 5, 10, 30, 60];
const KIND: Record<string, Record<Lang, string>> = {
  goal: { en: "Goal", es: "Gol", fr: "But" },
  stats: { en: "Match stats", es: "Estadísticas", fr: "Statistiques" },
  shot_speed: { en: "Shot speed", es: "Velocidad del tiro", fr: "Vitesse du tir" },
  top_speed: { en: "Top speed", es: "Velocidad punta", fr: "Vitesse de pointe" },
  distance: { en: "Distance", es: "Distancia", fr: "Distance" },
  card: { en: "Card", es: "Tarjeta", fr: "Carton" },
  substitution: { en: "Substitution", es: "Cambio", fr: "Remplacement" },
  spell: { en: "Control", es: "Dominio", fr: "Domination" },
  spotlight: { en: "Spotlight", es: "Destacado", fr: "Coup de projecteur" },
};
const VERIFIED: Record<Lang, string> = { en: "Verified", es: "Verificado", fr: "Vérifié" };

function pick<T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

/** "34:00" or "34" to match milliseconds, clamped to the replay. */
function startAt(value: string | null): number {
  if (!value) return 0;
  const [m, s] = value.split(":").map(Number);
  const ms = ((Number.isFinite(m) ? m : 0) * 60 + (Number.isFinite(s) ? s : 0)) * 1000;
  return Math.min(Math.max(ms, 0), END - 1000);
}

/** Load the log, the verifier and the feed, and keep only cues whose every claim re-verifies here. */
function useVerifiedCues(): Loaded | null {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  useEffect(() => {
    let live = true;
    Promise.all([import("./generated/nbr-riv-events.json"), import("./verifier"), import("./generated/nbr-riv-overlays.json")]).then(
      ([log, verifier, feedModule]) => {
        const events = verifier.expandLog(log.default as unknown as CompactLog);
        const feed = feedModule.default as unknown as Feed;
        const evidence = { match_id: matchExport.match_id, event_ids: events.map((e) => e.event_id), window: { from_ms: 0, to_ms: feed.replay_end_ms } };
        const ok = new Set(
          feed.claims
            .filter((r) => r.status === "verified" && r.claim.text === r.text && verifier.verifyClaim(r.claim, evidence, events, NAMES).status === "verified")
            .map((r) => r.claim_id),
        );
        const verified = new Set(feed.cues.filter((c) => c.claim_ids.length > 0 && c.claim_ids.every((id) => ok.has(id))).map((c) => c.cue_id));
        if (live) setLoaded({ events, cues: feed.cues, verified });
      },
      () => undefined,
    );
    return () => { live = false; };
  }, []);
  return loaded;
}

export function BroadcastOverlay() {
  const params = useSearchParams();
  const style = pick(params.get("style"), ["fan", "analyst", "caption"] as const, "caption");
  const lang = pick(params.get("lang"), ["en", "es", "fr"] as const, "en");
  const speed = Number(pick(params.get("speed"), SPEEDS.map(String), "10"));
  const bg = pick(params.get("bg"), ["transparent", "dark", "green"] as const, "transparent");
  const bug = params.get("bug") !== "0";
  const voiced = params.get("voice") === "1";
  const from = startAt(params.get("from"));
  const loaded = useVerifiedCues();
  const [t, setT] = useState(from);

  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  useEffect(() => { document.body.dataset.bg = bg; }, [bg]);
  useEffect(() => {
    if (!loaded) return;
    setT(from);
    const id = window.setInterval(() => setT((now) => (now + TICK_MS * speed >= END ? from : now + TICK_MS * speed)), TICK_MS);
    return () => window.clearInterval(id);
  }, [loaded, from, speed]);

  const score = useMemo(() => {
    const s = { nbr: 0, riv: 0 };
    for (const e of loaded?.events ?? []) {
      if (e.match_clock_ms > t) break;
      if (e.type === "goal" && (e.team_id === "nbr" || e.team_id === "riv")) s[e.team_id] += 1;
    }
    return s;
  }, [loaded, t]);
  const hold = HOLD_SECONDS * 1000 * speed;
  const active = loaded ? [...loaded.cues].reverse().find((c) => c.t_ms <= t && t - c.t_ms < hold && loaded.verified.has(c.cue_id)) ?? null : null;
  const activeId = active?.cue_id ?? null;
  useEffect(() => {
    if (voiced && active) void speak({ kind: "cue", id: active.cue_id, lang, text: active.text.fan[lang] });
  }, [voiced, activeId]);

  return (
    <main className="md-bc" data-style={style}>
      <h1 className="md-visually-hidden">MatchDesk broadcast overlay</h1>
      {bug && (
        <div className="md-bc-bug" aria-label="Score">
          <span className="md-bc-team md-bc-nbr">NBR</span>
          <span className="md-bc-score">{score.nbr}–{score.riv}</span>
          <span className="md-bc-team md-bc-riv">RIV</span>
          <span className="md-bc-clock">{clock(t / 1000)}</span>
        </div>
      )}
      <div className="md-bc-slot" role="status" aria-live="polite">
        {active && (
          <div key={active.cue_id} className={`md-bc-third md-bc-team-${active.team ?? "none"}`}>
            <span className="md-bc-kind">{KIND[active.kind]?.[lang] ?? active.kind}</span>
            <span className="md-bc-text">{active.text[style][lang]}</span>
            <span className="md-bc-proof" title={active.claim_ids.join(" · ")}>✓ {VERIFIED[lang]}</span>
          </div>
        )}
      </div>
    </main>
  );
}
