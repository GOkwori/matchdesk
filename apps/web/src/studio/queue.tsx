/** Producer review queue: draft eligibility reflects composer changes saved on this device. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { VerdictChip } from "./ui";
import { TourStep } from "./shell";
import { loadD031 } from "./composer";
import { draftEligibility, drafts, findClaim, verdictLabel, verdict } from "./data";

export function QueueBody() {
  const [states, setStates] = useState<Record<string, "keep" | "opinion" | "removed">>({});
  useEffect(() => { setStates(loadD031().states); }, []);
  const d031 = draftEligibility(states);
  const fixed = Object.keys(states).length > 0;

  return (
    <div className="md-split">
      <section className="md-panel md-split-main" aria-labelledby="md-q-title">
        <div className="md-panel-head"><h2 id="md-q-title">Drafts awaiting review</h2><span className="md-muted">2 drafts</span></div>
        <ul className="md-queue">
          <li className="md-queue-item md-queue-active">
            <span className="md-mono md-accent-soft-text">D-031 {fixed ? "v4" : "v3"}</span>
            <span className="md-queue-title"><strong>{drafts[0].title}</strong><span>Priya Shah · 4 claims</span></span>
            <VerdictChip pill verdict={d031.eligible ? "verified" : "failed"} label={d031.eligible ? "Eligible" : "Not eligible"} />
            <Link href="/producer/compose/D-031" className="md-btn md-btn-primary md-btn-sm">{d031.eligible ? "Review" : "Fix in composer"}</Link>
          </li>
          <li className="md-queue-item">
            <span className="md-mono md-accent-soft-text">D-029 v2</span>
            <span className="md-queue-title"><strong>{drafts[1].title}</strong><span>Priya Shah · 4 of 4 claims verified</span></span>
            <VerdictChip pill verdict="verified" label="Eligible · not approved" />
            <span className="md-locked"><Icon name="lock" size={14} /> Approve · Planned</span>
          </li>
        </ul>
      </section>
      <aside className="md-split-side" aria-label="D-031 inspection">
        <section className="md-panel" aria-labelledby="md-insp-title">
          <span className="md-mono md-accent-soft-text">D-031 {fixed ? "v4" : "v3"}</span>
          <h2 id="md-insp-title" className="md-sel-title">{drafts[0].title}</h2>
          <ul className="md-check-list">
            {["CL-0213", "CL-0214", "CL-0215", "CL-0216"].map((id) => {
              const claim = findClaim(id)!;
              const state = states[id] ?? "keep";
              const v = verdict(claim);
              return (
                <li key={id}>
                  <span><span className="md-mono">{id}</span> {claim.short}</span>
                  {state === "removed" ? <span className="md-muted">Removed</span> : state === "opinion" ? <span className="md-muted">Opinion</span> : <VerdictChip verdict={v} label={verdictLabel[v]} />}
                </li>
              );
            })}
          </ul>
          {!d031.eligible && <div className="md-banner md-banner-warn md-banner-inline"><span className="md-banner-icon" aria-hidden="true">!</span><span><strong>Approval blocked.</strong> {d031.blocking.join(" and ")} must be resolved first.</span></div>}
          <Link href="/producer/compose/D-031" className="md-btn md-btn-primary">Open in composer <Icon name="arrow" size={16} /></Link>
        </section>
        <TourStep step={4} />
      </aside>
    </div>
  );
}
