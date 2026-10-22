/**
 * Explainable match reading built only from registered metrics and verified sentences.
 *
 * Control vs chaos: the match is cut into five-minute windows and each window is labelled by a
 * fixed, published rule over recomputed figures (possession, pass accuracy, ball recoveries).
 * Adjacent windows with the same label become a phase, and each phase carries the verified
 * sentences that justify it. Player focus: one player's figures, each stated as a claim and
 * checked by the parity-tested verifier. No model writes any of this; nothing here is opinion.
 */
import { measuredLine, resolveWindow, type CheckedLine, type MatchContext, type Metric } from "./ask.ts";
import { computeMetric, type Evidence, type VEvent, type Window } from "./verifier.ts";

export const PHASE_MINUTES = 5;
/** A team is in control of a window when it has at least this share of the ball... */
export const CONTROL_POSSESSION = 0.6;
/** ...and completes at least this share of its passes. */
export const CONTROL_ACCURACY = 0.85;
/** A window is chaotic when the ball is won back this often per minute, by both teams together. */
export const CHAOS_RECOVERIES_PER_MINUTE = 3.2;

export type PhaseKind = "control" | "chaos" | "contested";

export type WindowReading = {
  fromMs: number;
  toMs: number;
  kind: PhaseKind;
  team: string | null;
  possession: number; // home share, 0..1
  accuracy: Record<string, number | null>;
  recoveries: Record<string, number>;
  pressured: Record<string, number>;
  ballSpeed: Record<string, number | null>;
  shots: Record<string, number>;
};

export type Phase = {
  fromMs: number;
  toMs: number;
  kind: PhaseKind;
  team: string | null;
  scope: string;
  reason: string;
  lines: CheckedLine[];
  windows: WindowReading[];
};

const MINUTE_MS = 60_000;

/** Evidence binding every event to the replay point, as the server's record does. */
export function evidenceFor(ctx: MatchContext): Evidence {
  return { match_id: ctx.matchId, event_ids: ctx.events.map((e) => e.event_id), window: { from_ms: 0, to_ms: ctx.replayEndMs } };
}

function hasPasses(ctx: MatchContext, team: string, window: Window): boolean {
  return ctx.events.some((e) => e.type === "pass" && e.team_id === team && window.from_ms <= e.match_clock_ms && e.match_clock_ms < window.to_ms);
}

/** Recompute one window's figures and label it by the published rule. */
export function readWindow(ctx: MatchContext, fromMs: number, toMs: number): WindowReading {
  const window: Window = { from_ms: fromMs, to_ms: toMs };
  const teams = Object.keys(ctx.teams);
  const [home] = teams;
  const per = <T,>(fn: (team: string) => T) => Object.fromEntries(teams.map((t) => [t, fn(t)])) as Record<string, T>;
  const metric = (m: Metric, team: string) => computeMetric(m, ctx.events, { team_id: team }, window);
  const reading: WindowReading = {
    fromMs,
    toMs,
    kind: "contested",
    team: null,
    possession: metric("possession_time.v1", home),
    accuracy: per((t) => (hasPasses(ctx, t, window) ? metric("pass_accuracy.v1", t) : null)),
    recoveries: per((t) => metric("recoveries.v1", t)),
    pressured: per((t) => metric("pressured_passes.v1", t)),
    ballSpeed: per((t) => (hasPasses(ctx, t, window) ? metric("ball_speed.v1", t) : null)),
    shots: per((t) => metric("shots.v1", t)),
  };
  const minutes = (toMs - fromMs) / MINUTE_MS;
  const recoveries = teams.reduce((sum, t) => sum + reading.recoveries[t], 0);
  if (recoveries / minutes >= CHAOS_RECOVERIES_PER_MINUTE) {
    reading.kind = "chaos";
    return reading;
  }
  for (const team of teams) {
    const share = team === home ? reading.possession : 1 - reading.possession;
    const accuracy = reading.accuracy[team];
    if (share >= CONTROL_POSSESSION && accuracy != null && accuracy >= CONTROL_ACCURACY) {
      reading.kind = "control";
      reading.team = team;
    }
  }
  return reading;
}

