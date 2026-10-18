/** Welcome: explains MatchDesk in ten seconds and offers a guided demo, a lens, or a resume. */
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { Icon } from "../../studio/icons";
import { TopActions } from "../../studio/shell";
import { Crest, Logo } from "../../studio/ui";
import { ContinueCard } from "../../studio/welcome";
import { STORY_SLUG } from "../../studio/data";
import { SITE_URL } from "../../studio/site";

export const metadata: Metadata = {
  title: { absolute: "MatchDesk · Turn football moments into verifiable stories" },
  description: "AI-assisted analysis, deterministic verification and human approval for football storytelling. Explore the synthetic Northbridge v Riverside demo.",
  alternates: { canonical: "/" },
};

const steps = [
  { n: "01", title: "Detect", body: "Key moments are found in the match event log by clear rules.", icon: "pulse" as const },
  { n: "02", title: "Verify", body: "Every claim is recalculated from the events, never taken on trust.", icon: "shield" as const },
  { n: "03", title: "Approve", body: "A human producer decides what reaches fans.", icon: "pen" as const },
];

/** Structured data for the product and site. The synthetic match is deliberately not marked up as a real SportsEvent. */
const jsonLd = [
  { "@context": "https://schema.org", "@type": "WebSite", name: "MatchDesk", url: `${SITE_URL}/`, inLanguage: "en-GB" },
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "MatchDesk",
    url: `${SITE_URL}/`,
    applicationCategory: "SportsApplication",
    operatingSystem: "Web",
    description: "AI-assisted football analysis with deterministic claim verification and human approval before anything reaches fans.",
    offers: { "@type": "Offer", price: "0", priceCurrency: "GBP" },
  },
];

export default function WelcomePage() {
  return (
    <div className="md-welcome">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
      <a className="md-skip" href="#main">Skip to main content</a>
      <header className="md-welcome-top">
        <Logo />
        <TopActions compact />
      </header>
      <main id="main" tabIndex={-1} className="md-welcome-main">
        <section className="md-welcome-hero">
          <div className="md-welcome-copy">
            <span className="md-eyebrow">Football intelligence · explained · verified</span>
            <h1>Turn football moments into <span className="md-accent-text">verifiable stories.</span></h1>
            <p>AI-assisted analysis. Deterministic verification. Human control. See it work on a replayed match in three minutes.</p>
            <div className="md-btn-row">
              <Link href="/match/nbr-riv?tour=1" className="md-btn md-btn-primary md-btn-lg">Start the 3-minute guided demo <Icon name="arrow" size={18} /></Link>
              <Link href="/match/nbr-riv" className="md-btn md-btn-secondary md-btn-lg">Explore on my own</Link>
            </div>
            <Suspense><ContinueCard /></Suspense>
          </div>
          <div className="md-welcome-card" aria-label="Demo match">
            <span className="md-eyebrow">Synthetic replay · 67:12</span>
            <div className="md-welcome-score">
              <span><Crest team="NBR" size={48} /><strong>Northbridge</strong></span>
              <span className="md-score">2 – 1</span>
              <span><Crest team="RIV" size={48} /><strong>Riverside</strong></span>
            </div>
            <ul className="md-welcome-facts">
              <li><span className="md-mono">34:18</span> Okafor opens the scoring</li>
              <li><span className="md-mono">41:03</span> Lindqvist levels</li>
              <li><span className="md-mono">58:17</span> Okafor header restores the lead</li>
            </ul>
          </div>
        </section>

        <ol className="md-welcome-steps" aria-label="How MatchDesk works">
          {steps.map((s) => (
            <li key={s.n} className="md-panel">
              <span className="md-step-icon"><Icon name={s.icon} size={22} /></span>
              <span className="md-mono md-accent-soft-text">{s.n}</span>
              <h2>{s.title}</h2>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>

        <section aria-labelledby="md-lens" className="md-lenses">
          <h2 id="md-lens">Or jump straight to what you care about</h2>
          <div className="md-lens-grid">
            <Link href="/producer/queue" className="md-lens"><Icon name="monitor" size={22} /><strong>I’m a producer</strong><span>See what’s blocked and fix a draft.</span></Link>
            <Link href="/match/nbr-riv/evidence/CL-0214" className="md-lens"><Icon name="shield" size={22} /><strong>Show me the proof</strong><span>Watch a statistic get recalculated.</span></Link>
            <Link href={`/story/${STORY_SLUG}`} className="md-lens"><Icon name="phone" size={22} /><strong>I’m a fan</strong><span>Read the verified story on your phone.</span></Link>
          </div>
        </section>
      </main>
      <footer className="md-welcome-foot"><span>AI-assisted. Verified. Human-led. <Link href="/about" className="md-link">How verification works</Link></span><span>Synthetic demo match · nothing is published</span></footer>
    </div>
  );
}
