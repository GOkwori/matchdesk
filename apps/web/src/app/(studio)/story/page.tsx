/** Every fan story in the match, newest first: one per goal, each verified against the log. */
import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "../../../studio/ui";
import { stories } from "../../../studio/stories";

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
        <p className="md-story-body">Every goal so far, explained and checked against the match event log. Synthetic demo match, replayed to 67:12.</p>
        <nav aria-label="Goals" className="md-story-more">
          <ul>
            {newest.map((s) => (
              <li key={s.slug}><Link href={`/story/${s.slug}`}><span className="md-mono">{s.clock}</span><span>{s.text.fan.en.headline}</span></Link></li>
            ))}
          </ul>
        </nav>
        <p className="md-muted md-small">Fans only see a story after a producer approves it.</p>
      </main>
    </div>
  );
}
