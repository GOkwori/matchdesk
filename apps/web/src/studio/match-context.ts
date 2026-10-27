/** The match as the verifier sees it, for pages that compute and check sentences while rendering. */
import eventLog from "./generated/nbr-riv-events.json";
import { expandLog, type CompactLog } from "./verifier";
import type { MatchContext } from "./ask";
import { matchExport } from "./data";

let cached: MatchContext | null = null;

/** Built once per server process: the full log, display names and the replay point. */
export function matchContext(): MatchContext {
  if (!cached) {
    const names = matchExport.display_names as Record<string, string>;
    cached = {
      events: expandLog(eventLog as unknown as CompactLog),
      names,
      teams: { nbr: names.nbr ?? "Northbridge", riv: names.riv ?? "Riverside" },
      replayEndMs: matchExport.replay_end_ms,
      matchId: matchExport.match_id,
    };
  }
  return cached;
}
