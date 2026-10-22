/** Publication journey (future state): where D-031 stands and how approval and publishing will work. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon, type IconName } from "./icons";
import { loadD031 } from "./composer";
import { draftEligibility } from "./data";
import { ProducerDecisionDialog } from "../workforce/decision-dialog";
import {
  lockProducerDecision,
  type LockedProducerDecision,
  type ProducerDecisionSnapshot,
} from "../workforce/decision-confirmation";

/** Static, explicitly fictional preview ONLY; not a real review or server binding. */
const DEMO_DECISION: ProducerDecisionSnapshot = {
  session_id: "DEMO_SESSION", output_id: "D-031",
  generation: 4, review_status: "ready_for_decision",
  binding: {
    item_id: "D-031", item_version: 4, replay_id: "DEMO_REPLAY",
    content_digest: "1".repeat(64), evidence_digest: "2".repeat(64),
    language: "en", persona: "analyst",
  },
};

const DESTINATIONS: { name: string; detail: string; icon: IconName }[] = [
  { name: "Match Centre", detail: "Web and app story card", icon: "monitor" },
  { name: "Broadcast graphics", detail: "On-air lower-third and caption", icon: "pulse" },
  { name: "Social channel", detail: "Scheduled post with evidence link", icon: "phone" },
  { name: "Data partner feed", detail: "Claim, evidence digest and version", icon: "grid" },
];

export function PublicationBody() {
  const [eligible, setEligible] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [decision, setDecision] = useState<LockedProducerDecision | null>(null);
  const [previewCompleted, setPreviewCompleted] = useState(false);
  useEffect(() => {
    const doc = loadD031();
    setEligible(draftEligibility(doc.states, doc.failedEdits).eligible);
    setSubmitted(doc.submitted);
  }, []);
  const steps = [
    { label: "Ready", detail: "Draft written", state: "done" },
    { label: "Eligible", detail: eligible ? "All claims checked" : "2 claims block it", state: eligible ? "done" : "current" },
    { label: "Approve", detail: "Producer sign-off · Planned", state: eligible ? "current" : "todo" },
    { label: "Destinations", detail: "Choose channels · Planned", state: "todo" },
    { label: "Published", detail: "Live and confirmed · Planned", state: "todo" },
  ];
  return (
    <>
      <section className="md-panel" aria-labelledby="md-pub-steps">
        <div className="md-panel-head"><h2 id="md-pub-steps">D-031 · where it stands</h2><span className="md-mono md-accent-soft-text">{eligible ? "v4" : "v3"}{submitted ? " · submitted" : ""}</span></div>
        <ol className="md-stepper md-stepper-wide">
          {steps.map((s, i) => (
            <li key={s.label} className={s.state} aria-current={s.state === "current" ? "step" : undefined}>
              <span>{s.state === "done" ? "✓" : i + 1}</span>{s.label}<small>{s.detail}</small>
            </li>
          ))}
        </ol>
        <div className="md-btn-row">
          {eligible
            ? <p className="md-locked"><Icon name="lock" size={14} /> Approve · Planned: a signed-in producer approves the exact version</p>
            : <Link href="/producer/compose/D-031" className="md-btn md-btn-primary">Make D-031 eligible <Icon name="arrow" size={16} /></Link>}
          <button type="button" className="md-btn md-btn-secondary"
            onClick={() => {
              setPreviewCompleted(false);
              setDecision(lockProducerDecision(DEMO_DECISION, "approve"));
            }}>
            Preview producer confirmation (demo)
          </button>
        </div>
        <p className="md-muted md-small">
          Preview only: the confirmation uses fictional hashes and a sample ready
          version, independent of this draft&apos;s eligibility. No approval or
          publication command is sent.
        </p>
        {previewCompleted && (
          <div className="md-banner md-banner-info" role="status">
            <span className="md-banner-icon" aria-hidden="true">i</span>
            <strong>Preview acknowledged</strong>
            <span>No producer command was sent and nothing was approved.</span>
          </div>
        )}
      </section>
      <section className="md-panel" aria-labelledby="md-pub-dest">
        <h2 id="md-pub-dest">Destinations</h2>
        <ul className="md-dest">
          {DESTINATIONS.map((d) => (
            <li key={d.name}><Icon name={d.icon} size={22} /><span><strong>{d.name}</strong><span className="md-muted md-small">{d.detail}</span></span><span className="md-chip md-chip-not-yet">Planned</span></li>
          ))}
        </ul>
      </section>
      <div className="md-split">
        <section className="md-panel md-split-main md-path md-path-ok" aria-labelledby="md-pub-ok">
          <span className="md-eyebrow">Illustration</span>
          <h2 id="md-pub-ok">Success path</h2>
          <p className="md-muted">Approved once, sent to every chosen destination, each confirmed back with the same evidence digest.</p>
          <ol className="md-path-steps"><li>Ready</li><li>Eligible</li><li>Approved</li><li>Sent</li><li>Confirmed</li></ol>
        </section>
        <section className="md-panel md-split-side md-path md-path-fail" aria-labelledby="md-pub-fail">
          <span className="md-eyebrow">Illustration</span>
          <h2 id="md-pub-fail">If a destination fails</h2>
          <p className="md-muted">The others still publish. The failed one shows the reason, keeps the approval, and offers a safe retry. Nothing is sent twice.</p>
          <ol className="md-path-steps"><li>Approved</li><li className="bad">Social channel timed out</li><li>Retry</li></ol>
        </section>
      </div>
      <ProducerDecisionDialog
        intent={decision}
        current={DEMO_DECISION}
        onDismiss={() => setDecision(null)}
        onConfirmed={(candidate) => {
          // Demo callback intentionally NEVER calls the BFF or stores approval.
          if (candidate.action !== "approve" || candidate.output_id !== "D-031") {
            throw new Error("Demo scope changed");
          }
          setPreviewCompleted(true);
        }}
      />
    </>
  );
}
