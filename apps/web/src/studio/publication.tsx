/**
 * Publication journey for D-031, with a working demo approval.
 *
 * Once every kept sentence is verified (or marked as opinion) a demo producer can approve the
 * exact version: the approval binds SHA-256 digests of the content and of the verified claims,
 * so any later edit withdraws it. Approved content then goes to the chosen destinations of a
 * demo channel, each delivery keyed by a publication id derived from the digest, so a retry
 * never sends anything twice. Everything stays in this browser: there is no sign-in, no server
 * command and no real destination, and the page says so.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Icon, type IconName } from "./icons";
import { loadD031 } from "./composer";
import { d031Sentences, draftEligibility, findClaim, verdict } from "./data";
import { ProducerDecisionDialog } from "../workforce/decision-dialog";
import {
  lockProducerDecision,
  type LockedProducerDecision,
  type ProducerDecisionSnapshot,
} from "../workforce/decision-confirmation";

const APPROVAL_KEY = "md.d031.approval";
const REPLAY_ID = "replay-nbr-riv-canonical";

type DestinationId = "match-centre" | "broadcast" | "social" | "partner";
const DESTINATIONS: { id: DestinationId; name: string; detail: string; icon: IconName }[] = [
  { id: "match-centre", name: "Match Centre", detail: "Web and app story card", icon: "monitor" },
  { id: "broadcast", name: "Broadcast graphics", detail: "On-air lower-third and caption", icon: "pulse" },
  { id: "social", name: "Social channel", detail: "Scheduled post with evidence link", icon: "phone" },
  { id: "partner", name: "Data partner feed", detail: "Claim, evidence digest and version", icon: "grid" },
];

type Delivery = { id: DestinationId; publication_id: string; status: "sent" | "failed"; attempts: number; at: string };
type Approval = {
  content_digest: string;
  evidence_digest: string;
  reason: string;
  approved_at: string;
  by: string;
  deliveries: Delivery[];
};
type AuditEntry = { at: string; what: string };
type Stored = { approval: Approval | null; audit: AuditEntry[] };

async function sha256(text: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

function readStored(): Stored {
  try {
    const raw = window.localStorage.getItem(APPROVAL_KEY);
    return raw ? { approval: null, audit: [], ...(JSON.parse(raw) as Partial<Stored>) } : { approval: null, audit: [] };
  } catch { return { approval: null, audit: [] }; }
}

function writeStored(value: Stored) {
  try { window.localStorage.setItem(APPROVAL_KEY, JSON.stringify(value)); } catch { /* demo state stays in memory */ }
}

const now = () => new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const short = (digest: string) => `${digest.slice(0, 12)}…`;

/** The draft as it stands: the text a reader would see, and the claims it rests on. */
function currentDraft() {
  const doc = loadD031();
  const kept = d031Sentences.filter((s) => (doc.states[s.claimId] ?? "keep") !== "removed");
  const text = [doc.headline, ...kept.map((s) => (doc.states[s.claimId] === "opinion" ? s.opinion ?? s.text : doc.texts[s.claimId] ?? s.text))].join("\n");
  const evidence = kept
    .filter((s) => doc.states[s.claimId] !== "opinion")
    .map((s) => { const claim = findClaim(s.claimId); return `${s.claimId}:${claim ? verdict(claim) : "missing"}`; })
    .join("\n");
  const elig = draftEligibility(doc.states, doc.failedEdits);
  return { doc, text, evidence, eligible: elig.eligible, blocking: elig.blocking };
}

