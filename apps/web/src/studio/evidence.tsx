/** Evidence proof panel for the possession claim, including the forged-value rejection demo. */
"use client";

import { useEffect, useState } from "react";
import { VerdictChip } from "./ui";
import { TourStep } from "./shell";
import { eventCountText, matchExport, possession, possessionSeries, possessionShare, serverClaim, toVerdict } from "./data";
import { expandLog, roundHalfUp, verifyClaim, type CompactLog, type Result } from "./verifier";

type Recheck = { state: "loading" } | { state: "done"; real: Result; forged: Result; agrees: boolean } | { state: "error" };

/** Re-run the TypeScript port of the backend verifier on the full event log, in this browser. */
function useBrowserRecheck(): Recheck {
  const [recheck, setRecheck] = useState<Recheck>({ state: "loading" });
  useEffect(() => {
    let live = true;
    import("./generated/nbr-riv-events.json").then(
      (module) => {
        const events = expandLog(module.default as unknown as CompactLog);
        const evidence = { match_id: matchExport.match_id, event_ids: events.map((e) => e.event_id), window: { from_ms: 0, to_ms: matchExport.replay_end_ms } };
        const names = matchExport.display_names;
        const real = verifyClaim(serverClaim("CL-0214").claim, evidence, events, names);
        const forged = verifyClaim(serverClaim("CL-0214", true).claim, evidence, events, names);
        const same = (browser: Result, server: Omit<Result, "claim_id">) =>
          browser.status === server.status && browser.reason === server.reason && browser.observed === server.observed && browser.expected === server.expected;
        const agrees = same(real, serverClaim("CL-0214").result) && same(forged, serverClaim("CL-0214", true).result);
        if (live) setRecheck({ state: "done", real, forged, agrees });
      },
      () => { if (live) setRecheck({ state: "error" }); },
    );
    return () => { live = false; };
  }, []);
  return recheck;
}

/** Rolling possession chart with a highlighted Riverside spell and a table alternative. */
function PossessionChart() {
  const x = (m: number) => 40 + (m / 67) * 540;
  const y = (v: number) => 130 - ((v - 25) / 50) * 110;
  const lowest = possessionSeries.reduce((m, p) => (p.share < m.share ? p : m));
  const summary = `Northbridge possession share by five-minute window. Lowest ${lowest.share} percent from minute ${lowest.minute}; whole-match share ${possessionShare().toFixed(1)} percent.`;
  const line = possessionSeries.map((p, i) => `${i ? "L" : "M"}${x(p.minute).toFixed(1)} ${y(p.share).toFixed(1)}`).join(" ");
  return (
    <figure className="md-chart">
      <figcaption>Northbridge possession share, rolling 5 minutes</figcaption>
      <svg viewBox="0 0 600 150" role="img" aria-label={summary}>
        <g stroke="var(--md-line)" strokeWidth="1">{[75, 50, 25].map((v) => <path key={v} d={`M40 ${y(v)}H590`} />)}</g>
        <g fill="var(--md-subtle)" fontFamily="var(--md-font-mono)" fontSize="10">
          {[75, 50, 25].map((v) => <text key={v} x="4" y={y(v) + 4}>{v}%</text>)}
          {[0, 30, 45, 67].map((m) => <text key={m} x={x(m) - 6} y="146">{m}′</text>)}
        </g>
        <rect x={x(30)} y="14" width={x(45) - x(30)} height="118" fill="rgba(246,196,107,0.10)" />
        <text x={x(30) + 4} y="28" fill="var(--md-warn)" fontSize="11">Riverside spell · CL-0215</text>
        <path d={line} fill="none" stroke="var(--md-accent)" strokeWidth="2.5" strokeLinejoin="round" />
        <path d={`M40 ${y(possessionShare())}H590`} stroke="var(--md-accent-soft)" strokeDasharray="4 4" />
        <text x="586" y="24" textAnchor="end" fill="var(--md-accent-soft)" fontFamily="var(--md-font-mono)" fontSize="11">avg {possessionShare().toFixed(1)}%</text>
      </svg>
      <details className="md-table-toggle">
        <summary>View as table</summary>
        <table>
          <caption className="md-visually-hidden">Northbridge possession share by minute</caption>
          <thead><tr><th scope="col">Minute</th><th scope="col">Northbridge share</th></tr></thead>
          <tbody>{possessionSeries.map((p) => <tr key={p.minute}><th scope="row">{p.minute}′</th><td>{p.share}%</td></tr>)}</tbody>
        </table>
      </details>
    </figure>
  );
}