/** Every five-minute window to the replay point; the last one ends at the replay point. */
export function readWindows(ctx: MatchContext): WindowReading[] {
  const out: WindowReading[] = [];
  for (let from = 0; from < ctx.replayEndMs; from += PHASE_MINUTES * MINUTE_MS) {
    out.push(readWindow(ctx, from, Math.min(from + PHASE_MINUTES * MINUTE_MS, ctx.replayEndMs)));
  }
  return out;
}

function phaseWindow(ctx: MatchContext, fromMs: number, toMs: number) {
  const plan = { from_minute: fromMs === 0 ? null : fromMs / MINUTE_MS, to_minute: toMs >= ctx.replayEndMs ? null : toMs / MINUTE_MS };
  const resolved = resolveWindow(plan, ctx.replayEndMs);
  if ("error" in resolved) throw new Error(resolved.error);
  return resolved;
}

/** Join same-label windows into phases and attach the verified sentences behind each label. */
export function controlPhases(ctx: MatchContext): Phase[] {
  const windows = readWindows(ctx);
  const groups: WindowReading[][] = [];
  for (const w of windows) {
    const last = groups.at(-1);
    if (last && last[0].kind === w.kind && last[0].team === w.team) last.push(w);
    else groups.push([w]);
  }
  const evidence = evidenceFor(ctx);
  const teams = Object.keys(ctx.teams);
  return groups.map((group) => {
    const fromMs = group[0].fromMs;
    const toMs = group.at(-1)!.toMs;
    const resolved = phaseWindow(ctx, fromMs, toMs);
    const line = (metric: Metric, subject: string) => measuredLine(metric, subject, resolved, ctx, evidence);
    const { kind, team } = group[0];
    const span = group.length === 1 ? "This window" : `Each of these ${group.length} windows`;
    let reason: string;
    let lines: CheckedLine[];
    if (kind === "control" && team) {
      reason = `${span} met the control rule for ${ctx.teams[team]}: at least ${CONTROL_POSSESSION * 100}% of the ball and at least ${CONTROL_ACCURACY * 100}% of passes completed.`;
      lines = [line("possession_time.v1", team), line("pass_accuracy.v1", team)];
    } else if (kind === "chaos") {
      reason = `${span} met the chaos rule: the ball was won back at least ${CHAOS_RECOVERIES_PER_MINUTE} times a minute between the two sides.`;
      lines = [...teams.map((t) => line("recoveries.v1", t)), ...teams.map((t) => line("pressured_passes.v1", t))];
    } else {
      reason = `${span} met neither rule: no side held at least ${CONTROL_POSSESSION * 100}% of the ball with ${CONTROL_ACCURACY * 100}% passing, and the ball was not won back often enough to call it chaos.`;
      lines = [line("possession_time.v1", teams[0]), ...teams.map((t) => line("recoveries.v1", t))];
    }
    return { fromMs, toMs, kind, team, scope: resolved.scope, reason, lines, windows: group };
  });
}

/** Player focus: the registered metrics for one player to the replay point, each one verified. */
export const PLAYER_METRICS: readonly Metric[] = [
  "goals.v1", "shots.v1", "synthetic_xg.v1", "pass_accuracy.v1", "pass_distance.v1", "progressive_passes.v1",
  "pass_difficulty.v1", "pressured_passes.v1", "tackles.v1", "interceptions.v1", "recoveries.v1",
];

export type PlayerFocus = {
  id: string;
  name: string;
  team: string;
  passes: number;
  lines: CheckedLine[];
  skipped: Metric[];
  events: VEvent[];
};

/** Build a player's verified profile; pass averages are skipped when there are no passes to average. */
export function playerFocus(ctx: MatchContext, playerId: string, team: string): PlayerFocus {
  const resolved = phaseWindow(ctx, 0, ctx.replayEndMs);
  const evidence = evidenceFor(ctx);
  const events = ctx.events.filter((e) => e.player_id === playerId && e.match_clock_ms < ctx.replayEndMs);
  const passes = events.filter((e) => e.type === "pass").length;
  const averages = new Set<Metric>(["pass_accuracy.v1", "pass_distance.v1", "pass_difficulty.v1"]);
  const skipped = PLAYER_METRICS.filter((m) => averages.has(m) && passes === 0);
  const lines = PLAYER_METRICS.filter((m) => !skipped.includes(m)).map((m) => measuredLine(m, playerId, resolved, ctx, evidence));
  return { id: playerId, name: ctx.names[playerId] ?? playerId, team, passes, lines, skipped, events };
}
