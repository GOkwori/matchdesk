/** Canonical, synthetic-only MatchDesk v3 design fixture.
 *
 * No API, event stream, AI provider, authentication, or stored producer state
 * supplies these values. Never render them as independently verified live data.
 * Source: approved 11 October 2026 Sunset Studio v3 design specification.
 */
export const fixture = {
  mode: "synthetic replay",
  home: "Northbridge FC",
  homeCode: "NBR",
  away: "Riverside United",
  awayCode: "RIV",
  clock: "67:12",
  half: "Second half",
  replaySpeed: "1×",
  scoreHome: 2,
  scoreAway: 1,
  eventCount: 1284,
  latestEvent: "E-1421",
  latestEventClock: "67:08",
  replayDate: "11 Oct 2026",
} as const;

/** Only recorded synthetic events provided by the signed-off design brief. */
export type Moment = {
  readonly id: string;
  readonly clock: string;
  readonly event: string;
  readonly title: string;
  readonly details: string;
  readonly kind: "Goal" | "Yellow card" | "Corner" | "Substitution";
  readonly scoreAfter: string;
};

export const moments: readonly Moment[] = [
  { id: "M-01", clock: "27:40", event: "E-0561", title: "Haddad booked for Riverside", details: "Haddad (RIV #6), late challenge", kind: "Yellow card", scoreAfter: "0–0" },
  { id: "M-02", clock: "34:18", event: "E-0688", title: "Okafor opens the scoring", details: "Okafor (NBR #9), right-footed finish, open play", kind: "Goal", scoreAfter: "1–0" },
  { id: "M-03", clock: "41:03", event: "E-0790", title: "Lindqvist levels for Riverside", details: "Lindqvist (RIV #11), finish from cut-back", kind: "Goal", scoreAfter: "1–1" },
  { id: "M-04", clock: "58:03", event: "E-1359", title: "Northbridge corner, right side", details: "Corner awarded on the right", kind: "Corner", scoreAfter: "1–1" },
  { id: "M-05", clock: "58:17", event: "E-1366", title: "Okafor restores Northbridge lead", details: "Okafor (NBR #9), header from the corner, 14 seconds after E-1359", kind: "Goal", scoreAfter: "2–1" },
  { id: "M-06", clock: "63:04", event: "E-1402", title: "Mensah booked for Northbridge", details: "Mensah (NBR #4), late midfield challenge", kind: "Yellow card", scoreAfter: "2–1" },
  { id: "M-07", clock: "67:08", event: "E-1421", title: "Riverside United substitution", details: "Substitution event; player names not supplied", kind: "Substitution", scoreAfter: "2–1" },
];

export type MatchStatistic = {
  readonly label: string;
  readonly home: number;
  readonly away: number;
  readonly suffix?: "%";
};

/** Counts and possession shares come from the frozen design script, not tracking. */
export const matchStatistics: readonly MatchStatistic[] = [
  { label: "Possession", home: 58, away: 42, suffix: "%" },
  { label: "Shots", home: 14, away: 9 },
  { label: "On target", home: 6, away: 3 },
  { label: "Corners", home: 6, away: 3 },
  { label: "Fouls", home: 8, away: 11 },
  { label: "Yellow cards", home: 1, away: 1 },
  { label: "Red cards", home: 0, away: 0 },
];

/** Editorial eligibility is demonstration-only; not a server decision. */
export const editorial = {
  insightsNeedingReview: 3,
  pendingClaims: 1,
  draftCount: 2,
  ineligibleDrafts: 1,
  blockedDraft: "D-031 v3",
  eligibleDraft: "D-029 v2",
  blockingReason: "CL-0215 is pending and CL-0216 has no supporting evidence. Resolve or remove before re-verification.",
} as const;

export const latestMoments = moments.filter((moment) =>
  ["M-02", "M-03", "M-05", "M-06"].includes(moment.id)
);
