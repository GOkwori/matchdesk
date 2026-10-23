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
  "pass_distance.v1": { unit: "metres", label: "average pass length" },
  "progressive_passes.v1": { unit: "count", label: "progressive passes" },
  "pass_difficulty.v1": { unit: "rating", label: "pass difficulty" },
  "ball_speed.v1": { unit: "km_per_hour", label: "estimated ball speed" },
  "pressured_passes.v1": { unit: "count", label: "passes under pressure" },
  "tackles.v1": { unit: "count", label: "tackles" },
  "interceptions.v1": { unit: "count", label: "interceptions" },
  "recoveries.v1": { unit: "count", label: "ball recoveries" },
  "shot_speed.v1": { unit: "km_per_hour", label: "shot speed" },
  "top_speed.v1": { unit: "km_per_hour", label: "top speed" },
  "distance_covered.v1": { unit: "kilometres", label: "distance covered" },
  "sprints.v1": { unit: "count", label: "sprints" },
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
  | { intent: "scorers"; subjects: string[]; window: PlanWindow; nth?: number }
  | { intent: "leaders"; metric: Metric; subjects: string[]; window: PlanWindow }
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
    text: "Only a human producer can approve a draft, and only after it is eligible. In this demo you approve as a demo producer on the publication page: the approval binds the exact version, any edit withdraws it, and publishing goes only to a demo channel in your browser.",
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
    text: "I check eighteen metrics, recalculated from the log every time. Attack: goals, shots, synthetic xG, final-third entries. Passing: accuracy, length, progressive passes, a 0\u2013100 difficulty rating, passes under pressure, estimated ball speed. Defending: tackles, interceptions, recoveries. Possession, for teams. Synthetic tracking: shot speed, top speed, distance covered, sprints.",
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
  if (timeWords.test(q) && !/\b(so far|whole match|whole game|overall|in total|full[- ]time|(since|from) kick[- ]?off)\b/.test(q)) {
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
  [/\bclearances?\b|\bduels?\b|\bdribbles?\b|\bcrosses\b|\bblocks\b/, "clearances, duels, dribbles or crosses"],
  [/\bhow many passes\b|\bnumber of passes\b|\bpasses (made|attempted)\b|\btouches\b|\bheat ?map\b|\bpace of\b|\bacceleration\b|\bpositions?\b|\bformations?\b/, "pass counts, touches, heat maps or positional tracking"],
  // Shot speed is a mean over a window; the speed of one shot is on its overlay, not answered here.
  [/\b(fastest|hardest|quickest) (shot|strike)\b|\bshot power\b|\bhow fast (was|is) (the|that|his|her) (shot|strike|header|goal)\b|\bshot speed of (the|that) (goal|shot|header|strike)\b|\bspeed of the (goal|header|strike)\b/, "the speed of a single shot (each scoring shot's speed is on its overlay in the replay)"],
];

