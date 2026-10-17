/** About: how MatchDesk verifies a football story, in plain language (public, indexable). */
import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "../../../studio/icons";
import { Logo } from "../../../studio/ui";
import { eventCountText, possessionShare } from "../../../studio/data";

export const metadata: Metadata = {
  title: "How verification works",
  description: "How MatchDesk detects football moments, recalculates every claim from the event log, and keeps a human producer in charge of publishing.",
};

export default function AboutPage() {
  return (
    <div className="md-welcome">
      <header className="md-welcome-top"><Logo /><Link href="/match/nbr-riv" className="md-btn md-btn-secondary">Open the demo</Link></header>
      <main id="main" tabIndex={-1} className="md-welcome-main md-about">
        <h1>How verification works</h1>
        <p className="md-lede">MatchDesk never asks you to trust a number. Every statement in a story is a claim, and every claim is recalculated from the match event log before a human can approve it.</p>
        <ol className="md-welcome-steps">
          <li className="md-panel"><span className="md-step-icon"><Icon name="pulse" size={22} /></span><h2>1. Detect</h2><p>Fixed rules scan the {eventCountText}-event log for goals, big chances and other moments. The same log always gives the same moments.</p></li>
          <li className="md-panel"><span className="md-step-icon"><Icon name="shield" size={22} /></span><h2>2. Verify</h2><p>Each claim is checked by a registered formula. “58% possession” passes because the log gives {possessionShare().toFixed(1)}%; a forged 59% fails.</p></li>
          <li className="md-panel"><span className="md-step-icon"><Icon name="pen" size={22} /></span><h2>3. Approve</h2><p>AI can propose wording and spot patterns, but interpretations are labelled, unsupported claims are blocked, and only a producer approves.</p></li>
        </ol>
        <section className="md-panel md-about-trust">
          <h2>What this demo is, and isn’t</h2>
          <ul>
            <li>Northbridge FC v Riverside United is an invented match, replayed from a synthetic event log.</li>
            <li>The AI proposals are scripted for the demo; no live model runs here.</li>
            <li>There is no player tracking, so the app never shows formations or defender positions.</li>
            <li>Approving and publishing are planned features; nothing is published.</li>
          </ul>
        </section>
      </main>
      <footer className="md-welcome-foot"><span>AI-assisted. Verified. Human-led.</span><Link href="/" className="md-link">Back to the start</Link></footer>
    </div>
  );
}
