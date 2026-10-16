/** Evidence & Verification (locked screen 02): three panels — claims, proof, impact. */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { PossessionProof } from "../../../../../../../studio/evidence";
import { Icon } from "../../../../../../../studio/icons";
import { TopActions } from "../../../../../../../studio/shell";
import { GoalPitch, NextStep, PageHead, ScoreStrip, VerdictChip } from "../../../../../../../studio/ui";
import { claims, findClaim, verdict, verdictLabel } from "../../../../../../../studio/data";

export function generateStaticParams() {
  return claims.map((c) => ({ claimId: c.id }));
}
export const dynamicParams = false;

export async function generateMetadata({ params }: { params: Promise<{ claimId: string }> }): Promise<Metadata> {
  const { claimId } = await params;
  const claim = findClaim(claimId);
  return { title: claim ? `${claim.id} · Evidence` : "Evidence", robots: { index: false } };
}

/** Proof content for the non-statistical claims; CL-0214 uses the interactive panel. */
function StaticProof({ id }: { id: string }) {
  const claim = findClaim(id)!;
  const v = verdict(claim);
  if (id === "CL-0213") {
    return (
      <>
        <div className="md-proof-head"><h2>{claim.text}</h2><VerdictChip verdict={v} /></div>
        <ol className="md-chain" aria-label="Proof chain">
          <li><span className="md-step-num">1</span><strong>Claim</strong><span>Both Northbridge goals were scored by Okafor</span></li>
          <li><span className="md-step-num">2</span><strong>Rule</strong><span>Every Northbridge goal event names Okafor as scorer</span></li>
          <li><span className="md-step-num">3</span><strong>Source events</strong><span className="md-mono">E-0688 · E-1366</span></li>
          <li className="md-chain-pass"><span className="md-step-num">✓</span><strong>Result</strong><span>2 of 2 goals match</span></li>
        </ol>
        <div className="md-twin-pitch">
          <figure><GoalPitch variant="right-foot" label="E-0688 at 34:18: right-footed finish from the edge of the box" /><figcaption>E-0688 · 34:18 · right foot</figcaption></figure>
          <figure><GoalPitch variant="header" label="E-1366 at 58:17: header after a corner from the right" /><figcaption>E-1366 · 58:17 · header</figcaption></figure>
        </div>
        <pre className="md-calc">{`goals(team = NBR)            = [E-0688, E-1366]
scorer(E-0688), scorer(E-1366) = Okafor, Okafor   ·   `}<span className="md-pass">PASS</span></pre>
      </>
    );
  }
  const pending = id === "CL-0215";
  return (
    <>
      <div className="md-proof-head"><h2>{claim.text}</h2><VerdictChip verdict={v} /></div>
      <ol className="md-chain" aria-label="Proof chain">
        <li><span className="md-step-num">1</span><strong>Claim</strong><span>{pending ? "An interpretation of momentum" : "A season-level record"}</span></li>
        <li><span className="md-step-num">2</span><strong>Rule</strong><span>{pending ? "Interpretations are not facts; a producer must label or remove them" : "Needs season history"}</span></li>
        <li><span className="md-step-num">3</span><strong>Source events</strong><span>{pending ? "Possession dips 30–45′ (see CL-0214 chart)" : "None: the log covers this match only"}</span></li>
        <li className={pending ? "md-chain-warn" : "md-chain-fail"}><span className="md-step-num">{pending ? "!" : "✕"}</span><strong>Result</strong><span>{pending ? "Needs a producer decision" : "Can’t be verified"}</span></li>
      </ol>
      <div className={`md-banner ${pending ? "md-banner-warn" : "md-banner-error"} md-banner-inline`}>
        <span className="md-banner-icon" aria-hidden="true">!</span>
        <span>{pending ? "Mark it as opinion in the composer, or remove it, before D-031 can be approved." : "Remove this sentence in the composer. MatchDesk never publishes a claim it can’t check."}</span>
      </div>
    </>
  );
}

export default async function EvidencePage({ params }: { params: Promise<{ claimId: string }> }) {
  const { claimId } = await params;
  const claim = findClaim(claimId);
  if (!claim) notFound();
  return (
    <div className="md-page">
      <ScoreStrip crumbs={[{ label: "Moments", href: "/match/nbr-riv/moments?moment=M-05" }, { label: "M-05 goal", href: "/match/nbr-riv/moments?moment=M-05" }, { label: "Evidence" }]} />
      <PageHead title="Evidence & Verification" sub="Every claim is recalculated from the event log. Pick a claim to see its proof."><TopActions /></PageHead>
      <div className="md-three">
        <nav className="md-panel md-claims" aria-labelledby="md-claims-title">
          <div className="md-panel-head"><h2 id="md-claims-title">Claims · D-031</h2><span className="md-muted">4</span></div>
          <ul>
            {claims.map((c) => {
              const v = verdict(c);
              const active = c.id === claim.id;
              return (
                <li key={c.id}>
                  <Link href={`/match/nbr-riv/evidence/${c.id}`} aria-current={active ? "page" : undefined} className={`md-claim-link${active ? " md-claim-active" : ""}`}>
                    <span className="md-claim-row"><span className="md-mono md-accent-soft-text">{c.id}</span><span className={`md-claim-status md-claim-${v}`}>{v === "verified" ? "✓" : v === "pending" ? "!" : "✕"} {verdictLabel[v]}</span></span>
                    <span>{c.text}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <section className="md-panel md-proof" aria-label={`Proof for ${claim.id}`}>
          {claim.id === "CL-0214" ? <Suspense><PossessionProof /></Suspense> : <StaticProof id={claim.id} />}
        </section>
        <aside className="md-impact" aria-label="Impact and next step">
          <section className="md-panel">
            <h2>Where this claim is used</h2>
            <Link href="/producer/queue" className="md-used">
              <span><span className="md-mono md-accent-soft-text">D-031 v3</span><span>Okafor double restores…</span></span>
              <VerdictChip verdict="failed" label="Not eligible" />
            </Link>
            <p className="md-muted md-small">{verdict(claim) === "verified" ? "This claim passes, but the draft is still blocked by CL-0215 and CL-0216." : "This claim is one of the reasons D-031 is blocked."}</p>
          </section>
          <section className="md-panel">
            <h2>Verification record</h2>
            <dl className="md-rows md-rows-tight">
              <div><dt>Checked by</dt><dd>MatchDesk verifier</dd></div>
              <div><dt>At replay time</dt><dd className="md-mono">67:12</dd></div>
              <div><dt>Evidence</dt><dd className="md-mono">{claim.evidence.length ? claim.evidence.join(" · ") : "None"}</dd></div>
            </dl>
          </section>
          <NextStep eyebrow="Next step" title="Resolve the blocking claims in the composer" href="/producer/compose/D-031" action="Open D-031 in composer" />
          <p className="md-muted md-small"><Icon name="info" size={14} /> Verdicts here are deterministic checks, not AI confidence scores.</p>
        </aside>
      </div>
    </div>
  );
}