// Qualifiers no registered metric or event field records. Answering without them would
// answer a broader question, so each one is declined and named.
const QUALIFIERS: readonly [RegExp, string][] = [
  [/\bheaders?\b|\bheaded\b|\bwith (his|her|their) head\b|\b(left|right|weaker|stronger|preferred) foot(ed)?\b|\bwith (his|her|their) (left|right)\b|\bvolley(s|ed)?\b|\btap[- ]?ins?\b/,
    "I can't check how a goal or shot was struck (header, foot or volley): the registered metrics count every goal and shot the same way."],
  [/\b(inside|outside|in|from outside|from inside) the (box|area|penalty area|(six|18)[- ]yard box)\b|\bfrom (distance|range|long range|close range)\b|\b(long|close)[- ]range\b/,
    "I can't split goals or shots by distance or by the box: the registered metrics count them all."],
  [/\bcounter[- ]?attacks?\b|\bon the (counter|break)\b|\bset[- ]pieces?\b|\bthrow[- ]ins?\b|\bopen play\b/,
    "I can't split statistics by phase of play (counter-attacks, set pieces or open play)."],
  [/\bseasons?\b|\bcareer\b|\bthis year\b|\bleague\b|\ball[- ]time\b|\b(previous|last|other) (match|game)(es|s)?\b/,
    "I only have this one match's events, so I can't check anything about a season or other games."],
  [/\b(when|while) (losing|winning|behind|ahead|level|drawing|trailing|leading|up|down|in front)\b|\b(going|being|went|were|was) (behind|ahead|in front)\b|\bgoing ([0-9]|one|two)[- –]([0-9]|nil) (up|down)\b|\bat ([0-9])[-–]([0-9])\b/,
    "I can't split statistics by the score at the time. Ask with minutes instead, such as “shots after 60 minutes”; “Who scored?” gives each goal's time."],
  [/\b(before|after|since|until|following) (the |their |his |her |a |an )?(northbridge |riverside |okafor's |lindqvist's )?((first|second|third|opening|1st|2nd|3rd|last) )?(goal|equali[sz]er|opener|winner|red card|card|substitution|sub|corner|save)\b|\b(before|after|since) (conceding|scoring)\b/,
    "I can't anchor a window to a match event. Ask with minutes instead, such as “shots after 60 minutes”; “Who scored?” gives each goal's time."],
  [/\bequali[sz](er|ing goal)\b|\bwinn(er|ing goal)\b|\bconsolation\b/,
    "I don't label goals as equalisers or winners. “Who scored?” lists every goal in order with its time, and every line is checked."],
];

const ORDINALS: Readonly<Record<string, number>> = { opened: 1, first: 1, "1st": 1, opening: 1, opener: 1, second: 2, "2nd": 2, third: 3, "3rd": 3, fourth: 4, "4th": 4 };
const ORDINAL_GOAL = /\b(first|1st|opening|second|2nd|third|3rd|fourth|4th) goal\b|\bthe (opener)\b|\bscored (first)\b|\b(first) to score\b|\b(opened) the scoring\b/;
// A record id such as nbr-09: only a named player's id may stand in for their name.
const RECORD_ID = /(?<![a-z0-9-])([a-z]{2,5}-[0-9]{1,3})(?![a-z0-9-])/g;

const PLAYER_QUESTION = /\bwhich player\b|\bwho (had|took|made|has|played|won) the (most|highest|longest|fastest|hardest)\b|\bmost (shots|goals|passes|tackles|interceptions|recoveries|progressive passes|sprints)\b|\btop (scorer|tackler)\b|\bleaders?\b|\bwho leads\b|\bwho (ran|covered|sprinted) (the )?(furthest|most)\b|\bwho (was|is) (the )?(fastest|quickest)\b|\bfastest player\b|\bquickest player\b/;
const OPINION_RANKING = /\bbest player\b|\bman of the match\b|\bplayer of the match\b|\bstar man\b|\bmvp\b/;
const KNOWN_WORDS = new Set([
  "who", "what", "which", "when", "how", "did", "does", "do", "is", "are", "was", "were", "the", "a", "an", "and", "or", "in", "on",
  "at", "of", "for", "to", "by", "after", "before", "since", "between", "from", "until", "up", "their", "they", "them", "it",
  "team", "teams", "side", "sides", "home", "away", "both", "each", "player", "players", "match", "game", "half", "score", "scored",
  "take", "took", "have", "had", "has", "make", "made", "get", "got", "much", "many", "more", "most", "his", "her", "show", "me",
  "tell", "about", "xg", "matchdesk", "ask", "eligible", "verified", "can", "you", "i", "please", "s",
]);

