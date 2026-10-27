/** Re-run claims with the browser's copy of the verifier, loaded only when a page asks. */
"use client";

import { useEffect, useState } from "react";
import type { Claim, CompactLog } from "./verifier";

export type Recheck = "pending" | "agrees" | "disagrees";

/** Every claim must verify in the browser exactly as it did on the server. */
export function useRecheck(
  claims: readonly { claim: Claim; status: string }[], matchId: string, replayEndMs: number, names: Record<string, string>,
): Recheck {
  const [state, setState] = useState<Recheck>("pending");
  useEffect(() => {
    let live = true;
    Promise.all([import("./generated/nbr-riv-events.json"), import("./verifier")]).then(([log, verifier]) => {
      const events = verifier.expandLog(log.default as unknown as CompactLog);
      const evidence = { match_id: matchId, event_ids: events.map((e) => e.event_id), window: { from_ms: 0, to_ms: replayEndMs } };
      const agrees = claims.every((c) => verifier.verifyClaim(c.claim, evidence, events, names).status === c.status && c.status === "verified");
      if (live) setState(agrees ? "agrees" : "disagrees");
    }, () => undefined);
    return () => { live = false; };
  }, [claims, matchId, replayEndMs, names]);
  return state;
}
