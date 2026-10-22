/**
 * Ask MatchDesk: answers questions about the app and the match, with proof.
 *
 * The engine writes every number. A question is read into a small query plan (by the
 * built-in parser, or by an optional language model that may only return a plan), the
 * registered metrics compute the figures, each factual sentence is built as a claim, and the
 * parity-tested verifier checks it before it is shown. Guidance comes from a fixed help
 * index. Nothing here calls the network, so Node can test it directly.
 */
import { computeMetric, roundHalfUp, verifyClaim, type Claim, type Evidence, type Names, type Result, type Subject, type VEvent, type Window } from "./verifier.ts";

export const METRICS = {
  "goals.v1": { unit: "count", label: "goals" },
  "shots.v1": { unit: "count", label: "shots" },
  "pass_accuracy.v1": { unit: "ratio", label: "pass accuracy" },
  "synthetic_xg.v1": { unit: "synthetic_xg", label: "synthetic xG" },
  "final_third_entries.v1": { unit: "count", label: "final-third entries" },
  "possession_time.v1": { unit: "ratio", label: "possession" },
} as const;
export type Metric = keyof typeof METRICS;

/** A window in whole match minutes; missing bounds mean kick-off and the replay point. */
export type PlanWindow = { period?: 1 | 2 | null; from_minute?: number | null; to_minute?: number | null; last_minutes?: number | null };

/** What a question asks for. Built by the parser or by a model; always validated. */
export type Plan =
  | { intent: "metric"; metric: Metric; subjects: string[]; window: PlanWindow }
  | { intent: "score"; window: PlanWindow }
  | { intent: "scorers"; window: PlanWindow }
  | { intent: "summary"; subject: string; window: PlanWindow }
  | { intent: "help"; topic: string }
  | { intent: "out_of_scope"; reason: "prediction" | "other_match" | "personal" | "unsupported" }
  | { intent: "unknown" };

export type Link = { href: string; label: string };
export type CheckedLine = { claim: Claim; result: Result };
export type Answer =
  | { kind: "help"; text: string; link?: Link }
  | { kind: "match"; scope: string; lines: CheckedLine[]; derived?: string; note?: string }
  | { kind: "decline"; text: string }
  | { kind: "unknown"; text: string };

export type MatchContext = {
  events: readonly VEvent[];
  names: Names;
  teams: Readonly<Record<string, string>>; // team id -> short display name
  replayEndMs: number;
  matchId: string;
};

export const SUGGESTIONS: readonly string[] = [
  "What's the score?",
  "Who scored?",
  "Who had more shots in the second half?",
  "Possession after 60 minutes",
  "How many shots did Okafor take?",
  "What does Eligible mean?",
];

/* ---------- Help index ---------- */

type HelpTopic = { id: string; patterns: RegExp[]; text: string; link?: Link };

const STORY = "/story/okafor-header-restores-northbridge-lead";