export function PossessionProof() {
  const [forged, setForged] = useState(false);
  const recheck = useBrowserRecheck();
  const server = serverClaim("CL-0214", forged);
  const assertion = server.claim.assertion!;
  const claimed = Math.round(assertion.value * 100);
  const result = toVerdict(server.result.status);
  const observed = possessionShare().toFixed(2);
  const rounded = roundHalfUp(server.result.observed ?? 0, assertion.decimals ?? 2);
  const roundedPct = `${Math.round(Number(rounded) * 100)}%`;
  const pass = result === "verified";
  return (
    <>
      <div className="md-proof-head">
        <h2>Northbridge have had {claimed}% possession</h2>
        <VerdictChip verdict={result} label={pass ? "Verified" : "Failed · needs revision"} />
      </div>
      <ol className="md-chain" aria-label="Proof chain">
        <li><span className="md-step-num">1</span><strong>Claim</strong><span>{claimed}% for Northbridge, whole match to 67:12</span></li>
        <li><span className="md-step-num">2</span><strong>Metric</strong><span>Possession share of in-play time</span></li>
        <li><span className="md-step-num">3</span><strong>Source events</strong><span>{eventCountText} events read from the log</span></li>
        <li className={pass ? "md-chain-pass" : "md-chain-fail"}><span className="md-step-num">{pass ? "✓" : "✕"}</span><strong>Result</strong><span>Observed {observed}% · {pass ? `rounds to ${claimed}%` : `rounds to ${roundedPct}, not ${claimed}%`}</span></li>
      </ol>
      <PossessionChart />
      <pre className="md-calc" aria-label="Calculation">{`possession(NBR) = in_play_time(NBR) / in_play_time(all)
               = ${possession.homeSeconds.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s / ${possession.totalSeconds.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s
               = ${observed}%  →  ${roundedPct} at whole-percent precision
claimed ${claimed}%  ·  `}<span className={pass ? "md-pass" : "md-fail"}>{pass ? "PASS" : "FAIL"}</span></pre>
      <p className="md-recheck" role="status" aria-live="polite">
        {recheck.state === "loading" && <>Re-checking in your browser from {eventCountText} events…</>}
        {recheck.state === "done" && recheck.agrees && <><span className="md-pass" aria-hidden="true">✓</span> Checked twice: by the server, and again in your browser from {eventCountText} events. Both give {observed}%.</>}
        {recheck.state === "done" && !recheck.agrees && <><span className="md-fail" aria-hidden="true">✕</span> The browser re-check disagrees with the server. Treat this claim as unverified.</>}
        {recheck.state === "error" && <>The browser re-check could not load the event log; the server’s verdict stands.</>}
      </p>
      <div className="md-forge">
        <span><strong>Try a forged value</strong><span className="md-muted">Change the claim to 59% and watch the verifier recompute it from the events and reject it.</span></span>
        <button type="button" className="md-btn md-btn-secondary" aria-pressed={forged} onClick={() => setForged((f) => !f)}>{forged ? "Restore 58%" : "Claim 59% instead"}</button>
      </div>
      <div role="status" aria-live="polite">
        {forged && <div className="md-banner md-banner-error"><span className="md-banner-icon" aria-hidden="true">!</span><strong>Rejected</strong><span>The log gives {observed}%, which rounds to {roundedPct}, not {claimed}%. A forged number can’t pass verification, so it can’t reach approval.</span></div>}
      </div>
      <TourStep step={3} />
    </>
  );
}
