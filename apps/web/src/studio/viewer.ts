/**
 * The viewer's own match: favourite club and player, analyst or fan, language and one focus
 * statistic. Kept on this device only (no account, nothing sent anywhere) and shared between
 * screens through a window event, so the replay, the overview and Settings stay in step.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

export type Persona = "analyst" | "fan" | "caption";
export type ViewerLanguage = "en" | "es" | "fr";
export type Viewer = {
  club: "nbr" | "riv" | null;
  player: string | null;
  persona: Persona;
  language: ViewerLanguage;
  focus: FocusMetric;
};

export const PERSONAS: readonly { id: Persona; label: string; hint: string }[] = [
  { id: "fan", label: "Fan", hint: "Plain words" },
  { id: "analyst", label: "Analyst", hint: "Every figure, exact clock" },
  { id: "caption", label: "Broadcast caption", hint: "Short on-screen strap" },
];

export const LANGUAGES: readonly { id: ViewerLanguage; label: string }[] = [
  { id: "en", label: "English" },
  { id: "es", label: "Español" },
  { id: "fr", label: "Français" },
];

/** Statistics a viewer can pin. Each is a registered metric the verifier can recompute. */
export const FOCUS_METRICS = [
  { id: "possession_time.v1", label: "Possession" },
  { id: "pass_accuracy.v1", label: "Pass accuracy" },
  { id: "shots.v1", label: "Shots" },
  { id: "synthetic_xg.v1", label: "Synthetic xG" },
  { id: "progressive_passes.v1", label: "Progressive passes" },
  { id: "pass_difficulty.v1", label: "Pass difficulty" },
  { id: "ball_speed.v1", label: "Ball speed (estimated)" },
  { id: "pressured_passes.v1", label: "Passes under pressure" },
  { id: "tackles.v1", label: "Tackles" },
  { id: "recoveries.v1", label: "Ball recoveries" },
  { id: "top_speed.v1", label: "Top speed (tracking)" },
  { id: "distance_covered.v1", label: "Distance covered (tracking)" },
  { id: "sprints.v1", label: "Sprints (tracking)" },
] as const;
export type FocusMetric = (typeof FOCUS_METRICS)[number]["id"];

const KEY = "md.viewer";
const EVENT = "md-viewer";
const PLAYER_ID = /^(?:nbr|riv)-(?:0[1-9]|1[0-6])$/;

export const DEFAULT_VIEWER: Viewer = { club: null, player: null, persona: "fan", language: "en", focus: "pass_accuracy.v1" };

/** Read stored choices, keeping only values this build understands. */
export function readViewer(): Viewer {
  let stored: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(KEY) ?? "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) stored = parsed as Record<string, unknown>;
  } catch { /* nothing stored, or storage blocked */ }
  const pick = <T,>(value: unknown, allowed: readonly T[], fallback: T): T => (allowed.includes(value as T) ? (value as T) : fallback);
  return {
    club: pick(stored.club, ["nbr", "riv", null] as const, null),
    player: typeof stored.player === "string" && PLAYER_ID.test(stored.player) ? stored.player : null,
    persona: pick(stored.persona, PERSONAS.map((p) => p.id), DEFAULT_VIEWER.persona),
    language: pick(stored.language, LANGUAGES.map((l) => l.id), DEFAULT_VIEWER.language),
    focus: pick(stored.focus, FOCUS_METRICS.map((m) => m.id), DEFAULT_VIEWER.focus),
  };
}

/** Store choices on this device and tell every open screen. */
export function saveViewer(next: Viewer) {
  try { window.localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* applies for this visit only */ }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: next }));
}

/** The current choices, kept in step across components; `ready` is false until the device has been read. */
export function useViewer(): { viewer: Viewer; ready: boolean; update: (patch: Partial<Viewer>) => void } {
  const [viewer, setViewer] = useState<Viewer>(DEFAULT_VIEWER);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setViewer(readViewer());
    setReady(true);
    const onChange = (e: Event) => setViewer((e as CustomEvent<Viewer>).detail ?? readViewer());
    window.addEventListener(EVENT, onChange);
    return () => window.removeEventListener(EVENT, onChange);
  }, []);
  const update = useCallback((patch: Partial<Viewer>) => {
    const next = { ...readViewer(), ...patch };
    // A favourite player from the other club would contradict the favourite club.
    if (patch.club !== undefined && next.player && next.club && !next.player.startsWith(next.club)) next.player = null;
    if (patch.player && !patch.club) next.club = patch.player.startsWith("nbr") ? "nbr" : "riv";
    saveViewer(next);
  }, []);
  return { viewer, ready, update };
}