function parseSubjects(question: string, ctx: Pick<MatchContext, "names" | "teams">): string[] {
  const found: string[] = [];
  const add = (id: string) => { if (!found.includes(id)) found.push(id); };
  for (const [, id] of question.matchAll(RECORD_ID)) if (Object.hasOwn(ctx.names, id) && !Object.hasOwn(ctx.teams, id)) add(id);
  const q = question.replace(RECORD_ID, " ");
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

const NOT_NAMES = new Set([
  ...KNOWN_WORDS, "anyone", "anybody", "someone", "somebody", "everyone", "nobody", "we", "us", "our", "he", "she", "him",
  "they", "them", "it", "that", "this", "these", "those", "either", "neither", "each", "both", "one", "team", "side",
  "first", "second", "third", "last", "final", "half", "minute", "minutes", "time", "goal", "goals", "shot", "shots",
]);

/** A name the question gives a player who is not in this match, if any. Only clear forms count. */
function unknownPerson(original: string, q: string, ctx: Pick<MatchContext, "names" | "teams">): string | null {
  const known = new Set([...Object.values(ctx.names), ...Object.values(ctx.teams)].map((n) => n.toLowerCase()));
  const candidates: string[] = [];
  const did = /\b(?:did|does|has|had) ([a-z][a-z'-]+) (?:take|score|have|make|get|shoot|pass)\b/.exec(q);
  if (did) candidates.push(did[1]);
  const possessive = /\b([a-z][a-z-]+)'s (?:shots?|goals?|xg|pass(?:ing)?|possession|final[- ]third|stats|game|match|performance)\b/.exec(q);
  if (possessive) candidates.push(possessive[1]);
  for (const word of candidates) {
    const bare = word.replace(/'s$/, "");
    if (NOT_NAMES.has(bare) || known.has(bare)) continue;
    return original.split(/[^A-Za-zÀ-ÿ'-]+/).find((w) => w.toLowerCase().replace(/'s$/, "") === bare) ?? bare;
  }
  return null;
}

function parseMetric(q: string): Metric | null {
  if (/\bxg\b|expected goals/.test(q)) return "synthetic_xg.v1";
  if (/pass(ing)? difficulty|difficult(y of| )pass|hardest pass|difficulty rating/.test(q)) return "pass_difficulty.v1";
  if (/pass(es|ing)? (length|distance)|how (long|far) (were|are|was) (the |their |his |her )?pass|longest pass|average pass|pass(es)? travel/.test(q)) return "pass_distance.v1";
  if (/progressive pass|progressive/.test(q)) return "progressive_passes.v1";
  if (/under pressure|pressured pass|pressing/.test(q)) return "pressured_passes.v1";
  if (/shot speed|speed of (his |her |their )?shots/.test(q)) return "shot_speed.v1";
  if (/top speed|max(imum)? speed|fastest player|quickest player|who was (the )?fastest|sprint speed|how fast (did|does|can) [a-z]+ (run|sprint)/.test(q)) return "top_speed.v1";
  if (/distance (covered|run|ran)|how far (did|has) [a-z]+ run|\bran (the )?(furthest|most)\b|covered the most (ground|distance)|kilomet(re|er)s?|\bkm\b(?!\/h)/.test(q)) return "distance_covered.v1";
  if (/\bsprints?\b|\bsprinted\b|high[- ]speed runs?/.test(q)) return "sprints.v1";
  if (/ball speed|pass speed|speed of (the )?(ball|pass)|how fast (was|is|were) the (ball|pass)|km\/h|kph/.test(q)) return "ball_speed.v1";
  if (/\btackles?\b|\btackled\b|\btackling\b/.test(q)) return "tackles.v1";
  if (/\binterceptions?\b|\bintercepted\b/.test(q)) return "interceptions.v1";
  if (/\brecover(ies|y|ed)\b|won the ball back|ball wins?\b|regain/.test(q)) return "recoveries.v1";
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
  // Explanations come before figures: "what is xG?" asks what it is, not what it was, and
  // "what does Blocked mean?" asks about the app's own status chip, not blocked shots.
  for (const topic of HELP) {
    if (topic.id === "metrics" && topic.patterns.slice(0, 3).some((p) => p.test(q))) return { intent: "help", topic: "metrics" };
  }
  if (/\bmean(s|ing)?\b|\bhow (do|can|should) i\b|\bwhat do(es)? (the|a|an)\b|\bstatus(es)?\b|\bchips?\b|\bbadges?\b|\bshot map\b/.test(q)) {
    for (const topic of HELP) if (topic.patterns.some((p) => p.test(q))) return { intent: "help", topic: topic.id };
  }
  for (const [pattern, label] of UNSUPPORTED_STATS) {
    if (pattern.test(q)) return decline("unsupported", `I can't check ${label}: it isn't one of the registered metrics, so I won't estimate it. I can check goals, shots, xG, final-third entries, pass accuracy, pass length, progressive passes, pass difficulty, passes under pressure, ball speed, tackles, interceptions, recoveries, possession, and from synthetic tracking shot speed, top speed, distance covered and sprints.`);
  }
  for (const [pattern, text] of QUALIFIERS) if (pattern.test(q)) return decline("unsupported", text);
  const named = "Ask about any player in either squad by name, such as Okafor, Mensah or Lindqvist.";
  const unnamedId = [...q.matchAll(RECORD_ID)].map((m) => m[1]).find((id) => !Object.hasOwn(ctx.names, id) || Object.hasOwn(ctx.teams, id));
  if (unnamedId) return decline("unsupported", `${unnamedId} is not a player in either squad, so I can't answer for them. ${named}`);
  const subjects = parseSubjects(q, ctx);
  const stranger = unknownPerson(question, q, ctx);
  if (stranger) return decline("unsupported", `There's no player called ${stranger} in either squad. ${named}`);
  const aboutTeams = /\b(which|what) (team|side|club)\b|\bteams?\b|\bsides?\b/.test(q);
  if (OPINION_RANKING.test(q)) {
    return decline("unsupported", "\u201cBest player\u201d is a judgement, not a figure I can check. Ask who led a statistic instead, such as \u201cWho made the most tackles?\u201d or \u201cWhich player had the most shots?\u201d");
  }
  if (PLAYER_QUESTION.test(q) && !aboutTeams && !subjects.some((s) => !Object.hasOwn(ctx.teams, s))) {
    const ranked = /\bscor(er|ed|ing)\b|\bgoals?\b/.test(q) && !/\bshots?\b/.test(q) ? "goals.v1" : parseMetric(q);
    if (!ranked) return decline("unsupported", "Tell me which statistic to rank players by, such as shots, tackles, progressive passes or ball recoveries.");
    const reading = parseWindow(q, "range");
    if ("unclear" in reading) return decline("unsupported", reading.unclear);
    return { intent: "leaders", metric: ranked, subjects, window: reading.window };
  }
  if (subjects.length > 2) return decline("unsupported", "Ask about one or two teams or players at a time.");
  const comparesGoals = /\b(more|fewer|less) (goals )?than\b|\bscore more\b|\boutscore/.test(q);
  const ordinal = ORDINAL_GOAL.exec(q);
  const isScorers = !comparesGoals && !/\bhow many\b/.test(q) && (ordinal != null || /\bwho scored\b|\bscorers?\b|\bgoal ?scorers?\b|\bwho got the goals?\b|\bwhen (was|were|did|came) .*\bgoals?\b|\bwhen did .* score\b|\bdid .* score\b/.test(q));
  if (comparesGoals) {
    const reading = parseWindow(q, "range");
    if ("unclear" in reading) return decline("unsupported", reading.unclear);
    return { intent: "metric", metric: "goals.v1", subjects, window: reading.window };
  }
  const isResult = !isScorers && /\bdid [a-z' -]{2,30} (win|lose|draw)\b/.test(q);
  const isScore = !isScorers && /\bscore(line)?\b|\bwho('s| is| was) (winning|ahead|leading|in front)\b|\bwho won\b|\bwho('s| is) (going to )?win(ning)?\b|\b(the |final |full[- ]time )result\b|\bwho (lost|is losing)\b/.test(q) && !/\bshots?\b/.test(q);
  const reading = parseWindow(q, isScore || isResult ? "score" : "range");
  if ("unclear" in reading) return decline("unsupported", reading.unclear);
  const window = reading.window;
  if (isScorers) return ordinal ? { intent: "scorers", subjects, window, nth: ORDINALS[ordinal.slice(1).find(Boolean) as string] } : { intent: "scorers", subjects, window };
  if (isResult) return { intent: "score", window };
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
  scorers: ["intent", "subjects", "window", "nth"],
  leaders: ["intent", "metric", "subjects", "window"],
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
      if (!validSubjects(subjects, ctx) || !validWindow(plan.window)) return null;
      if (plan.nth === undefined || plan.nth === null) return { intent: "scorers", subjects: [...subjects], window: window() };
      return Number.isInteger(plan.nth) && (plan.nth as number) >= 1 && (plan.nth as number) <= 4
        ? { intent: "scorers", subjects: [...subjects], window: window(), nth: plan.nth as number } : null;
    }
    case "leaders": {
      // Players are ranked; subjects may only narrow the ranking to one team.
      if (typeof plan.metric !== "string" || !Object.hasOwn(METRICS, plan.metric) || !validWindow(plan.window)) return null;
      const subjects = plan.subjects ?? [];
      if (!validSubjects(subjects, ctx) || subjects.length > 1 || subjects.some((s) => !Object.hasOwn(ctx.teams, s))) return null;
      return { intent: "leaders", metric: plan.metric as Metric, subjects: [...subjects], window: window() };
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
    case "scorers": return `${plan.nth ? `${ordinalWord(plan.nth)} goal` : "scorers"} · ${plan.subjects.length ? plan.subjects.map(name).join(" and ") : "both teams"} · ${w(plan.window)}`;
    case "summary": return `summary · ${name(plan.subject)} · ${w(plan.window)}`;
    case "leaders": return `${METRICS[plan.metric].label} leaders · ${plan.subjects.length ? plan.subjects.map(name).join(" and ") : "both teams"} · ${w(plan.window)}`;
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
    if (plan.last_minutes * MINUTE_MS >= end) {
      return { window: { from_ms: 0, to_ms: end }, phrase: `up to ${mark(end)}`, scope: `Whole match so far, to ${mark(end)}`, fromKickOff: true,
        clamped: `The replay is only ${mark(end)} long, so this covers the whole match so far.` };
    }
    const from = end - plan.last_minutes * MINUTE_MS;
    return { window: { from_ms: from, to_ms: end }, phrase: `in the last ${plan.last_minutes} minutes`, scope: `${mark(from)} to ${mark(end)}`, fromKickOff: false };
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
    case "pass_distance.v1": return `${name}'s average pass length was ${roundHalfUp(value, 1)} metres ${phrase}.`;
    case "progressive_passes.v1": return `${name} played ${value} progressive ${value === 1 ? "pass" : "passes"} ${phrase}.`;
    case "pass_difficulty.v1": return `${name}'s pass difficulty rating was ${roundHalfUp(value, 1)} ${phrase}.`;
    case "ball_speed.v1": return `${name}'s estimated ball speed was ${roundHalfUp(value, 1)} km/h ${phrase}.`;
    case "pressured_passes.v1": return `${name} played ${value} ${value === 1 ? "pass" : "passes"} under pressure ${phrase}.`;
    case "tackles.v1": return `${name} made ${value} ${value === 1 ? "tackle" : "tackles"} ${phrase}.`;
    case "interceptions.v1": return `${name} made ${value} ${value === 1 ? "interception" : "interceptions"} ${phrase}.`;
    case "recoveries.v1": return `${name} made ${value} ball ${value === 1 ? "recovery" : "recoveries"} ${phrase}.`;
    case "shot_speed.v1": return `${name}'s shot speed was ${roundHalfUp(value, 1)} km/h ${phrase}.`;
    case "top_speed.v1": return `${name} reached a top speed of ${roundHalfUp(value, 1)} km/h ${phrase}.`;
    case "distance_covered.v1": return `${name} covered ${roundHalfUp(value, 1)} km ${phrase}.`;
    case "sprints.v1": return `${name} made ${value} ${value === 1 ? "sprint" : "sprints"} ${phrase}.`;
  }
}

/** The precision a metric is stated at: whole counts, two places for shares and xG, one for measures. */
export function decimalsFor(metric: Metric): number | null {
  const unit = METRICS[metric].unit;
  return unit === "count" ? null : unit === "ratio" || unit === "synthetic_xg" ? 2 : 1;
}

/** Notes that say how a measure was obtained, shown with every answer that uses it. */
const METRIC_NOTES: Partial<Record<Metric, string>> = {
  "synthetic_xg.v1": "Synthetic xG is this demo's own chance-quality model, not a licensed xG feed.",
  "ball_speed.v1": "Ball speed is estimated: pass length over the time to the next logged event, not from tracking.",
  "pass_difficulty.v1": "Pass difficulty is a 0\u2013100 rating of each attempt: 45% length, 30% forward ambition, 15% a target in the final sixth, 10% pressure.",
  "pass_distance.v1": "Lengths are measured on a 105 m \u00d7 68 m pitch.",
  "progressive_passes.v1": "A progressive pass is completed, goes at least 10 m forward and ends at least 25% closer to goal.",
  "shot_speed.v1": "Shot speed is the mean ball speed of the shots, from the log's synthetic tracking (this demo's own model, not a tracking provider).",
  "top_speed.v1": "Top speed is the fastest a player was moving at any of their actions, from the log's synthetic tracking.",
  "distance_covered.v1": "Distance is summed from the metres the log's synthetic tracking records between a player's actions.",
  "sprints.v1": "A sprint is an action made at 25.2 km/h or faster, from the log's synthetic tracking.",
};

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
  const decimals = decimalsFor(metric);
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
const PASS_AVERAGES: readonly Metric[] = ["pass_accuracy.v1", "pass_distance.v1", "pass_difficulty.v1", "ball_speed.v1"];

/** An average has no meaning without anything to average: say so instead of verifying a 0. */
function emptyRatio(metric: Metric, subject: string, window: Window, ctx: MatchContext): string | null {
  if (!PASS_AVERAGES.includes(metric)) return null;
  const isPlayer = !Object.hasOwn(ctx.teams, subject);
  const passes = ctx.events.some((e) => e.type === "pass" && inWindow(e, window) && (isPlayer ? e.player_id === subject : e.team_id === subject)
    && (metric !== "ball_speed.v1" || e.outcome === "complete"));
  return passes ? null : `${nameOf(subject, ctx)}: no passes recorded in this window, so there is no ${METRICS[metric].label} to check.`;
}

function comparison(metric: Metric, lines: CheckedLine[], ctx: MatchContext): string | undefined {
  if (lines.length !== 2 || lines.some((l) => l.result.status !== "verified" || l.result.observed == null)) return undefined;
  const [a, b] = lines.map((l) => ({ id: (l.claim.assertion?.subject.team_id ?? l.claim.assertion?.subject.player_id) as string, raw: l.result.observed as number, shown: l.claim.assertion?.value as number }));
  if (a.id === b.id) return undefined;
  const label = METRICS[metric].label;
  if (a.raw === b.raw) return METRICS[metric].unit === "count" ? `Level: the same number of ${label} each.` : `Level: the same ${label}.`;
  const [hi, lo] = a.raw > b.raw ? [a, b] : [b, a];
  if (hi.shown === lo.shown) return `Almost level: ${nameOf(hi.id, ctx)} are very slightly ahead on ${label} before rounding.`;
  const more: Partial<Record<Metric, string>> = {
    "pass_accuracy.v1": "a higher pass accuracy",
    "possession_time.v1": "more of the ball",
    "synthetic_xg.v1": "a higher synthetic xG",
    "pass_distance.v1": "a longer average pass",
    "pass_difficulty.v1": "a higher pass difficulty rating",
    "ball_speed.v1": "a higher estimated ball speed",
    "shot_speed.v1": "a higher shot speed",
    "top_speed.v1": "a higher top speed",
    "distance_covered.v1": "more distance covered",
  };
  return `${nameOf(hi.id, ctx)} had ${more[metric] ?? `more ${label}`} than ${nameOf(lo.id, ctx)}.`;
}

/** Below this many passes in the window, a player's pass averages are not ranked. */
const LEADER_MIN_PASSES = 10;

function leaders(plan: Extract<Plan, { intent: "leaders" }>, resolved: { window: Window; phrase: string; scope: string }, ctx: MatchContext, evidence: Evidence, notes: (...extra: (string | undefined | null)[]) => string | undefined): Answer {
  const teams = plan.subjects.filter((s) => Object.hasOwn(ctx.teams, s));
  const averages = PASS_AVERAGES.includes(plan.metric);
  const passCount = new Map<string, number>();
  for (const e of ctx.events) {
    if (e.player_id && inWindow(e, resolved.window) && (!teams.length || teams.includes(e.team_id as string))) {
      passCount.set(e.player_id, (passCount.get(e.player_id) ?? 0) + (e.type === "pass" ? 1 : 0));
    }
  }
  const players = [...passCount.keys()].filter((p) => Object.hasOwn(ctx.names, p) && (!averages || (passCount.get(p) ?? 0) >= LEADER_MIN_PASSES));
  const scored = players
    .map((p) => ({ p, raw: computeMetric(plan.metric, ctx.events, { player_id: p }, resolved.window) }))
    .filter((r) => r.raw > 0)
    .sort((a, b) => b.raw - a.raw || nameOf(a.p, ctx).localeCompare(nameOf(b.p, ctx)));
  const label = METRICS[plan.metric].label;
  if (!scored.length) return { kind: "decline", text: `No player recorded any ${label} in that part of the match.` };
  const top = scored.slice(0, 3);
  const lines = top.map((r) => measuredLine(plan.metric, r.p, resolved, ctx, evidence));
  const verified = lines.every((l) => l.result.status === "verified");
  const tied = scored.filter((r) => r.raw === scored[0].raw);
  const tiedNames = tied.map((r) => nameOf(r.p, ctx));
  const joint = tiedNames.length === 2 ? tiedNames.join(" and ") : `${tiedNames.slice(0, -1).join(", ")} and ${tiedNames.at(-1)}`;
  const derived = !verified ? undefined
    : tied.length > 1 ? `${joint} are joint top for ${label}.`
    : `${nameOf(scored[0].p, ctx)} led ${scored.length} players on ${label}.`;
  const pool = averages ? `Players with at least ${LEADER_MIN_PASSES} passes in this window.` : undefined;
  return { kind: "match", scope: `${resolved.scope}${teams.length ? ` · ${teams.map((t) => nameOf(t, ctx)).join(" and ")}` : ""}`, lines, derived, note: notes(pool, METRIC_NOTES[plan.metric]) };
}

const DECLINES: Record<DeclineReason, string> = {
  prediction: "I don't predict results. I only state what the recorded events show, and I check every figure before I show it.",
  other_match: "I only know this synthetic match, Northbridge FC v Riverside United. I have no data on real clubs or other games.",
  personal: "I only answer about what happened on the pitch in this match, not about people's private lives.",
  unsupported: "I can't check that against the event log, so I won't guess.",
};

export const UNKNOWN_TEXT = "I couldn't read that question. Try the score, scorers, shots, possession, xG, passing (accuracy, length, progressive passes, difficulty, ball speed, pressure), defending (tackles, interceptions, recoveries) or tracking (shot speed, top speed, distance, sprints), for a team, a player or part of the game; who led a statistic; or how the app works.";

const ordinalWord = (n: number) => ["first", "second", "third", "fourth"][n - 1] ?? `${n}th`;

/** Whether answering a plan needs the event log. */
export function needsEvents(plan: Plan): boolean {
  return plan.intent === "metric" || plan.intent === "score" || plan.intent === "scorers" || plan.intent === "summary" || plan.intent === "leaders";
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
    const past = resolved.window.to_ms < ctx.replayEndMs || resolved.window.period === 1;
    // A lead or a draw only makes sense for a window that starts at kick-off.
    const derived = !verified ? undefined
      : !resolved.fromKickOff ? `Goals in this window only: ${nameOf(teams[0], ctx)} ${h}, ${nameOf(teams[1], ctx)} ${a}. This is not the score.`
      : h === a ? `It ${past ? "was" : "is"} level, ${h}–${a}.`
      : `${nameOf(h > a ? teams[0] : teams[1], ctx)} ${past ? "led" : "lead"} ${Math.max(h, a)}–${Math.min(h, a)}.`;
    const unfinished = resolved.fromKickOff && resolved.window.period == null && resolved.window.to_ms === ctx.replayEndMs
      ? `The replay stops at ${mark(ctx.replayEndMs)}, before full time, so there is no final result yet.` : undefined;
    return { kind: "match", scope: resolved.scope, lines, derived, note: notes(unfinished) };
  }
  if (plan.intent === "scorers") {
    const goals = ctx.events.filter((e) => e.type === "goal" && inWindow(e, resolved.window)
      && (!plan.subjects.length || plan.subjects.includes(e.player_id as string) || plan.subjects.includes(e.team_id as string)));
    if (!goals.length) {
      const who = plan.subjects.length ? plan.subjects : teams;
      const lines = who.map((t) => measuredLine("goals.v1", t, resolved, ctx, evidence));
      return { kind: "match", scope: resolved.scope, lines, note: notes("No goals in that part of the match.") };
    }
    if (plan.nth != null && plan.nth > goals.length) {
      return { kind: "decline", text: `Only ${goals.length} ${goals.length === 1 ? "goal has" : "goals have"} been scored in that part of the match, so there is no ${ordinalWord(plan.nth)} goal to check.` };
    }
    const chosen = plan.nth != null ? [goals.sort((x, y) => x.sequence - y.sequence)[plan.nth - 1]] : goals;
    const lines = chosen.map((goal) => {
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
    return { kind: "match", scope: resolved.scope, lines, note: notes(plan.nth != null ? `The ${ordinalWord(plan.nth)} goal in this part of the match, in the order they were scored.` : undefined) };
  }
  if (plan.intent === "leaders") return leaders(plan, resolved, ctx, evidence, notes);
  if (plan.intent === "summary") {
    const isTeam = Object.hasOwn(ctx.teams, plan.subject);
    if (!isTeam && !ctx.events.some((e) => e.player_id === plan.subject && inWindow(e, resolved.window))) {
      return { kind: "decline", text: `${nameOf(plan.subject, ctx)} has no recorded events in that part of the match, so there is nothing to check.` };
    }
    const metrics: Metric[] = isTeam
      ? ["goals.v1", "shots.v1", "possession_time.v1", "pass_accuracy.v1", "progressive_passes.v1", "tackles.v1"]
      : ["goals.v1", "shots.v1", "pass_accuracy.v1", "progressive_passes.v1", "tackles.v1", "recoveries.v1"];
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
  return { kind: "match", scope: resolved.scope, lines, derived: comparison(plan.metric, lines, ctx), note: notes(...empty, METRIC_NOTES[plan.metric]) };
}

/** Read and answer a question with the built-in rules. */
export function ask(question: string, ctx: MatchContext | null, names: Pick<MatchContext, "names" | "teams">): { plan: Plan; answer: Answer } {
  const plan = parseQuestion(question, names);
  return { plan, answer: answerPlan(plan, ctx) };
}
