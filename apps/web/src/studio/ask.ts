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

/** Why a question is declined. ``detail`` is only ever written by the built-in parser, never taken from a model. */
export type DeclineReason = "prediction" | "other_match" | "personal" | "unsupported";

/** A window in whole match minutes; missing bounds mean kick-off and the replay point. */
export type PlanWindow = { period?: 1 | 2 | null; from_minute?: number | null; to_minute?: number | null; last_minutes?: number | null };

/** What a question asks for. Built by the parser or by a model; always validated. */
export type Plan =
  | { intent: "metric"; metric: Metric; subjects: string[]; window: PlanWindow }
  | { intent: "score"; window: PlanWindow }
  | { intent: "scorers"; subjects: string[]; window: PlanWindow }
  | { intent: "summary"; subject: string; window: PlanWindow }
  | { intent: "help"; topic: string }
  | { intent: "out_of_scope"; reason: DeclineReason; detail?: string }
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
  { id: "metrics", patterns: [/what (is|are|does) (xg|synthetic xg|expected goals|possession|pass accuracy|final[- ]third entr(y|ies))\b/, /how (is|are|do you) .*(calculated|measured|computed|worked out)/, /what (metrics|statistics|stats) (can|do)/, /\bmetrics?\b/],
    text: "I can check six registered metrics: goals, shots, pass accuracy (completed passes over all passes), synthetic xG (this demo's own chance-quality model), final-third entries (completed passes, carries or dribbles into the final third) and possession (time on the ball between events, for teams only). Each is recalculated from the event log every time.",
    link: { href: "/match/nbr-riv/evidence/CL-0214", label: "See a metric being recalculated" } },
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
const ORD = "(?:st|nd|rd|th)?";
const UNIT = "(?:'|\\s*(?:min(?:ute)?s?|mins?))?";
const HALF_1 = /\b(first|1st|opening)[- ]half\b|\bbefore (half[- ]?time|the break|the interval)\b|\b(at|by) (half[- ]?time|the break|the interval)\b|\bhalf[- ]?time (score|result|lead)\b/;
const HALF_2 = /\b(second|2nd)[- ]half\b|\b(after|since) (half[- ]?time|the break|the interval)\b/;

/** One window reading, or a reason the time words could not be used exactly. */
type WindowReading = { window: PlanWindow } | { unclear: string };