export const HELP: readonly HelpTopic[] = [
  { id: "tour", patterns: [/\btour\b/, /guide me/, /show me around/, /where (do|should) i start/, /\bget started\b/],
    text: "The guided tour takes about three minutes: a goal, its evidence, the AI agents, a recalculated claim, the review queue, the composer and the fan story.",
    link: { href: "/match/nbr-riv?tour=1", label: "Start the tour" } },
  { id: "eligible", patterns: [/\beligible\b/, /\beligibility\b/],
    text: "Eligible means every factual sentence in a draft is verified and nothing is blocked. An eligible draft can go to a human producer for approval; it is not published until they approve it.",
    link: { href: "/producer/queue", label: "Open the review queue" } },
  { id: "statuses", patterns: [/\bverified\b/, /needs revision/, /\bblocked\b/, /supported inference/, /not verifiable/, /what do the (statuses|chips|badges)/, /\bstatus(es)?\b/],
    text: "Verified: the engine recomputed the figure from the event log and it matches. Supported inference: the cited events exist, but the meaning is a judgement. Needs revision: the figure or the words don't match the events. Blocked: the claim cites events it may not use. Not verifiable yet: the events it needs haven't happened at this point in the replay.",
    link: { href: "/match/nbr-riv/evidence/CL-0214", label: "See a claim being checked" } },
  { id: "how", patterns: [/how (does|do) (the )?(verification|verifier|checking|checks?) work/, /how (is|are) .* (checked|verified)/, /\bevidence\b/, /\bproof\b/, /how do you know/],
    text: "Every factual sentence carries a structured claim: a metric, a team or player, a time window and a value. The verifier recalculates that value from all the recorded events and checks that the sentence states exactly that figure about exactly that subject.",
    link: { href: "/match/nbr-riv/evidence/CL-0214", label: "Open the evidence screen" } },
  { id: "approve", patterns: [/\bapprov/, /\bpublish/, /human (gate|producer|review)/, /who decides/, /send (it )?out/],
    text: "Only a human producer can approve a draft, and only after it is eligible. In this demo the Approve button stays locked: the point is that AI and code can prepare a story, but a person decides.",
    link: { href: "/producer/publish/D-031", label: "Open publication" } },
  { id: "composer", patterns: [/\bcompos/, /\bedit\b/, /\bdraft\b/, /\bfix\b/, /\brewrite/],
    text: "The composer re-verifies every sentence as you type. Change 58% to 60% and it fails; remove the unsupported sentence and the draft becomes eligible.",
    link: { href: "/producer/compose/D-031", label: "Open the composer" } },
  { id: "queue", patterns: [/\bqueue\b/, /\breview\b/],
    text: "The review queue lists drafts waiting for a producer, with what is blocking each one.",
    link: { href: "/producer/queue", label: "Open the review queue" } },
  { id: "agents", patterns: [/\bagents?\b/, /\bfoundry\b/, /\bazure\b/, /\bai\b/, /\bmodel\b/, /\bgpt\b/, /\bllm\b/],
    text: "Four AI specialists on Microsoft Foundry draft the insights: an analyst, a tactician, a writer and a reviewer. Code verifies everything they write. The Insights screen replays a recorded live run, including the claims code rejected.",
    link: { href: "/match/nbr-riv/insights", label: "See the agents' run" } },
  { id: "story", patterns: [/\bfans?\b/, /\bstory\b/, /\baudience\b/, /\bspanish\b/, /\bfrench\b/, /\blanguages?\b/, /\btranslat/],
    text: "Fans get a short verified story with its checks shown, in English, Spanish or French. Spanish and French versions need a human language review before they can be published.",
    link: { href: STORY, label: "Open the fan story" } },
  { id: "moments", patterns: [/\bmoments?\b/, /\btimeline\b/, /key events/],
    text: "Moments are detected from the event log: goals, cards, big chances and substitutions, each linked to the events that prove it.",
    link: { href: "/match/nbr-riv/moments", label: "Open moments" } },
  { id: "tactical", patterns: [/\btactic/, /\bshot map\b/, /\bpitch\b/, /\bformation/],
    text: "Tactical analysis shows shot locations and territory computed from event coordinates. There is no player-tracking data.",
    link: { href: "/match/nbr-riv/tactical", label: "Open tactical analysis" } },
  { id: "data", patterns: [/\breal\b/, /\bsynthetic\b/, /\bfake\b/, /where does the data/, /\bdata\b/, /is this live/],
    text: "The match is synthetic: Northbridge FC v Riverside United, generated from a fixed seed into 1,421 events and replayed to 67:12. No real players, clubs or feeds are used.",
    link: { href: "/about", label: "About MatchDesk" } },
  { id: "search", patterns: [/\bsearch\b/, /\bfind\b/, /\bshortcut/, /ctrl ?k/, /command/],
    text: "Press Ctrl K (⌘ K on a Mac) to jump to any screen, moment, claim or draft." },
  { id: "settings", patterns: [/\bsettings?\b/, /\btheme\b/, /dark mode/, /light mode/, /reduced motion/, /text size/, /\bpreferences?\b/],
    text: "Theme, reduced motion, text size and technical IDs are in Settings.",
    link: { href: "/workspace/settings", label: "Open settings" } },
  { id: "activity", patterns: [/\bactivity\b/, /\baudit\b/, /\bhistory\b/, /\blog\b/],
    text: "Activity & Audit lists every verification and producer action in order.",
    link: { href: "/workspace/activity", label: "Open activity" } },
  { id: "what", patterns: [/what (is|does) matchdesk/, /what can (you|i) do/, /what is this/, /\bhelp\b/, /what can i ask/],
    text: "MatchDesk turns match events into stories you can check: AI drafts, code verifies every claim against the event log, and a human approves. Ask me about the match, such as the score, shots, possession or xG for a team, player or part of the game, or about how the app works.",
    link: { href: "/about", label: "About MatchDesk" } },
];

