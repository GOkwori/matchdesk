/** Story & Commentary Composer for D-031 with live, deterministic re-verification. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { GoalPitch, ScoreStrip, VerdictChip } from "./ui";
import { TourStep } from "./shell";
import { d031Sentences, draftEligibility, eventCountText, findClaim, statistics, verdict, type SentenceState } from "./data";

const STORE_KEY = "md.d031";

type Saved = { states: Record<string, SentenceState>; headline: string; submitted: boolean };
const initial: Saved = { states: {}, headline: "Okafor double restores Northbridge lead", submitted: false };

/** Shared with the review queue so a fixed draft shows as eligible there too. */
export function loadD031(): Saved {
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    return raw ? { ...initial, ...(JSON.parse(raw) as Partial<Saved>) } : initial;
  } catch { return initial; }
}

function save(value: Saved) {
  try { window.localStorage.setItem(STORE_KEY, JSON.stringify(value)); } catch { /* demo state stays in memory */ }
}

export function ComposerBody() {
  const [doc, setDoc] = useState<Saved>(initial);
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => { setDoc(loadD031()); setHydrated(true); }, []);
  useEffect(() => { if (hydrated) save(doc); }, [doc, hydrated]);

  const elig = draftEligibility(doc.states);
  const edited = Object.keys(doc.states).length > 0;
  const setState = (claimId: string, state: SentenceState) =>
    setDoc((d) => ({ ...d, submitted: false, states: { ...d.states, [claimId]: state } }));
  const reset = () => setDoc(initial);

  return (
    <>
      <div aria-live="polite" role="status">
        {doc.submitted
          ? <div className="md-banner md-banner-success"><span className="md-banner-icon" aria-hidden="true">✓</span><strong>Submitted</strong><span>D-031 v4 is with the producer for review. Approval stays with a human.</span></div>
          : edited && elig.eligible
            ? <div className="md-banner md-banner-success"><span className="md-banner-icon" aria-hidden="true">✓</span><strong>Re-verified</strong><span>D-031 v4 is now eligible. Every remaining statement is verified or marked as opinion.</span></div>
            : <div className="md-banner md-banner-warn"><span className="md-banner-icon" aria-hidden="true">!</span><strong>Re-verification required</strong><span>{elig.blocking.length} claim{elig.blocking.length === 1 ? "" : "s"} block approval. Resolve them below; the draft re-verifies as you edit.</span></div>}
      </div>

      <div className="md-composer-meta">
        <ScoreStrip crumbs={[{ label: "Producer Tools", href: "/producer/queue" }, { label: "Composer · D-031" }]} />
        <span className="md-save"><span className="md-dot md-dot-success" aria-hidden="true" />Saved on this device</span>
      </div>

      <div className="md-split">
        <div className="md-split-main md-stack">
          <label className="md-field">
            <span>Headline <span className="md-muted">(required)</span></span>
            <span className="md-input-wrap">
              <input value={doc.headline} maxLength={120} onChange={(e) => setDoc((d) => ({ ...d, headline: e.target.value }))} />
              <span className="md-count" aria-hidden="true">{doc.headline.length}/120</span>
            </span>
          </label>

          <section className="md-panel" aria-labelledby="md-narr-title">
            <div className="md-panel-head"><h2 id="md-narr-title">Commentary narrative</h2><span className="md-muted">Each statement is linked to a claim</span></div>
            <p className="md-narrative">
              {d031Sentences.map((s) => {
                const state = doc.states[s.claimId] ?? "keep";
                const claim = findClaim(s.claimId)!;
                const v = verdict(claim);
                const cls = state === "removed" ? "md-hl-removed" : state === "opinion" ? "md-hl-opinion" : `md-hl-${v}`;
                return <span key={s.claimId}><span className={`md-hl ${cls}`}>{state === "opinion" && s.opinion ? s.opinion : s.text}</span>{state === "removed" && <span className="md-visually-hidden"> (removed)</span>} </span>;
              })}
            </p>
            <ul className="md-claim-cards" aria-label="Claims in this draft">
              {d031Sentences.map((s) => {
                const state = doc.states[s.claimId] ?? "keep";
                const claim = findClaim(s.claimId)!;
                const v = verdict(claim);
                const status = state === "removed" ? "Removed" : state === "opinion" ? "Marked as opinion" : v === "verified" ? "Verified" : v === "pending" ? "Interpretation · needs a decision" : "No supporting evidence";
                const tone = state === "removed" ? "removed" : state === "opinion" ? "opinion" : v;
                return (
                  <li key={s.claimId} className={`md-claim-card md-cc-${tone}`}>
                    <span className="md-cc-head"><span className="md-mono">{s.claimId}</span><span className="md-cc-status">{status}</span></span>
                    <span className="md-cc-text">{claim.short}</span>
                    <span className="md-cc-actions">
                      <Link href={`/match/nbr-riv/evidence/${s.claimId}`} className="md-link">Evidence</Link>
                      {v === "pending" && state === "keep" && <button type="button" className="md-mini-btn" onClick={() => setState(s.claimId, "opinion")}>Mark as opinion</button>}
                      {v !== "verified" && state !== "removed" && <button type="button" className="md-mini-btn" onClick={() => setState(s.claimId, "removed")}>Remove sentence</button>}
                      {state !== "keep" && <button type="button" className="md-mini-btn" onClick={() => setState(s.claimId, "keep")}>Undo</button>}
                    </span>
                  </li>
                );
              })}
            </ul>
            <TourStep step={5} />
          </section>

          <section className="md-panel" aria-labelledby="md-ev-title">
            <div className="md-panel-head"><h2 id="md-ev-title">Linked evidence (3)</h2></div>
            <ul className="md-evidence-list">
              <li><GoalPitch variant="header" label="Goal E-1366: header inside the six-yard box after a corner from the right" /><span className="md-ev-text"><strong>Goal · Okafor header</strong><span>E-1366 · 58:17 · after corner E-1359</span></span><VerdictChip verdict="verified" /><Link className="md-btn md-btn-secondary md-btn-sm" href="/match/nbr-riv/moments?moment=M-05">View</Link></li>
              <li><svg viewBox="0 0 96 58" className="md-pitch" role="img" aria-label="Possession trend, Northbridge averaging 58 percent"><rect width="96" height="58" fill="var(--md-canvas)" /><path d="M4 40 16 36 28 38 40 30 52 32 64 24 76 26 92 18" fill="none" stroke="var(--md-accent)" strokeWidth="2" /></svg><span className="md-ev-text"><strong>Possession · whole match</strong><span>{statistics[0].home}% vs {statistics[0].away}% · computed from {eventCountText} events</span></span><VerdictChip verdict="verified" /><Link className="md-btn md-btn-secondary md-btn-sm" href="/match/nbr-riv/evidence/CL-0214">View</Link></li>
              <li><GoalPitch variant="right-foot" label="Goal E-0688: right-footed finish from the edge of the box" /><span className="md-ev-text"><strong>Goal · Okafor right foot</strong><span>E-0688 · 34:18 · open play</span></span><VerdictChip verdict="verified" /><Link className="md-btn md-btn-secondary md-btn-sm" href="/match/nbr-riv/moments?moment=M-02">View</Link></li>
            </ul>
          </section>
        </div>

        <div className="md-split-side md-stack">
          <section className="md-panel" aria-labelledby="md-vc-title">
            <h2 id="md-vc-title">Version compare</h2>
            <p className="md-muted md-small"><strong>v3</strong> · 11 Oct 2026, 18:32 &nbsp;vs&nbsp; <strong>v4</strong> · current</p>
            {edited ? (
              <ul className="md-diff">
                {d031Sentences.filter((s) => doc.states[s.claimId] && doc.states[s.claimId] !== "keep").map((s) => (
                  <li key={s.claimId}>
                    {doc.states[s.claimId] === "removed"
                      ? <><span className="md-diff-tag md-diff-del">Removed</span><del>{s.text}</del></>
                      : <><span className="md-diff-tag md-diff-add">Changed</span><span><del>{s.text}</del> <ins>{s.opinion}</ins></span></>}
                  </li>
                ))}
              </ul>
            ) : <p className="md-empty">No changes from v3 yet.</p>}
          </section>

          <section className={`md-panel md-elig ${elig.eligible ? "md-elig-ok" : "md-elig-no"}`} aria-labelledby="md-elig-title">
            <div className="md-panel-head"><h2 id="md-elig-title">Eligibility</h2><VerdictChip pill verdict={elig.eligible ? "verified" : "failed"} label={elig.eligible ? "Eligible" : "Not eligible"} /></div>
            <p className="md-muted">{elig.verified} verified · {elig.opinions} marked as opinion · {elig.blocking.length} blocking{elig.blocking.length ? ` (${elig.blocking.join(", ")})` : ""}.</p>
          </section>

          <section className="md-panel" aria-labelledby="md-pv-title">
            <h2 id="md-pv-title">Preview <span className="md-muted md-small">(Match Centre style)</span></h2>
            <div className="md-preview">
              <svg viewBox="0 0 320 110" role="img" aria-label="Illustrated preview: corner delivery to a header" className="md-preview-art"><g fill="none" stroke="var(--md-pitch-line)"><path d="M200 0v110" /><rect x="250" y="20" width="70" height="70" /><rect x="292" y="40" width="28" height="30" /></g><path d="M318 4C290 20 285 38 296 54" stroke="var(--md-accent-soft)" strokeWidth="2" strokeDasharray="5 4" fill="none" /><circle cx="296" cy="54" r="7" fill="var(--md-home)" stroke="var(--md-text)" strokeWidth="2" /><text x="16" y="26" fontFamily="var(--md-font-mono)" fontSize="13" fill="var(--md-accent-soft)">58′ · 2–1</text></svg>
              <div className="md-preview-text"><strong>{doc.headline || "Untitled draft"}</strong><span>{d031Sentences.filter((s) => (doc.states[s.claimId] ?? "keep") !== "removed").map((s) => (doc.states[s.claimId] === "opinion" ? s.opinion : s.text)).join(" ")}</span></div>
            </div>
          </section>

          <div className="md-btn-row md-actions-end">
            <button type="button" className="md-btn md-btn-secondary" onClick={reset} disabled={!edited && !doc.submitted}>Reset to v3</button>
            <button type="button" className="md-btn md-btn-primary" disabled={!elig.eligible || doc.submitted} aria-describedby="md-submit-help" onClick={() => setDoc((d) => ({ ...d, submitted: true }))}>
              {doc.submitted ? "Submitted" : "Submit for review"} <Icon name="arrow" size={16} />
            </button>
          </div>
          <p id="md-submit-help" className="md-muted md-small">{elig.eligible ? "A producer approves or rejects it next. Approval and publishing stay with a human." : "Resolve the blocking claims to submit."}</p>
          <div className="md-btn-row"><p className="md-locked"><Icon name="lock" size={14} /> Approve · Planned</p><Link href="/producer/publish/D-031" className="md-link">See the publication journey <Icon name="arrow" size={14} /></Link></div>
        </div>
      </div>
    </>
  );
}
