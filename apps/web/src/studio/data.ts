/** Canonical synthetic fixture for the locked Sunset Studio frontend.
 *
 * Numbers come from generated/nbr-riv.json, which `python -m scripts.export_demo_data`
 * builds by running the backend's registered metric formulas over the canonical
 * event log (backend/src/matchdesk/domain/canonical_match.py). A pytest gate fails
 * if the committed export is stale. The match is invented demonstration data,
 * never a live match, and nothing here grants approval or publication authority.
 */
import exportData from "./generated/nbr-riv.json";

export type ExportEvent = {
  id: string; clock_ms: number; period: number; type: string; team: string | null; player: string | null;
  outcome: string | null; tags: string[]; x?: number; y?: number; xg?: number;
};

export const matchExport = exportData as typeof exportData & { key_events: ExportEvent[]; shots: ExportEvent[]; feed: ExportEvent[] };

export const REPLAY_END_SECONDS = matchExport.replay_end_ms / 1000;

const keyEvents = new Map(matchExport.key_events.map((e) => [e.id, e]));

/** Seconds of a scripted key event, read from the export so the UI cannot drift from the log. */
function keySeconds(id: string): number {
  const event = keyEvents.get(id);
  if (!event) throw new Error(`Key event ${id} is missing from the demo export`);
  return event.clock_ms / 1000;
}

export const fixture = {
  slug: "nbr-riv",
  home: { name: "Northbridge FC", short: "Northbridge", code: "NBR" },
  away: { name: "Riverside United", short: "Riverside", code: "RIV" },
  eventCount: matchExport.event_count,
  latestEvent: matchExport.last_event.id,
  digest: matchExport.evidence_digest,
  replayDate: "11 Oct 2026",
} as const;

export const eventCountText = fixture.eventCount.toLocaleString("en-GB");

/** Display name for a player id (invented names for the players the story mentions). */
export function playerName(id: string | null | undefined): string {
  if (!id) return "";
  const names = matchExport.players as Record<string, string>;
  return names[id] ?? `#${Number(id.split("-")[1])}`;
}

export type Team = "NBR" | "RIV";
export type MomentKind = "Goal" | "Yellow card" | "Corner" | "Substitution";

export type Moment = {
  readonly id: string;
  readonly seconds: number;
  readonly event: string;
  readonly kind: MomentKind;
  readonly team: Team;
  readonly title: string;
  readonly detail: string;
  readonly claimIds: readonly string[];
};

/** Format seconds as the match clock used everywhere in the UI (mm:ss). */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export const moments: readonly Moment[] = [
  { id: "M-01", seconds: keySeconds("E-0561"), event: "E-0561", kind: "Yellow card", team: "RIV", title: "Haddad booked", detail: "Late challenge · Haddad (RIV #6)", claimIds: [] },
  { id: "M-02", seconds: keySeconds("E-0688"), event: "E-0688", kind: "Goal", team: "NBR", title: "Okafor opens the scoring", detail: "Right-footed finish, open play", claimIds: ["CL-0213"] },
  { id: "M-03", seconds: keySeconds("E-0790"), event: "E-0790", kind: "Goal", team: "RIV", title: "Lindqvist levels for Riverside", detail: "Finish from a cut-back", claimIds: [] },
  { id: "M-04", seconds: keySeconds("E-1359"), event: "E-1359", kind: "Corner", team: "NBR", title: "Northbridge corner", detail: "Corner from the right", claimIds: [] },
  { id: "M-05", seconds: keySeconds("E-1366"), event: "E-1366", kind: "Goal", team: "NBR", title: "Okafor header restores the lead", detail: "Header from the corner 14 seconds earlier", claimIds: ["CL-0213"] },
  { id: "M-06", seconds: keySeconds("E-1402"), event: "E-1402", kind: "Yellow card", team: "NBR", title: "Mensah booked", detail: "Late challenge in midfield · Mensah (NBR #4)", claimIds: [] },
  { id: "M-07", seconds: keySeconds("E-1421"), event: "E-1421", kind: "Substitution", team: "RIV", title: "Riverside substitution", detail: "Barros off, Kovac on", claimIds: [] },
];

/** Score at a replay time, derived only from the recorded goal moments. */
export function scoreAt(seconds: number): { home: number; away: number } {
  let home = 0;
  let away = 0;
  for (const m of moments) {
    if (m.kind !== "Goal" || m.seconds > seconds) continue;
    if (m.team === "NBR") home += 1;
    else away += 1;
  }
  return { home, away };
}