/* ---------- Parsing ---------- */

const WORD_NUMBERS: Readonly<Record<string, number>> = {
  five: 5, ten: 10, fifteen: 15, twenty: 20, "twenty-five": 25, thirty: 30, forty: 40, "forty-five": 45, fifty: 50, sixty: 60,
};

function normalise(question: string): string {
  return question.toLowerCase().replace(/[’‘]/g, "'").replace(/[′]/g, "'").replace(/\s+/g, " ").trim();
}

function minuteValue(token: string): number | null {
  if (/^[0-9]{1,3}$/.test(token)) return Number(token);
  return WORD_NUMBERS[token] ?? null;
}

const MIN = "([0-9]{1,3}|five|ten|fifteen|twenty|twenty-five|thirty|forty|forty-five|fifty|sixty)";
const UNIT = "(?:'|\\s*(?:min(?:ute)?s?|mins?))?";

export function parseWindow(q: string): PlanWindow {
  if (/\b(first|1st|opening) half\b|\bbefore (half[- ]?time|the break)\b/.test(q)) return { period: 1 };
  if (/\b(second|2nd) half\b|\bafter (half[- ]?time|the break)\b|\bsince (half[- ]?time|the break)\b/.test(q)) return { period: 2 };
  let m = new RegExp(`\\b(?:last|final) ${MIN}${UNIT}`).exec(q);
  if (m) return { last_minutes: minuteValue(m[1]) };
  m = new RegExp(`\\bbetween (?:the )?${MIN}(?:st|nd|rd|th)?${UNIT} and (?:the )?${MIN}(?:st|nd|rd|th)?${UNIT}`).exec(q);
  if (m) return { from_minute: minuteValue(m[1]), to_minute: minuteValue(m[2]) };
  m = new RegExp(`\\b(?:after|since|from) (?:the )?${MIN}(?:st|nd|rd|th)?${UNIT}`).exec(q);
  if (m) return { from_minute: minuteValue(m[1]) };
  m = new RegExp(`\\b(?:before|by|until|up to) (?:the )?${MIN}(?:st|nd|rd|th)?${UNIT}`).exec(q);
  if (m) return { to_minute: minuteValue(m[1]) };
  m = new RegExp(`\\b(?:first|opening) ${MIN}${UNIT}`).exec(q);
  if (m) return { to_minute: minuteValue(m[1]) };
  return {};
}

function parseMetric(q: string): Metric | null {
  if (/\bxg\b|expected goals/.test(q)) return "synthetic_xg.v1";
  if (/possession|had the ball|ball time|more of the ball/.test(q)) return "possession_time.v1";
  if (/pass(ing)? (accuracy|completion|success)|passes completed|completed passes|accurate pass|passing/.test(q)) return "pass_accuracy.v1";
  if (/final[- ]third|attacking third/.test(q)) return "final_third_entries.v1";
  if (/\bshots?\b|\bshoot|\battempts?\b/.test(q)) return "shots.v1";
  if (/\bgoals?\b/.test(q)) return "goals.v1";
  return null;
}

function parseSubjects(q: string, ctx: Pick<MatchContext, "names" | "teams">): string[] {
  const found: string[] = [];
  const add = (id: string) => { if (!found.includes(id)) found.push(id); };
  for (const [id, name] of Object.entries(ctx.names)) {
    if (id in ctx.teams) continue;
    if (new RegExp(`(?<![a-z])${name.toLowerCase()}(?![a-z])`).test(q)) add(id);
  }
  for (const [id, name] of Object.entries(ctx.teams)) {
    const words = [name.toLowerCase(), id];
    if (words.some((w) => new RegExp(`(?<![a-z])${w}(?![a-z])`).test(q))) add(id);
  }
  if (/\bhome (side|team)\b|\bthe hosts\b/.test(q)) add(Object.keys(ctx.teams)[0]);
  if (/\baway (side|team)\b|\bthe visitors\b/.test(q)) add(Object.keys(ctx.teams)[1]);
  return found;
}

