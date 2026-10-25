/** Styled 404 for any unknown studio address, with the three useful ways back in. */
import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "../../studio/icons";
import { Logo } from "../../studio/ui";

export const metadata: Metadata = { title: "Page not found", robots: { index: false } };

export default function NotFound() {
  return (
    <div className="md-welcome">
      <a className="md-skip" href="#main">Skip to main content</a>
      <header className="md-welcome-top"><Logo /></header>
      <main id="main" tabIndex={-1} className="md-state">
        <section className="md-panel md-state-card" aria-labelledby="md-404-title">
          <span className="md-state-icon" aria-hidden="true"><Icon name="flag" size={26} /></span>
          <h1 id="md-404-title">That page isn’t in the match log</h1>
          <p>The address may be mistyped, or the screen has moved. These will get you back on track.</p>
          <div className="md-btn-row">
            <Link href="/" className="md-btn md-btn-primary">Start page <Icon name="arrow" size={16} /></Link>
            <Link href="/match/nbr-riv" className="md-btn md-btn-secondary">Match overview</Link>
            <Link href="/about" className="md-btn md-btn-secondary">How facts are checked</Link>
          </div>
        </section>
      </main>
    </div>
  );
}