/** Moments that have happened by a replay time, most recent first. */
export function momentsUntil(seconds: number): Moment[] {
  return moments.filter((m) => m.seconds <= seconds).sort((a, b) => b.seconds - a.seconds);
}

export function findMoment(id: string | null | undefined): Moment | undefined {
  return moments.find((m) => m.id === id);
}

const home = matchExport.statistics.nbr;
const away = matchExport.statistics.riv;
const homeShare = Math.round(matchExport.possession.home_share * 100);

/** Whole-match statistics to 67:12, computed from the event log by the export. */
export const statistics: readonly { label: string; home: number; away: number; suffix?: "%" }[] = [
  { label: "Possession", home: homeShare, away: 100 - homeShare, suffix: "%" },
  { label: "Shots", home: home.shots, away: away.shots },
  { label: "On target", home: home.on_target, away: away.on_target },
  { label: "Corners", home: home.corners, away: away.corners },
  { label: "Fouls", home: home.fouls, away: away.fouls },
  { label: "Yellow cards", home: home.yellow_cards, away: away.yellow_cards },
];

/** possession_time.v1 inputs for CL-0214 (attributable in-play time). */
export const possession = {
  homeSeconds: matchExport.possession.home_ms / 1000,
  totalSeconds: matchExport.possession.total_ms / 1000,
} as const;

/** Northbridge possession share per five-minute window, used by the CL-0214 chart. */
export const possessionSeries: readonly { minute: number; share: number }[] = matchExport.possession_series.map((w) => ({
  minute: w.from_minute,
  share: Math.round(w.home_share * 100),
}));

export const shots: readonly ExportEvent[] = matchExport.shots;
export const recentEvents: readonly ExportEvent[] = matchExport.feed;

export type Verdict = "verified" | "pending" | "failed" | "not-yet";

export type Claim = {
  readonly id: string;
  readonly text: string;
  readonly short: string;
  readonly kind: "fact" | "metric" | "interpretation" | "history";
  readonly evidence: readonly string[];
};

export const claims: readonly Claim[] = [
  { id: "CL-0213", text: "Okafor scored both Northbridge goals", short: "Okafor scored both goals", kind: "fact", evidence: ["E-0688", "E-1366"] },
  { id: "CL-0214", text: "Northbridge have had 58% possession", short: "58% possession", kind: "metric", evidence: [`${eventCountText} events`] },
  { id: "CL-0215", text: "Riverside’s best spell came between 30 and 45 minutes", short: "Riverside’s best spell 30–45′", kind: "interpretation", evidence: [] },
  { id: "CL-0216", text: "It is Okafor’s first brace of the season", short: "First brace of the season", kind: "history", evidence: [] },
];

export function findClaim(id: string): Claim | undefined {
  return claims.find((c) => c.id === id);
}

/** Possession share for CL-0214, in percent with one decimal place. */
export function possessionShare(): number {
  return Math.round((possession.homeSeconds / possession.totalSeconds) * 1000) / 10;
}

/** Deterministic verdict for a claim at a replay time. A forged value is recalculated, never trusted. */
export function verdict(claim: Claim, seconds = REPLAY_END_SECONDS, claimedPossession = 58): Verdict {
  switch (claim.kind) {
    case "fact": {
      const okaforGoals = moments.filter((m) => m.kind === "Goal" && m.team === "NBR" && m.seconds <= seconds).length;
      return okaforGoals >= 2 ? "verified" : "not-yet";
    }
    case "metric":
      return Math.abs(possessionShare() - claimedPossession) <= 0.5 ? "verified" : "failed";
    case "interpretation":
      return "pending";
    case "history":
      return "failed";
  }
}

export const verdictLabel: Record<Verdict, string> = {
  verified: "Verified",
  pending: "Pending",
  failed: "Failed",
  "not-yet": "Not verifiable yet",
};

/** Draft D-031 narrative: one sentence per claim, editable in the composer. */
export type Sentence = { readonly claimId: string; readonly text: string; readonly opinion?: string };

export const d031Sentences: readonly Sentence[] = [
  { claimId: "CL-0213", text: "Okafor has scored both Northbridge goals, heading in from a corner at 58:17 to restore the lead." },
  { claimId: "CL-0214", text: "Northbridge have had 58% of possession at the replay point." },
  { claimId: "CL-0215", text: "Riverside’s best spell came between 30 and 45 minutes.", opinion: "In our view, Riverside’s best spell came between 30 and 45 minutes." },
  { claimId: "CL-0216", text: "It is Okafor’s first brace of the season." },
];

export type SentenceState = "keep" | "opinion" | "removed";