export function PublicationBody() {
  const [draft, setDraft] = useState<ReturnType<typeof currentDraft> | null>(null);
  const [digests, setDigests] = useState<{ content: string; evidence: string } | null>(null);
  const [stored, setStored] = useState<Stored>({ approval: null, audit: [] });
  const [decision, setDecision] = useState<LockedProducerDecision | null>(null);
  const [chosen, setChosen] = useState<Record<DestinationId, boolean>>({ "match-centre": true, broadcast: true, social: true, partner: true });
  const [sending, setSending] = useState(false);

  useEffect(() => {
    const d = currentDraft();
    setDraft(d);
    setStored(readStored());
    void Promise.all([sha256(d.text), sha256(d.evidence)]).then(([content, evidence]) => setDigests({ content, evidence }));
  }, []);

  const update = useCallback((next: Stored) => { setStored(next); writeStored(next); }, []);
  const approval = stored.approval;
  // An approval is for one exact version: any change to the text or its checks withdraws it.
  const current = Boolean(approval && digests && approval.content_digest === digests.content && approval.evidence_digest === digests.evidence);
  const withdrawn = Boolean(approval && digests && !current);
  const eligible = draft?.eligible ?? false;
  const delivered = approval?.deliveries ?? [];
  const sent = (id: DestinationId) => delivered.find((d) => d.id === id && d.status === "sent");
  const published = current && delivered.length > 0 && delivered.every((d) => d.status === "sent");

  const snapshot: ProducerDecisionSnapshot | null = useMemo(() => digests && eligible ? {
    session_id: "DEMO_PRODUCER", output_id: "D-031", generation: 1, review_status: "ready_for_decision",
    binding: { item_id: "D-031", item_version: 4, replay_id: REPLAY_ID, content_digest: digests.content, evidence_digest: digests.evidence, language: "en", persona: "analyst" },
  } : null, [digests, eligible]);

  const send = async (only?: DestinationId) => {
    if (!approval || !current || !digests) return;
    setSending(true);
    let deliveries = [...approval.deliveries];
    const audit = [...stored.audit];
    for (const dest of DESTINATIONS) {
      if (only ? dest.id !== only : !chosen[dest.id] || sent(dest.id)) continue;
      // The publication id comes from the approved digest and the destination: a retry reuses it.
      const publication_id = `PUB-${(await sha256(`${digests.content}:${dest.id}`)).slice(0, 10)}`;
      const previous = deliveries.find((d) => d.id === dest.id);
      const attempts = (previous?.attempts ?? 0) + 1;
      await new Promise((r) => setTimeout(r, 350));
      // The demo social channel times out on its first attempt, to show a safe retry.
      const status = dest.id === "social" && attempts === 1 ? "failed" : "sent";
      deliveries = [...deliveries.filter((d) => d.id !== dest.id), { id: dest.id, publication_id, status, attempts, at: now() }];
      audit.push({ at: now(), what: status === "sent" ? `${dest.name}: sent ${publication_id} (attempt ${attempts}), digest ${short(digests.content)}` : `${dest.name}: timed out (attempt ${attempts}); approval kept, nothing else re-sent` });
    }
    update({ approval: { ...approval, deliveries }, audit });
    setSending(false);
  };

  const steps = [
    { label: "Ready", detail: "Draft written", state: "done" },
    { label: "Eligible", detail: eligible ? "All claims checked" : `${draft?.blocking.length ?? 2} claims block it`, state: eligible ? "done" : "current" },
    { label: "Demo approval", detail: current ? "Approved in this browser" : "Not a real producer sign-off", state: current ? "done" : eligible ? "current" : "todo" },
    { label: "Demo channels", detail: delivered.length && current ? `${delivered.filter((d) => d.status === "sent").length} of ${delivered.length} simulated` : "Choose pretend channels", state: published ? "done" : current ? "current" : "todo" },
    { label: "Demo sent", detail: published ? "Confirmed in this browser" : "Nothing sent to real users", state: published ? "done" : "todo" },
  ];

  return (
    <>
      <div className="md-banner md-banner-info" role="note">
        <span className="md-banner-icon" aria-hidden="true">i</span>
        <span><strong>Demo producer — nobody is signed in.</strong> You can try approving a sample story and sending it to pretend channels. Everything stays in this browser. No real approval, message or publication takes place.</span>
      </div>
      <section className="md-panel" aria-labelledby="md-pub-steps">
        <div className="md-panel-head"><h2 id="md-pub-steps">D-031 · where it stands</h2><span className="md-mono md-accent-soft-text">{eligible ? "v4" : "v3"}{draft?.doc.submitted ? " · submitted" : ""}</span></div>
        <ol className="md-stepper md-stepper-wide">
          {steps.map((s, i) => (
            <li key={s.label} className={s.state} aria-current={s.state === "current" ? "step" : undefined}>
              <span>{s.state === "done" ? "✓" : i + 1}</span>{s.label}<small>{s.detail}</small>
            </li>
          ))}
        </ol>
        {withdrawn && (
          <div className="md-banner md-banner-warn" role="alert">
            <span className="md-banner-icon" aria-hidden="true">!</span>
            <span><strong>Approval withdrawn.</strong> The draft changed after it was approved, so the approval no longer matches this version. Approve the new version to publish it.</span>
          </div>
        )}
        <div className="md-btn-row">
          {!eligible
            ? <Link href="/producer/compose/D-031" className="md-btn md-btn-primary">Make D-031 eligible <Icon name="arrow" size={16} /></Link>
            : current
              ? <p className="md-ok"><strong>✓ Approved in demo</strong> {approval?.approved_at} · content {short(approval!.content_digest)} · evidence {short(approval!.evidence_digest)}</p>
              : <button type="button" className="md-btn md-btn-primary" disabled={!snapshot} onClick={() => snapshot && setDecision(lockProducerDecision(snapshot, "approve"))}>Approve this version <Icon name="shield" size={16} /></button>}
        </div>
        {digests && (
          <details className="md-small md-pub-binds">
            <summary>What the approval binds</summary>
            <p className="md-muted">The exact text (headline and every kept sentence) and the verdicts of the claims behind it, as SHA-256 digests: content <code className="md-mono">{short(digests.content)}</code>, evidence <code className="md-mono">{short(digests.evidence)}</code>. Edit a sentence in the story editor and the approval is withdrawn.</p>
          </details>
        )}
      </section>

      <section className="md-panel" aria-labelledby="md-pub-dest">
        <div className="md-panel-head"><h2 id="md-pub-dest">Pretend destinations</h2><span className="md-chip md-chip-not-yet">Demo channel</span></div>
        <ul className="md-dest">
          {DESTINATIONS.map((d) => {
            const record = current ? delivered.find((x) => x.id === d.id) : undefined;
            return (
              <li key={d.id}>
                <Icon name={d.icon} size={22} />
                <span><strong>{d.name}</strong><span className="md-muted md-small">{d.detail}</span>
                  {record && <span className="md-mono md-small">{record.publication_id} · attempt {record.attempts}</span>}</span>
                {record?.status === "sent" ? <span className="md-chip md-chip-verified">✓ Sent</span>
                  : record?.status === "failed" ? <button type="button" className="md-btn md-btn-secondary md-btn-sm" disabled={sending} onClick={() => void send(d.id)}>Retry</button>
                  : <label className="md-dest-pick"><input type="checkbox" checked={chosen[d.id]} disabled={!current || sending} onChange={(e) => setChosen((c) => ({ ...c, [d.id]: e.target.checked }))} /> <span className="md-visually-hidden">Send to {d.name}</span>Send</label>}
              </li>
            );
          })}
        </ul>
        <div className="md-btn-row">
          <button type="button" className="md-btn md-btn-primary" disabled={!current || sending || published || !DESTINATIONS.some((d) => chosen[d.id] && !sent(d.id))} onClick={() => void send()}>
            {sending ? "Sending in demo…" : published ? "Sent in demo" : "Send to demo channels"}
          </button>
          {delivered.some((d) => d.status === "failed") && current && <p className="md-muted md-small" role="status">One destination timed out. The others are confirmed; retry sends only that one, with the same publication id.</p>}
        </div>
      </section>

      {published && draft && (
        <section className="md-panel" aria-labelledby="md-pub-live">
          <div className="md-panel-head"><h2 id="md-pub-live">In the demo channel</h2><span className="md-chip md-chip-verified">✓ Confirmed</span></div>
          <p className="md-story-body"><strong>{draft.doc.headline}</strong></p>
          <p className="md-story-body">{draft.text.split("\n").slice(1).join(" ")}</p>
          <p className="md-muted md-small">Every destination confirmed the same content digest {short(digests!.content)}. Synthetic match; demo channel only.</p>
        </section>
      )}

      {stored.audit.length > 0 && (
        <section className="md-panel" aria-labelledby="md-pub-audit">
          <div className="md-panel-head"><h2 id="md-pub-audit">Demo activity record</h2>
            <button type="button" className="md-btn md-btn-secondary md-btn-sm" onClick={() => update({ approval: null, audit: [] })}>Clear demo approval</button></div>
          <ol className="md-audit">
            {stored.audit.map((a, i) => <li key={i}><span className="md-mono">{a.at}</span> {a.what}</li>)}
          </ol>
        </section>
      )}

      <ProducerDecisionDialog
        intent={decision}
        current={snapshot}
        title="Approve D-031, this exact version"
        note="You are approving the text and checks shown by these digests. Demo producer: no sign-in, and publishing goes only to the demo channel in this browser."
        onDismiss={() => setDecision(null)}
        onConfirmed={(candidate) => {
          if (candidate.action !== "approve" || candidate.output_id !== "D-031" || !digests) throw new Error("Approval scope changed");
          const at = now();
          update({
            approval: { content_digest: candidate.body.binding.content_digest, evidence_digest: candidate.body.binding.evidence_digest, reason: candidate.body.reason, approved_at: at, by: "Demo producer", deliveries: [] },
            audit: [...stored.audit, { at, what: `Approved D-031 v4 (content ${short(candidate.body.binding.content_digest)}, evidence ${short(candidate.body.binding.evidence_digest)}): "${candidate.body.reason}"` }],
          });
        }}
      />
    </>
  );
}
