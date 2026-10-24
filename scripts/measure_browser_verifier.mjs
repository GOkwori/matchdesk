/** Time the browser verifier on every overlay, recap and story claim, as the studio re-checks them.
 *
 * Run: node --experimental-strip-types scripts/measure_browser_verifier.mjs
 * Node runs the same TypeScript module the browser loads; a phone is slower than this.
 */
import { readFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import { expandLog, verifyClaim } from "../apps/web/src/studio/verifier.ts";

const read = (p) => JSON.parse(readFileSync(new URL(`../apps/web/src/studio/generated/${p}`, import.meta.url), "utf8"));
const exportData = read("nbr-riv.json");
const began = performance.now();
const events = expandLog(read("nbr-riv-events.json")).filter((e) => e.match_clock_ms < exportData.replay_end_ms);
const expanded = performance.now() - began;
const evidence = { match_id: exportData.match_id, event_ids: events.map((e) => e.event_id), window: { from_ms: 0, to_ms: exportData.replay_end_ms } };
const claims = new Map();
for (const feed of ["nbr-riv-overlays.json", "nbr-riv-recaps.json", "nbr-riv-stories.json"]) for (const c of read(feed).claims) claims.set(c.claim_id, c.claim);
let best = Infinity;
let verified = 0;
for (let i = 0; i < 5; i++) {
  const start = performance.now();
  verified = 0;
  for (const claim of claims.values()) verified += verifyClaim(claim, evidence, events, exportData.display_names).status === "verified" ? 1 : 0;
  best = Math.min(best, performance.now() - start);
}
console.log(JSON.stringify({ node: process.version, events: events.length, load_ms: Math.round(expanded), claims: claims.size, verified, verify_all_ms: Math.round(best * 10) / 10 }, null, 1));