/** A draft is eligible when every kept sentence is verified or explicitly marked as opinion. */
export function draftEligibility(states: Record<string, SentenceState>): { eligible: boolean; blocking: string[]; verified: number; opinions: number } {
  const blocking: string[] = [];
  let verified = 0;
  let opinions = 0;
  for (const s of d031Sentences) {
    const state = states[s.claimId] ?? "keep";
    if (state === "removed") continue;
    if (state === "opinion") { opinions += 1; continue; }
    const claim = findClaim(s.claimId);
    if (claim && verdict(claim) === "verified") verified += 1;
    else blocking.push(s.claimId);
  }
  return { eligible: blocking.length === 0, blocking, verified, opinions };
}

export const drafts = [
  { id: "D-031", version: "v3", title: "Okafor double restores Northbridge lead", author: "Priya Shah", updated: "11 Oct 2026, 18:32" },
  { id: "D-029", version: "v2", title: "Lindqvist levels for Riverside before the break", author: "Priya Shah", updated: "11 Oct 2026, 17:05" },
] as const;

export const STORY_SLUG = "okafor-header-restores-northbridge-lead";

export type Language = "en" | "es" | "fr";

/** Scripted, unreviewed fan-story copy, bound to the same verified claim (CL-0213). */
export const storyCopy: Record<Language, { label: string; headline: [string, string]; body: string; checks: [string, string, string]; matches: string; notChecked: string; title: string; note: string; caption: string }> = {
  en: {
    label: "English", title: "How we checked this", headline: ["58′ Goal for ", "Northbridge FC"],
    body: "Okafor rises to head in a corner from the right, his second of the match, and Northbridge lead again.",
    checks: ["Goal scorer", "Corner, then goal 14 s later", "Defender positions"],
    matches: "Matches event log", notChecked: "Not checked · no data",
    note: "Fans only see this after a producer approves it.", caption: "① Corner from the right · ② Okafor header, 14 seconds later",
  },
  es: {
    label: "Español", title: "Cómo lo comprobamos", headline: ["Gol de ", "Northbridge FC en el 58′"],
    body: "Okafor cabecea un córner desde la derecha, su segundo gol del partido, y Northbridge vuelve a ponerse por delante.",
    checks: ["Autor del gol", "Córner y gol 14 s después", "Posición de los defensas"],
    matches: "Coincide con el registro", notChecked: "Sin comprobar · sin datos",
    note: "Los aficionados solo lo ven cuando un productor lo aprueba.", caption: "① Córner desde la derecha · ② Cabezazo de Okafor, 14 segundos después",
  },
  fr: {
    label: "Français", title: "Comment nous l’avons vérifié", headline: ["But de ", "Northbridge FC à la 58e"],
    body: "Okafor reprend de la tête un corner venu de la droite, son deuxième but du match, et Northbridge repasse devant.",
    checks: ["Buteur", "Corner, puis but 14 s plus tard", "Position des défenseurs"],
    matches: "Conforme au journal", notChecked: "Non vérifié · pas de données",
    note: "Les supporters ne le voient qu’après validation par un producteur.", caption: "① Corner côté droit · ② Tête d’Okafor, 14 secondes plus tard",
  },
};

/** Guided tour: six stops across the real routes; the step lives in the URL (?tour=n). */
export const tourSteps: readonly { title: string; body: string; next?: string; nextLabel?: string }[] = [
  { title: "Start with the 58′ goal", body: "Open it to see exactly which events prove it happened.", next: "/match/nbr-riv/moments?moment=M-05&tour=2", nextLabel: "Open the goal" },
  { title: "Every moment links to evidence", body: `This goal is matched to recorded events. Next, see how a statistic is recalculated from all ${eventCountText} of them.`, next: "/match/nbr-riv/evidence/CL-0214?tour=3", nextLabel: "See the proof" },
  { title: "Claims are recalculated, not trusted", body: "Try a forged value: the verifier recomputes 58.0% from the events and rejects it.", next: "/producer/queue?tour=4", nextLabel: "See the review queue" },
  { title: "One draft is blocked", body: "D-031 has a pending interpretation and an unsupported claim. Fix it in the composer.", next: "/producer/compose/D-031?tour=5", nextLabel: "Open the composer" },
  { title: "Fix it and it re-verifies instantly", body: "Remove the unsupported sentence and mark the interpretation as opinion. Watch the draft become eligible.", next: `/story/${STORY_SLUG}?tour=6`, nextLabel: "See what fans get" },
  { title: "What fans see", body: "A verified story with its checks shown. It only goes out after a human producer approves it." },
];
