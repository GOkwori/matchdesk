/** Every fan story in the match, newest first: one per goal, each verified against the log. */
import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "../../../studio/ui";
import { stories } from "../../../studio/stories";
import { recaps } from "../../../studio/recaps";

export const metadata: Metadata = {
  title: "Match stories",
  description: "Every goal in the synthetic demo match, explained for fans and verified against the event log.",
  alternates: { canonical: "/story" },
};

export default function StoriesIndex() {
  const newest = [...stories].reverse();
  return (
    <div className="md-story">
      <a className="md-skip" href="#main">Skip to main content</a>
      <header className="md-story-top"><Logo size={30} /></header>
      <main id="main" tabIndex={-1} className="md-story-main">
        <h1 className="md-story-h1">Northbridge 2–1 Riverside</h1>
        <p className="md-story-body">Automated recaps and every goal so far, explained and checked against the match event log. Synthetic demo match, replayed to 67:12.</p>
        <nav aria-labelledby="md-recaps-h" className="md-story-more">
          <h2 id="md-recaps-h">Match recaps</h2>
          <ul>
            {[...recaps].reverse().map((r) => (
              <li key={r.id}><Link href={`/story/recap?at=${r.id}`}><span className="md-mono">{r.half ? "HT" : r.clock}</span><span>{r.text.fan.en.headline}</span></Link></li>
            ))}
          </ul>
        </nav>
        <nav aria-labelledby="md-goals-h" className="md-story-more">
          <h2 id="md-goals-h">Goals</h2>
          <ul>
            {newest.map((s) => (
              <li key={s.slug}><Link href={`/story/${s.slug}`}><span className="md-mono">{s.clock}</span><span>{s.text.fan.en.headline}</span></Link></li>
            ))}
          </ul>
        </nav>
        <p className="md-muted md-small">These are sample stories from a made-up match. Real publishing would need approval from a signed-in producer.</p>
      </main>
    </div>
  );
}
