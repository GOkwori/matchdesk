/**
 * Explainable match reading built only from registered metrics and verified sentences.
 *
 * Control vs chaos: the match is cut into five-minute windows and each window is labelled by a
 * fixed, published rule over recomputed figures (possession, pass accuracy, ball recoveries).
 * Adjacent windows with the same label become a phase, and each phase carries the verified
 * sentences that justify it. Player focus: one player's figures, each stated as a claim and
 * checked by the parity-tested verifier. Pressure changes: from one window to the next, the side
 * pressing harder (its opponents played more passes under pressure) changes, or the pressure
 * in the match rises or falls sharply; each change carries the verified counts on both sides of
 * it. No model writes any of this; nothing here is opinion.
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

/** A side is pressing harder when its opponents played at least this many more passes under pressure. */
export const PRESSING_MARGIN = 3;
/** Pressure in the match has changed sharply when passes under pressure, both sides together, move by this many. */
export const PRESSURE_SWING = 8;

export type PressureChange = {
  fromMs: number;
  toMs: number;
  /** The side pressing harder in this window, or null when neither leads by the margin. */
  presser: string | null;
  previousPresser: string | null;
  total: number;
  previousTotal: number;
  kinds: ("side" | "up" | "down")[];
  scope: string;
  reason: string;
  lines: CheckedLine[];
};

/** Who pressed harder in a window: the side whose opponents played clearly more passes under pressure. */
export function presserOf(w: WindowReading, teams: readonly string[]): string | null {
  const [a, b] = teams;
  const onA = w.pressured[a];
  const onB = w.pressured[b];
  if (onA - onB >= PRESSING_MARGIN) return b;
  if (onB - onA >= PRESSING_MARGIN) return a;
  return null;
}

/** Each window where the pressing side changed, or the pressure rose or fell sharply, with its proof. */
export function pressureChanges(ctx: MatchContext): PressureChange[] {
  const windows = readWindows(ctx);
  const teams = Object.keys(ctx.teams);
  const evidence = evidenceFor(ctx);
  const total = (w: WindowReading) => teams.reduce((sum, t) => sum + w.pressured[t], 0);
  const out: PressureChange[] = [];
  for (let i = 1; i < windows.length; i += 1) {
    const before = windows[i - 1];
    const now = windows[i];
    const presser = presserOf(now, teams);
    const previousPresser = presserOf(before, teams);
    const kinds: PressureChange["kinds"] = [];
    if (presser !== previousPresser && presser != null) kinds.push("side");
    if (total(now) - total(before) >= PRESSURE_SWING) kinds.push("up");
    if (total(before) - total(now) >= PRESSURE_SWING) kinds.push("down");
    if (!kinds.length) continue;
    const resolvedNow = phaseWindow(ctx, now.fromMs, now.toMs);
    const resolvedBefore = phaseWindow(ctx, before.fromMs, before.toMs);
    const lines = [
      ...teams.map((t) => measuredLine("pressured_passes.v1", t, resolvedBefore, ctx, evidence)),
      ...teams.map((t) => measuredLine("pressured_passes.v1", t, resolvedNow, ctx, evidence)),
    ];
    const parts: string[] = [];
    if (kinds.includes("side") && presser) {
      const victim = teams.find((t) => t !== presser)!;
      parts.push(`${ctx.teams[presser]} pressed harder: ${ctx.teams[victim]} played ${now.pressured[victim]} passes under pressure, ${ctx.teams[presser]} ${now.pressured[presser]}`);
    }
    if (kinds.includes("up")) parts.push(`pressure rose from ${total(before)} to ${total(now)} passes under pressure`);
    if (kinds.includes("down")) parts.push(`pressure fell from ${total(before)} to ${total(now)} passes under pressure`);
    const reason = parts.join("; ").replace(/^./, (c) => c.toUpperCase()) + ".";
    out.push({ fromMs: now.fromMs, toMs: now.toMs, presser, previousPresser, total: total(now), previousTotal: total(before), kinds, scope: resolvedNow.scope, reason, lines });
  }
  return out;
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