/** Read the time window. Every time phrase must be fully used; anything else is declined, not ignored. */
export function parseWindow(q: string, mode: "range" | "score" = "range"): WindowReading {
  const found: PlanWindow[] = [];
  if (HALF_1.test(q)) found.push({ period: 1 });
  if (HALF_2.test(q)) found.push({ period: 2 });
  let m = new RegExp(`\\b(?:last|final) ${MIN}${UNIT}`).exec(q);
  if (m) found.push({ last_minutes: minuteValue(m[1]) });
  m = new RegExp(`\\bbetween (?:the )?${MIN}${ORD}${UNIT} and (?:the )?${MIN}${ORD}${UNIT}`).exec(q);
  if (m) found.push({ from_minute: minuteValue(m[1]), to_minute: minuteValue(m[2]) });
  else {
    // For a score, "after 40 minutes" means the score at that point, not goals since then.
    m = new RegExp(`\\b(?:after|since|from) (?:the )?${MIN}${ORD}${UNIT}`).exec(q);
    if (m) found.push(mode === "score" && !/\bsince\b|\bfrom\b/.test(m[0]) ? { to_minute: minuteValue(m[1]) } : { from_minute: minuteValue(m[1]) });
    m = new RegExp(`\\b(?:before|by|until|up to|at) (?:the )?${MIN}${ORD}${UNIT}`).exec(q);
    if (m) found.push({ to_minute: minuteValue(m[1]) });
  }
  m = new RegExp(`\\b(?:first|opening) ${MIN}${UNIT}`).exec(q);
  if (m && !/\bfirst half\b/.test(q)) found.push({ to_minute: minuteValue(m[1]) });
  m = new RegExp(`\\bin the ${MIN}(?:st|nd|rd|th)(?: minute)?\\b(?![- ]half)`).exec(q);
  if (m) {
    const minute = minuteValue(m[1]);
    if (minute != null && minute >= 1) found.push({ from_minute: minute - 1, to_minute: minute });
  }
  if (found.length > 1) return { unclear: "I can read one time window at a time: a half, a minute range or the last few minutes, but not a mix of them." };
  if (found.length === 1) return { window: found[0] };
  const timeWords = /\b(minutes?|mins?|half|halves|period|interval|stoppage|added time|injury time|extra time|kick[- ]?off|full[- ]time|o'clock)\b|\b[0-9]{1,3}'/;
  if (timeWords.test(q) && !/\b(so far|whole match|whole game|overall|in total|full[- ]time)\b/.test(q)) {
    return { unclear: "I couldn't read that time window exactly. Try “first half”, “second half”, “after 60 minutes”, “between 30 and 45 minutes” or “the last 15 minutes”." };
  }
  return { window: {} };
}

// Statistics and qualifiers the registered metrics do not cover. Answering them with a
// nearby metric would be a different question with a Verified chip, so they are declined.
const UNSUPPORTED_STATS: readonly [RegExp, string][] = [
  [/\bon target\b|\boff target\b|\bsaves?\b|\bsaved\b|\bblocked\b|\bbig chances?\b/, "shots by outcome"],
  [/\bconcede[ds]?\b|\bconceding\b|\bagainst them\b|\bown goals?\b/, "goals or shots conceded"],
  [/\bassists?\b|\bassisted\b/, "assists"],
  [/\bcorners?\b/, "corners"],
  [/\b(yellow|red) cards?\b|\bcards?\b|\bbookings?\b|\bbooked\b|\bsent off\b/, "cards"],
  [/\bfouls?\b|\bfouled\b|\boffsides?\b|\bfree[- ]kicks?\b|\bpenalt(y|ies)\b/, "fouls and set pieces"],
  [/\btackles?\b|\binterceptions?\b|\bclearances?\b|\bduels?\b|\bdribbles?\b|\bcrosses\b/, "defensive or duel actions"],
  [/\bhow many passes\b|\bnumber of passes\b|\bpasses (made|played|attempted)\b|\btouches\b|\bdistance\b|\bsprints?\b|\bheat ?map\b/, "pass counts, touches or tracking data"],
];

const PLAYER_QUESTION = /\bwhich player\b|\bwho (had|took|made|has) the most\b|\bmost (shots|goals|passes)\b|\btop scorer\b|\bbest player\b|\bman of the match\b|\bplayer of the match\b/;
const KNOWN_WORDS = new Set([
  "who", "what", "which", "when", "how", "did", "does", "do", "is", "are", "was", "were", "the", "a", "an", "and", "or", "in", "on",
  "at", "of", "for", "to", "by", "after", "before", "since", "between", "from", "until", "up", "their", "they", "them", "it",
  "team", "teams", "side", "sides", "home", "away", "both", "each", "player", "players", "match", "game", "half", "score", "scored",
  "take", "took", "have", "had", "has", "make", "made", "get", "got", "much", "many", "more", "most", "his", "her", "show", "me",
  "tell", "about", "xg", "matchdesk", "ask", "eligible", "verified", "can", "you", "i", "please", "s",
]);

function parseSubjects(q: string, ctx: Pick<MatchContext, "names" | "teams">): string[] {
  const found: string[] = [];
  const add = (id: string) => { if (!found.includes(id)) found.push(id); };
  for (const [id, name] of Object.entries(ctx.names)) {
    if (Object.hasOwn(ctx.teams, id)) continue;
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

/** A name the question uses for a person who is not in this match, if any. */
function unknownPerson(original: string, q: string, ctx: Pick<MatchContext, "names" | "teams">): string | null {
  const known = new Set([...Object.values(ctx.names), ...Object.values(ctx.teams)].map((n) => n.toLowerCase()));
  const did = /\b(?:did|does|has|had|was|is) ([a-z][a-z'-]+) (?:take|score|have|make|get|play|do|shoot|pass)\b/.exec(q);
  if (did && !KNOWN_WORDS.has(did[1]) && !known.has(did[1]) && !known.has(did[1].replace(/'s$/, ""))) {
    const asTyped = original.split(/[^A-Za-zÀ-ÿ'-]+/).find((w) => w.toLowerCase() === did[1]);
    return asTyped ?? did[1];
  }
  const words = original.split(/[^A-Za-zÀ-ÿ'-]+/).filter(Boolean);
  for (const [i, word] of words.entries()) {
    const bare = word.replace(/'s$/i, "");
    if (i === 0 || !/^[A-ZÀ-Þ][a-zà-ÿ'-]+$/.test(bare)) continue;
    const lower = bare.toLowerCase();
    if (!known.has(lower) && !KNOWN_WORDS.has(lower) && !["Northbridge", "Riverside", "FC", "United", "Eligible", "Verified", "Foundry", "Azure"].includes(bare)) return bare;
  }
  return null;
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

const decline = (reason: DeclineReason, detail?: string): Plan => ({ intent: "out_of_scope", reason, detail });

/** Read a question into a plan with the built-in rules. Unknown questions return "unknown". */
export function parseQuestion(question: string, ctx: Pick<MatchContext, "names" | "teams">): Plan {
  const q = normalise(question);
  if (!q) return { intent: "unknown" };
  if (/\bwho (will|is going to|'s going to) win\b|\bpredict|\bodds\b|\bbet(ting)?\b|\bnext (match|game|season)\b|\bwill (they|northbridge|riverside) (win|score|lose)\b/.test(q)) {
    return decline("prediction");
  }
  if (/\b(arsenal|chelsea|liverpool|man(chester)? (city|united|utd)|tottenham|spurs|newcastle|everton|aston villa|west ham|premier league table|champions league|world cup|last season)\b/.test(q)) {
    return decline("other_match");
  }
  if (/\b(salary|wages?|girlfriend|wife|age of|how old|injur)/.test(q)) return decline("personal");
  // Explanations come before figures: "what is xG?" asks what it is, not what it was.
  for (const topic of HELP) {
    if (topic.id === "metrics" && topic.patterns.slice(0, 3).some((p) => p.test(q))) return { intent: "help", topic: "metrics" };
  }
  for (const [pattern, label] of UNSUPPORTED_STATS) {
    if (pattern.test(q)) return decline("unsupported", `I can't check ${label}: it isn't one of the registered metrics, so I won't estimate it. I can check goals, shots, pass accuracy, synthetic xG, final-third entries and possession.`);
  }
  const subjects = parseSubjects(q, ctx);
  const stranger = unknownPerson(question, q, ctx);
  const named = Object.entries(ctx.names).filter(([id]) => !Object.hasOwn(ctx.teams, id)).map(([, n]) => n).join(", ");
  if (stranger) return decline("unsupported", `There's no player called ${stranger} with a name in this match. The named players are ${named}.`);
  if (PLAYER_QUESTION.test(q) && !subjects.some((s) => !Object.hasOwn(ctx.teams, s))) {
    return decline("unsupported", `I don't rank players, because only some players have names in this demo. Ask about a team or a named player: ${named}.`);
  }
  if (subjects.length > 2) return decline("unsupported", "Ask about one or two teams or players at a time.");
  const isScorers = /\bwho scored\b|\bscorers?\b|\bgoal ?scorers?\b|\bwho got the goals?\b|\bwhen (was|were) the goals?\b|\bwhen did .* score\b|\bdid .* score\b/.test(q);
  const isScore = !isScorers && /\bscore(line)?\b|\bwho('s| is| was) (winning|ahead|leading|in front)\b/.test(q) && !/\bshots?\b/.test(q);
  const reading = parseWindow(q, isScore ? "score" : "range");
  if ("unclear" in reading) return decline("unsupported", reading.unclear);
  const window = reading.window;
  if (isScorers) return { intent: "scorers", subjects, window };
  if (isScore) {
    if (subjects.length) return { intent: "metric", metric: "goals.v1", subjects, window };
    return { intent: "score", window };
  }
  const metric = parseMetric(q);
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
  scorers: ["intent", "subjects", "window"],
  summary: ["intent", "subject", "window"],
  help: ["intent", "topic"],
  out_of_scope: ["intent", "reason"],
  unknown: ["intent"],
};

function isMinute(value: unknown): boolean {
  return value === null || value === undefined || (Number.isInteger(value) && (value as number) >= 0 && (value as number) <= 130);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
}

/** Exactly one kind of window: a half, a minute range or the last N minutes. */
function validWindow(value: unknown): value is PlanWindow {
  if (value === undefined) return true;
  if (!isPlainObject(value)) return false;
  if (Object.keys(value).some((k) => !["period", "from_minute", "to_minute", "last_minutes"].includes(k))) return false;
  const has = (k: string) => value[k] !== undefined && value[k] !== null;
  if (!(!has("period") || value.period === 1 || value.period === 2)) return false;
  const kinds = [has("period"), has("from_minute") || has("to_minute"), has("last_minutes")].filter(Boolean).length;
  if (kinds > 1) return false;
  if (has("last_minutes") && (value.last_minutes as number) < 1) return false;
  return isMinute(value.from_minute) && isMinute(value.to_minute) && isMinute(value.last_minutes);
}

function knownSubject(s: unknown, ctx: Pick<MatchContext, "names" | "teams">): s is string {
  return typeof s === "string" && (Object.hasOwn(ctx.names, s) || Object.hasOwn(ctx.teams, s));
}

function validSubjects(value: unknown, ctx: Pick<MatchContext, "names" | "teams">): value is string[] {
  return Array.isArray(value) && value.length <= 2 && new Set(value).size === value.length && value.every((s) => knownSubject(s, ctx));
}

/** Accept a plan from an untrusted source only if it has exactly the expected shape. */
export function validatePlan(value: unknown, ctx: Pick<MatchContext, "names" | "teams">): Plan | null {
  if (!isPlainObject(value) || typeof value.intent !== "string" || !Object.hasOwn(PLAN_KEYS, value.intent)) return null;
  const plan = value;
  const keys = PLAN_KEYS[plan.intent as string];
  if (Object.keys(plan).some((k) => !keys.includes(k))) return null;
  const window = () => ({ ...((plan.window ?? {}) as PlanWindow) });
  switch (plan.intent) {
    case "metric":
      if (typeof plan.metric !== "string" || !Object.hasOwn(METRICS, plan.metric)) return null;
      if (!validSubjects(plan.subjects, ctx) || !validWindow(plan.window)) return null;
      return { intent: "metric", metric: plan.metric as Metric, subjects: [...plan.subjects], window: window() };
    case "score":
      return validWindow(plan.window) ? { intent: "score", window: window() } : null;
    case "scorers": {
      const subjects = plan.subjects ?? [];
      return validSubjects(subjects, ctx) && validWindow(plan.window) ? { intent: "scorers", subjects: [...subjects], window: window() } : null;
    }
    case "summary":
      return knownSubject(plan.subject, ctx) && validWindow(plan.window) ? { intent: "summary", subject: plan.subject, window: window() } : null;
    case "help":
      return typeof plan.topic === "string" && HELP.some((t) => t.id === plan.topic) ? { intent: "help", topic: plan.topic } : null;
    case "out_of_scope":
      return ["prediction", "other_match", "personal", "unsupported"].includes(String(plan.reason)) ? decline(plan.reason as DeclineReason) : null;
    case "unknown":
      return { intent: "unknown" };
    default:
      return null;
  }
}

/** A short description of what a plan asks, so a reader can see how the question was read. */
export function describePlan(plan: Plan, ctx: Pick<MatchContext, "names" | "teams">): string {
  const name = (id: string) => ctx.names[id] ?? ctx.teams[id] ?? id;
  const w = (window: PlanWindow) => window.period ? (window.period === 1 ? "first half" : "second half")
    : window.last_minutes ? `last ${window.last_minutes} minutes`
    : window.from_minute != null || window.to_minute != null ? `minutes ${window.from_minute ?? 0}–${window.to_minute ?? "now"}` : "whole match";
  switch (plan.intent) {
    case "metric": return `${METRICS[plan.metric].label} · ${plan.subjects.length ? plan.subjects.map(name).join(" and ") : "both teams"} · ${w(plan.window)}`;
    case "score": return `score · ${w(plan.window)}`;
    case "scorers": return `scorers · ${plan.subjects.length ? plan.subjects.map(name).join(" and ") : "both teams"} · ${w(plan.window)}`;
    case "summary": return `summary · ${name(plan.subject)} · ${w(plan.window)}`;
    case "help": return `help · ${plan.topic}`;
    case "out_of_scope": return "outside what I can check";
    case "unknown": return "not understood";
  }
}

/* ---------- Answering ---------- */

const MINUTE_MS = 60_000;

function mark(ms: number): string {
  const s = Math.round(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

type Resolved = { window: Window; phrase: string; scope: string; fromKickOff: boolean; clamped?: string } | { error: string };

/** Turn a plan window into the verifier's window, the words used in sentences, and a scope label. */
export function resolveWindow(plan: PlanWindow, replayEndMs: number): Resolved {
  const end = replayEndMs;
  const endMinute = Math.floor(end / MINUTE_MS);
  if (plan.period === 1) return { window: { period: 1, from_ms: 0, to_ms: end }, phrase: "in the first half", scope: "First half", fromKickOff: true };
  if (plan.period === 2) return { window: { period: 2, from_ms: 0, to_ms: end }, phrase: "in the second half so far", scope: `Second half, to ${mark(end)}`, fromKickOff: false };
  if (plan.last_minutes != null) {
    if (plan.last_minutes < 1) return { error: "Ask about at least the last minute." };
    const minutes = Math.min(plan.last_minutes, endMinute);
    const from = end - minutes * MINUTE_MS;
    const clamped = minutes < plan.last_minutes ? `The replay is only ${mark(end)} long, so this covers the last ${minutes} minutes.` : undefined;
    return { window: { from_ms: from, to_ms: end }, phrase: `in the last ${minutes} minutes`, scope: `${mark(from)} to ${mark(end)}`, fromKickOff: false, clamped };
  }
  const fromMinute = plan.from_minute ?? null;
  let toMinute = plan.to_minute ?? null;
  if (fromMinute != null && fromMinute * MINUTE_MS >= end) {
    return { error: `The replay stops at ${mark(end)}, so I can only answer up to minute ${endMinute}.` };
  }
  let clamped: string | undefined;
  if (toMinute != null && toMinute * MINUTE_MS > end) {
    clamped = `The replay stops at ${mark(end)}, so this covers the match up to then.`;
    toMinute = null;
  }
  const from = (fromMinute ?? 0) * MINUTE_MS;
  const to = toMinute == null ? end : toMinute * MINUTE_MS;
  if (to <= from) return { error: "That window is empty: the start must come before the end." };
  if (fromMinute != null && toMinute != null) return { window: { from_ms: from, to_ms: to }, phrase: `between ${fromMinute}′ and ${toMinute}′`, scope: `${mark(from)} to ${mark(to)}`, fromKickOff: fromMinute === 0, clamped };
  if (fromMinute != null) return { window: { from_ms: from, to_ms: to }, phrase: `since ${fromMinute}′`, scope: `${mark(from)} to ${mark(to)}`, fromKickOff: fromMinute === 0, clamped };
  if (toMinute != null) return { window: { from_ms: 0, to_ms: to }, phrase: `before ${toMinute}′`, scope: `Kick-off to ${mark(to)}`, fromKickOff: true, clamped };
  return { window: { from_ms: 0, to_ms: end }, phrase: `up to ${mark(end)}`, scope: `Whole match so far, to ${mark(end)}`, fromKickOff: true, clamped };
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
  const isPlayer = !Object.hasOwn(ctx.teams, subject);
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
  const isPlayer = !Object.hasOwn(ctx.teams, subject);
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

/** A ratio has no meaning without its denominator: say so instead of verifying "0%". */
function emptyRatio(metric: Metric, subject: string, window: Window, ctx: MatchContext): string | null {
  if (metric !== "pass_accuracy.v1") return null;
  const isPlayer = !Object.hasOwn(ctx.teams, subject);
  const passes = ctx.events.some((e) => e.type === "pass" && inWindow(e, window) && (isPlayer ? e.player_id === subject : e.team_id === subject));
  return passes ? null : `${nameOf(subject, ctx)}: no passes recorded in this window, so there is no pass accuracy to check.`;
}

function comparison(metric: Metric, lines: CheckedLine[], ctx: MatchContext): string | undefined {
  if (lines.length !== 2 || lines.some((l) => l.result.status !== "verified" || l.result.observed == null)) return undefined;
  const [a, b] = lines.map((l) => ({ id: (l.claim.assertion?.subject.team_id ?? l.claim.assertion?.subject.player_id) as string, raw: l.result.observed as number, shown: l.claim.assertion?.value as number }));
  if (a.id === b.id) return undefined;
  const label = METRICS[metric].label;
  if (a.raw === b.raw) return METRICS[metric].unit === "count" ? `Level: the same number of ${label} each.` : `Level: the same ${label}.`;
  const [hi, lo] = a.raw > b.raw ? [a, b] : [b, a];
  if (hi.shown === lo.shown) return `Almost level: ${nameOf(hi.id, ctx)} are very slightly ahead on ${label} before rounding.`;
  const more = metric === "pass_accuracy.v1" ? "a higher pass accuracy" : metric === "possession_time.v1" ? "more of the ball" : metric === "synthetic_xg.v1" ? "a higher synthetic xG" : `more ${label}`;
  return `${nameOf(hi.id, ctx)} had ${more} than ${nameOf(lo.id, ctx)}.`;
}

const DECLINES: Record<DeclineReason, string> = {
  prediction: "I don't predict results. I only state what the recorded events show, and I check every figure before I show it.",
  other_match: "I only know this synthetic match, Northbridge FC v Riverside United. I have no data on real clubs or other games.",
  personal: "I only answer about what happened on the pitch in this match, not about people's private lives.",
  unsupported: "I can't check that against the event log, so I won't guess.",
};

export const UNKNOWN_TEXT = "I couldn't read that question. Try asking about the score, scorers, shots, possession, pass accuracy, xG or final-third entries, for a team, a player or part of the game, or ask how the app works.";

/** Whether answering a plan needs the event log. */
export function needsEvents(plan: Plan): boolean {
  return plan.intent === "metric" || plan.intent === "score" || plan.intent === "scorers" || plan.intent === "summary";
}

/** Answer a plan. Match plans need the event log; help and declines do not. */
export function answerPlan(plan: Plan, ctx: MatchContext | null): Answer {
  if (plan.intent === "help") {
    const topic = HELP.find((t) => t.id === plan.topic);
    return topic ? { kind: "help", text: topic.text, link: topic.link } : { kind: "unknown", text: UNKNOWN_TEXT };
  }
  if (plan.intent === "out_of_scope") return { kind: "decline", text: plan.detail ?? DECLINES[plan.reason] };
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
  const notes = (...extra: (string | undefined | null)[]) => [resolved.clamped, ...extra].filter(Boolean).join(" ") || undefined;
  if (plan.intent === "score") {
    const lines = teams.map((t) => measuredLine("goals.v1", t, resolved, ctx, evidence));
    const verified = lines.every((l) => l.result.status === "verified");
    const [h, a] = lines.map((l) => l.claim.assertion?.value as number);
    // A lead or a draw only makes sense for a window that starts at kick-off.
    const derived = !verified ? undefined
      : !resolved.fromKickOff ? `Goals in this window only: ${nameOf(teams[0], ctx)} ${h}, ${nameOf(teams[1], ctx)} ${a}. This is not the score.`
      : h === a ? `It's level, ${h}–${a}.`
      : `${nameOf(h > a ? teams[0] : teams[1], ctx)} ${resolved.window.to_ms < ctx.replayEndMs || resolved.window.period === 1 ? "led" : "lead"} ${Math.max(h, a)}–${Math.min(h, a)}.`;
    return { kind: "match", scope: resolved.scope, lines, derived, note: notes() };
  }
  if (plan.intent === "scorers") {
    const goals = ctx.events.filter((e) => e.type === "goal" && inWindow(e, resolved.window)
      && (!plan.subjects.length || plan.subjects.includes(e.player_id as string) || plan.subjects.includes(e.team_id as string)));
    if (!goals.length) {
      const who = plan.subjects.length ? plan.subjects : teams;
      const lines = who.map((t) => measuredLine("goals.v1", t, resolved, ctx, evidence));
      return { kind: "match", scope: resolved.scope, lines, note: notes("No goals in that part of the match.") };
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
    return { kind: "match", scope: resolved.scope, lines, note: notes() };
  }
  if (plan.intent === "summary") {
    const isTeam = Object.hasOwn(ctx.teams, plan.subject);
    if (!isTeam && !ctx.events.some((e) => e.player_id === plan.subject && inWindow(e, resolved.window))) {
      return { kind: "decline", text: `${nameOf(plan.subject, ctx)} has no recorded events in that part of the match, so there is nothing to check.` };
    }
    const metrics: Metric[] = isTeam
      ? ["goals.v1", "shots.v1", "possession_time.v1", "pass_accuracy.v1"]
      : ["goals.v1", "shots.v1", "pass_accuracy.v1", "final_third_entries.v1"];
    const empty: string[] = [];
    const lines = metrics.flatMap((m) => {
      const missing = emptyRatio(m, plan.subject, resolved.window, ctx);
      if (missing) { empty.push(missing); return []; }
      return [measuredLine(m, plan.subject, resolved, ctx, evidence)];
    });
    return { kind: "match", scope: resolved.scope, lines, note: notes(...empty) };
  }
  // A measured stat for one or two subjects; none named means both teams.
  const subjects = plan.subjects.length ? [...new Set(plan.subjects)] : teams;
  if (subjects.length > 2) return { kind: "decline", text: "Ask about one or two teams or players at a time." };
  if (plan.metric === "possession_time.v1") {
    const players = subjects.filter((s) => !Object.hasOwn(ctx.teams, s));
    if (players.length) {
      const team = teamOfPlayer(players[0], ctx);
      return { kind: "decline", text: `Possession is measured for teams, not players. Try “${team ? nameOf(team, ctx) : "Northbridge"}'s possession”.` };
    }
  }
  const empty: string[] = [];
  const lines = subjects.flatMap((s) => {
    const missing = emptyRatio(plan.metric, s, resolved.window, ctx);
    if (missing) { empty.push(missing); return []; }
    return [measuredLine(plan.metric, s, resolved, ctx, evidence)];
  });
  if (!lines.length) return { kind: "decline", text: empty.join(" ") };
  const xg = plan.metric === "synthetic_xg.v1" ? "Synthetic xG is this demo's own chance-quality model, not a licensed xG feed." : undefined;
  return { kind: "match", scope: resolved.scope, lines, derived: comparison(plan.metric, lines, ctx), note: notes(...empty, xg) };
}

/** Read and answer a question with the built-in rules. */
export function ask(question: string, ctx: MatchContext | null, names: Pick<MatchContext, "names" | "teams">): { plan: Plan; answer: Answer } {
  const plan = parseQuestion(question, names);
  return { plan, answer: answerPlan(plan, ctx) };
}