/** Read a question into a plan with the built-in rules. Unknown questions return "unknown". */
export function parseQuestion(question: string, ctx: Pick<MatchContext, "names" | "teams">): Plan {
  const q = normalise(question);
  if (!q) return { intent: "unknown" };
  if (/\bwho (will|is going to|'s going to) win\b|\bpredict|\bodds\b|\bbet(ting)?\b|\bnext (match|game|season)\b|\bwill (they|northbridge|riverside) (win|score|lose)\b/.test(q)) {
    return { intent: "out_of_scope", reason: "prediction" };
  }
  if (/\b(arsenal|chelsea|liverpool|man(chester)? (city|united|utd)|tottenham|spurs|newcastle|everton|aston villa|west ham|premier league table|champions league|world cup|last season)\b/.test(q)) {
    return { intent: "out_of_scope", reason: "other_match" };
  }
  if (/\b(salary|wages?|girlfriend|wife|age of|how old|injur)/.test(q)) return { intent: "out_of_scope", reason: "personal" };
  const window = parseWindow(q);
  if (/\bwho scored\b|\bscorers?\b|\bgoal ?scorers?\b|\bwho got the goals?\b|\bwhen (was|were) the goals?\b|\bwhen did .* score\b/.test(q)) {
    return { intent: "scorers", window };
  }
  if (/\b(the |what'?s the |what is the |current )score(line)?\b|\bwho('s| is) (winning|ahead|leading)\b|\bhow many goals\b/.test(q) && !/\bshots?\b/.test(q)) {
    const subjects = parseSubjects(q, ctx);
    if (subjects.some((id) => !(id in ctx.teams)) || subjects.length === 1) return { intent: "metric", metric: "goals.v1", subjects, window };
    return { intent: "score", window };
  }
  const metric = parseMetric(q);
  const subjects = parseSubjects(q, ctx);
  if (metric) return { intent: "metric", metric, subjects, window };
  // A team or player with no statistic named: a short verified summary.
  if (subjects.length === 1 && !HELP.some((t) => t.id !== "what" && t.patterns.some((p) => p.test(q)))) {
    return { intent: "summary", subject: subjects[0], window };
  }
  for (const topic of HELP) if (topic.patterns.some((p) => p.test(q))) return { intent: "help", topic: topic.id };
  return { intent: "unknown" };
}

/* ---------- Validating plans that come from outside (a model) ---------- */

const PLAN_KEYS: Readonly<Record<string, readonly string[]>> = {
  metric: ["intent", "metric", "subjects", "window"],
  score: ["intent", "window"],
  scorers: ["intent", "window"],
  summary: ["intent", "subject", "window"],
  help: ["intent", "topic"],
  out_of_scope: ["intent", "reason"],
  unknown: ["intent"],
};

function isMinute(value: unknown): boolean {
  return value === null || value === undefined || (Number.isInteger(value) && (value as number) >= 0 && (value as number) <= 130);
}

function validWindow(value: unknown): value is PlanWindow {
  if (value === undefined) return true;
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const w = value as Record<string, unknown>;
  if (Object.keys(w).some((k) => !["period", "from_minute", "to_minute", "last_minutes"].includes(k))) return false;
  if (!(w.period === undefined || w.period === null || w.period === 1 || w.period === 2)) return false;
  return isMinute(w.from_minute) && isMinute(w.to_minute) && isMinute(w.last_minutes);
}

/** Accept a plan from an untrusted source only if it has exactly the expected shape. */
export function validatePlan(value: unknown, ctx: Pick<MatchContext, "names" | "teams">): Plan | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const plan = value as Record<string, unknown>;
  const keys = PLAN_KEYS[String(plan.intent)];
  if (!keys || Object.keys(plan).some((k) => !keys.includes(k))) return null;
  switch (plan.intent) {
    case "metric": {
      if (typeof plan.metric !== "string" || !(plan.metric in METRICS)) return null;
      if (!Array.isArray(plan.subjects) || plan.subjects.length > 2) return null;
      if (plan.subjects.some((s) => typeof s !== "string" || !(s in ctx.names || s in ctx.teams))) return null;
      if (!validWindow(plan.window)) return null;
      return { intent: "metric", metric: plan.metric as Metric, subjects: [...plan.subjects] as string[], window: (plan.window ?? {}) as PlanWindow };
    }
    case "score":
    case "scorers":
      return validWindow(plan.window) ? { intent: plan.intent, window: (plan.window ?? {}) as PlanWindow } : null;
    case "summary":
      if (typeof plan.subject !== "string" || !(plan.subject in ctx.names || plan.subject in ctx.teams)) return null;
      return validWindow(plan.window) ? { intent: "summary", subject: plan.subject, window: (plan.window ?? {}) as PlanWindow } : null;
    case "help":
      return typeof plan.topic === "string" && HELP.some((t) => t.id === plan.topic) ? { intent: "help", topic: plan.topic } : null;
    case "out_of_scope":
      return ["prediction", "other_match", "personal", "unsupported"].includes(String(plan.reason))
        ? { intent: "out_of_scope", reason: plan.reason as "prediction" } : null;
    case "unknown":
      return { intent: "unknown" };
    default:
      return null;
  }
}

