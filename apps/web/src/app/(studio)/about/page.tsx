/** About: how MatchDesk verifies a football story, in plain language (public, indexable). */
import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "../../../studio/icons";
import { Logo } from "../../../studio/ui";
import { eventCountText, possessionShare } from "../../../studio/data";

/** The public MCP endpoint, on the Azure deployment where the API sits behind /api. */
const MCP_URL = "https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/api/mcp";

export const metadata: Metadata = {
  title: "How verification works",
  description: "How MatchDesk detects football moments, recalculates every claim from the event log, and keeps a human producer in charge of publishing.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <div className="md-welcome">
      <a className="md-skip" href="#main">Skip to main content</a>
      <header className="md-welcome-top"><Logo /><Link href="/match/nbr-riv" className="md-btn md-btn-secondary">Open the demo</Link></header>
      <main id="main" tabIndex={-1} className="md-welcome-main md-about">
        <h1>How verification works</h1>
        <p className="md-lede">MatchDesk never asks you to trust a number. Every statement in a story is a claim, and every claim is recalculated from the match event log before a human can approve it.</p>
        <ol className="md-welcome-steps">
          <li className="md-panel"><span className="md-step-icon"><Icon name="pulse" size={22} /></span><h2>1. Detect</h2><p>Fixed rules scan the {eventCountText}-event log for goals, big chances and other moments. The same log always gives the same moments.</p></li>
          <li className="md-panel"><span className="md-step-icon"><Icon name="shield" size={22} /></span><h2>2. Verify</h2><p>Each claim is checked by a registered formula. “58% possession” passes because the log gives {possessionShare().toFixed(2)}%, which rounds to 58% at the precision the claim is stated at; a forged 59% fails. The same check runs on the server and again in your browser, and the two must agree.</p></li>
          <li className="md-panel"><span className="md-step-icon"><Icon name="pen" size={22} /></span><h2>3. Approve</h2><p>AI can propose wording and spot patterns, but interpretations are labelled, unsupported claims are blocked, and only a producer approves.</p></li>
        </ol>
        <section className="md-panel md-about-trust">
          <h2>What this demo is, and isn’t</h2>
          <ul>
            <li>Northbridge FC v Riverside United is an invented match, replayed from a synthetic event log.</li>
            <li>The four AI specialists run on Microsoft Foundry. AI insights opens on a recorded live run; on the Azure deployment you can start a fresh one, spaced out and capped to bound cost. Every figure they propose is checked by the verifier, never taken on trust.</li>
            <li>There is no player tracking, so the app never shows formations or defender positions.</li>
            <li>Approving and publishing are planned features; nothing is published.</li>
          </ul>
        </section>
        <section className="md-panel md-about-trust" aria-labelledby="md-mcp">
          <h2 id="md-mcp">Connect your own agent</h2>
          <p>The Azure deployment offers MatchDesk’s tools over the Model Context Protocol, so a broadcaster’s graphics assistant, an IDE agent or a Foundry agent can use the same evidence and the same verifier. It is read-only and needs no key.</p>
          <p><code className="md-mono">{MCP_URL}</code></p>
          <ul>
            <li><strong>check_sentence</strong> and <strong>verify_claim</strong>: have a sentence or a claim checked before it is shown.</li>
            <li><strong>compute_metric</strong>, <strong>list_metrics</strong>, <strong>list_players</strong>: the fourteen registered statistics for any team, player and window.</li>
            <li><strong>get_events</strong>, <strong>get_overlays</strong>, <strong>get_story</strong>, <strong>get_recap</strong>: the log, the timed overlay cues, the goal stories and the recaps, in any persona and language.</li>
          </ul>
          <p className="md-small md-muted">Add it to an MCP client as a Streamable HTTP server, for example <code className="md-mono">{`{"servers": {"matchdesk": {"type": "http", "url": "${MCP_URL}"}}}`}</code> in VS Code.</p>
        </section>
      </main>
      <footer className="md-welcome-foot"><span>AI-assisted. Verified. Human-led.</span><Link href="/" className="md-link">Back to the start</Link></footer>
    </div>
  );
}