/* ---------- Answering ---------- */

const MINUTE_MS = 60_000;

function mark(ms: number): string {
  const s = Math.round(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

type Resolved = { window: Window; phrase: string; scope: string } | { error: string };

/** Turn a plan window into the verifier's window, the words used in sentences, and a scope label. */
export function resolveWindow(plan: PlanWindow, replayEndMs: number): Resolved {
  const end = replayEndMs;
  const endMinute = Math.floor(end / MINUTE_MS);
  if (plan.period === 1) return { window: { period: 1, from_ms: 0, to_ms: end }, phrase: "in the first half", scope: "First half" };
  if (plan.period === 2) return { window: { period: 2, from_ms: 0, to_ms: end }, phrase: "in the second half so far", scope: `Second half, to ${mark(end)}` };
  if (plan.last_minutes != null) {
    if (plan.last_minutes < 1) return { error: "Ask about at least the last minute." };
    const from = Math.max(0, end - plan.last_minutes * MINUTE_MS);
    return { window: { from_ms: from, to_ms: end }, phrase: `in the last ${plan.last_minutes} minutes`, scope: `${mark(from)} to ${mark(end)}` };
  }
  const fromMinute = plan.from_minute ?? null;
  const toMinute = plan.to_minute ?? null;
  for (const minute of [fromMinute, toMinute]) {
    if (minute != null && minute * MINUTE_MS > end) {
      return { error: `The replay stops at ${mark(end)}, so I can only answer up to minute ${endMinute}.` };
    }
  }
  const from = (fromMinute ?? 0) * MINUTE_MS;
  const to = toMinute == null ? end : toMinute * MINUTE_MS;
  if (to <= from) return { error: "That window is empty: the start must come before the end." };
  if (fromMinute != null && toMinute != null) return { window: { from_ms: from, to_ms: to }, phrase: `between ${fromMinute}′ and ${toMinute}′`, scope: `${mark(from)} to ${mark(to)}` };
  if (fromMinute != null) return { window: { from_ms: from, to_ms: to }, phrase: `since ${fromMinute}′`, scope: `${mark(from)} to ${mark(to)}` };
  if (toMinute != null) return { window: { from_ms: 0, to_ms: to }, phrase: `before ${toMinute}′`, scope: `Kick-off to ${mark(to)}` };
  return { window: { from_ms: 0, to_ms: end }, phrase: `up to ${mark(end)}`, scope: `Whole match so far, to ${mark(end)}` };
}

function inWindow(e: VEvent, w: Window): boolean {
  return (w.period == null || e.period === w.period) && w.from_ms <= e.match_clock_ms && e.match_clock_ms < w.to_ms;
}

function nameOf(id: string, ctx: MatchContext): string {
  return ctx.names[id] ?? ctx.teams[id] ?? id;
}

function teamOfPlayer(id: string, ctx: MatchContext): string | null {
  const event = ctx.events.find((e) => e.player_id === id);
  return event?.team_id ?? null;
}

function sentence(metric: Metric, subject: string, value: number, phrase: string, ctx: MatchContext): string {
  const name = nameOf(subject, ctx);
  const isPlayer = !(subject in ctx.teams);
  switch (metric) {
    case "goals.v1": return `${name} scored ${value} ${value === 1 ? "goal" : "goals"} ${phrase}.`;
    case "shots.v1": return `${name} ${isPlayer ? "took" : "had"} ${value} ${value === 1 ? "shot" : "shots"} ${phrase}.`;
    case "final_third_entries.v1": return `${name} made ${value} ${value === 1 ? "entry" : "entries"} into the final third ${phrase}.`;
    case "pass_accuracy.v1": return `${name} completed ${roundHalfUp(value * 100, 0)}% of their passes ${phrase}.`;
    case "possession_time.v1": return `${name} had ${roundHalfUp(value * 100, 0)}% possession ${phrase}.`;
    case "synthetic_xg.v1": return `${name}'s synthetic xG was ${roundHalfUp(value, 2)} ${phrase}.`;
  }
}

let claimCounter = 0;
function nextId(): string {
  claimCounter += 1;
  return `ASK-${String(claimCounter).padStart(4, "0")}`;
}

/** Build, then verify, one measured claim about one subject. */
export function measuredLine(metric: Metric, subject: string, resolved: { window: Window; phrase: string }, ctx: MatchContext, evidence: Evidence): CheckedLine {
  const spec = METRICS[metric];
  const isPlayer = !(subject in ctx.teams);
  const sub: Subject = isPlayer ? { player_id: subject } : { team_id: subject };
  const raw = computeMetric(metric, ctx.events, sub, resolved.window);
  const decimals = spec.unit === "count" ? null : 2;
  const value = decimals == null ? raw : Number(roundHalfUp(raw, decimals));
  const counted = metric === "goals.v1" ? "goal" : metric === "shots.v1" || metric === "synthetic_xg.v1" ? "shot" : null;
  const cited = counted == null ? [] : ctx.events
    .filter((e) => e.type === counted && inWindow(e, resolved.window) && (isPlayer ? e.player_id === subject : e.team_id === subject))
    .map((e) => e.event_id);
  const claim: Claim = {
    claim_id: nextId(),
    text: sentence(metric, subject, value, resolved.phrase, ctx),
    kind: "measured_stat",
    assertion: { metric, subject: sub, window: resolved.window, comparator: "eq", value, unit: spec.unit, decimals },
    evidence_event_ids: cited,
  };
  return { claim, result: verifyClaim(claim, evidence, ctx.events, ctx.names) };
}

function comparison(metric: Metric, lines: CheckedLine[], ctx: MatchContext): string | undefined {
  if (lines.length !== 2 || lines.some((l) => l.result.status !== "verified")) return undefined;
  const [a, b] = lines.map((l) => ({ id: (l.claim.assertion?.subject.team_id ?? l.claim.assertion?.subject.player_id) as string, v: l.claim.assertion?.value as number }));
  const label = METRICS[metric].label;
  if (a.v === b.v) return `Level: both have the same ${label}.`;
  const [hi, lo] = a.v > b.v ? [a, b] : [b, a];
  const more = metric === "pass_accuracy.v1" ? "a higher pass accuracy" : metric === "possession_time.v1" ? "more of the ball" : metric === "synthetic_xg.v1" ? "a higher synthetic xG" : `more ${label}`;
  return `${nameOf(hi.id, ctx)} had ${more} than ${nameOf(lo.id, ctx)}.`;
}

const DECLINES: Record<"prediction" | "other_match" | "personal" | "unsupported", string> = {
  prediction: "I don't predict results. I only state what the recorded events show, and I check every figure before I show it.",
  other_match: "I only know this synthetic match, Northbridge FC v Riverside United. I have no data on real clubs or other games.",
  personal: "I only answer about what happened on the pitch in this match, not about people's private lives.",
  unsupported: "I can't check that against the event log, so I won't guess.",
};

export const UNKNOWN_TEXT = "I couldn't read that question. Try asking about the score, scorers, shots, possession, pass accuracy, xG or final-third entries, for a team, a player or part of the game, or ask how the app works.";

/** Answer a plan. Match plans need the event log; help and declines do not. */
export function answerPlan(plan: Plan, ctx: MatchContext | null): Answer {
  if (plan.intent === "help") {
    const topic = HELP.find((t) => t.id === plan.topic);
    return topic ? { kind: "help", text: topic.text, link: topic.link } : { kind: "unknown", text: UNKNOWN_TEXT };
  }
  if (plan.intent === "out_of_scope") return { kind: "decline", text: DECLINES[plan.reason] };
  if (plan.intent === "unknown") return { kind: "unknown", text: UNKNOWN_TEXT };
  if (!ctx) return { kind: "unknown", text: "The match data is still loading. Try again in a moment." };
  const resolved = resolveWindow(plan.window, ctx.replayEndMs);
  if ("error" in resolved) return { kind: "decline", text: resolved.error };
  const evidence: Evidence = {
    match_id: ctx.matchId,
    event_ids: ctx.events.filter((e) => e.match_clock_ms < ctx.replayEndMs).map((e) => e.event_id),
    window: { from_ms: 0, to_ms: ctx.replayEndMs },
  };
  const teams = Object.keys(ctx.teams);
  if (plan.intent === "score") {
    const lines = teams.map((t) => measuredLine("goals.v1", t, resolved, ctx, evidence));
    const verified = lines.every((l) => l.result.status === "verified");
    const [h, a] = lines.map((l) => l.claim.assertion?.value as number);
    const derived = !verified ? undefined
      : h === a ? `It's level, ${h}–${a}.`
      : `${nameOf(h > a ? teams[0] : teams[1], ctx)} lead ${Math.max(h, a)}–${Math.min(h, a)}.`;
    return { kind: "match", scope: resolved.scope, lines, derived };
  }
  if (plan.intent === "scorers") {
    const goals = ctx.events.filter((e) => e.type === "goal" && inWindow(e, resolved.window));
    if (!goals.length) {
      const lines = teams.map((t) => measuredLine("goals.v1", t, resolved, ctx, evidence));
      return { kind: "match", scope: resolved.scope, lines, note: "No goals in that part of the match." };
    }
    const lines = goals.map((goal) => {
      const scorer = goal.player_id as string;
      const claim: Claim = {
        claim_id: nextId(),
        text: `${nameOf(scorer, ctx)} scored for ${nameOf(goal.team_id as string, ctx)} at ${mark(goal.match_clock_ms)}.`,
        kind: "event_fact",
        fact: { query: "goal_scorer.v1", event_id: goal.event_id, player_id: scorer },
        evidence_event_ids: [goal.event_id],
      };
      return { claim, result: verifyClaim(claim, evidence, ctx.events, ctx.names) };
    });
    return { kind: "match", scope: resolved.scope, lines };
  }
  if (plan.intent === "summary") {
    const isTeam = plan.subject in ctx.teams;
    const metrics: Metric[] = isTeam
      ? ["goals.v1", "shots.v1", "possession_time.v1", "pass_accuracy.v1"]
      : ["goals.v1", "shots.v1", "pass_accuracy.v1", "final_third_entries.v1"];
    return { kind: "match", scope: resolved.scope, lines: metrics.map((m) => measuredLine(m, plan.subject, resolved, ctx, evidence)) };
  }
  // A measured stat for one or two subjects; none named means both teams.
  let subjects = plan.subjects.length ? plan.subjects : teams;
  if (plan.metric === "possession_time.v1") {
    const players = subjects.filter((s) => !(s in ctx.teams));
    if (players.length) {
      const team = teamOfPlayer(players[0], ctx);
      return { kind: "decline", text: `Possession is measured for teams, not players. Try “${team ? nameOf(team, ctx) : "Northbridge"}'s possession”.` };
    }
  }
  subjects = subjects.slice(0, 2);
  const lines = subjects.map((s) => measuredLine(plan.metric, s, resolved, ctx, evidence));
  const note = plan.metric === "synthetic_xg.v1" ? "Synthetic xG is this demo's own chance-quality model, not a licensed xG feed." : undefined;
  return { kind: "match", scope: resolved.scope, lines, derived: comparison(plan.metric, lines, ctx), note };
}

/** Read and answer a question with the built-in rules. */
export function ask(question: string, ctx: MatchContext | null, names: Pick<MatchContext, "names" | "teams">): { plan: Plan; answer: Answer } {
  const plan = parseQuestion(question, names);
  return { plan, answer: answerPlan(plan, ctx) };
}
