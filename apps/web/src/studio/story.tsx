/** Public fan story with a language switch; every variant is bound to the same verified claim. */
"use client";

import { useState } from "react";
import { Crest, Logo } from "./ui";
import { TourStep } from "./shell";
import { storyCopy, type Language } from "./data";

export function StoryBody() {
  const [lang, setLang] = useState<Language>("en");
  const copy = storyCopy[lang];
  return (
    <div className="md-story">
      <header className="md-story-top">
        <Logo size={30} />
        <div role="group" aria-label="Language" className="md-lang">
          {(Object.keys(storyCopy) as Language[]).map((l) => (
            <button key={l} type="button" aria-pressed={lang === l} lang={l} onClick={() => setLang(l)} aria-label={storyCopy[l].label}>{l.toUpperCase()}</button>
          ))}
        </div>
      </header>
      <main id="main" tabIndex={-1} lang={lang} className="md-story-main">
        <div className="md-banner md-banner-success"><span className="md-banner-icon" aria-hidden="true">✓</span><span><strong>Verified moment</strong> · checked against the match event log</span></div>
        <h1 className="md-story-h1">{copy.headline[0]}<span className="md-accent-text">{copy.headline[1]}</span></h1>
        <p className="md-story-body">{copy.body}</p>
        <div className="md-story-score" aria-label="Northbridge 2, Riverside 1 at 58:17">
          <span><Crest team="NBR" size={26} />NBR</span>
          <span className="md-story-num"><span>2 – 1</span><span className="md-mono md-accent-soft-text">58:17</span></span>
          <span>RIV<Crest team="RIV" size={26} /></span>
        </div>
        <figure className="md-story-fig">
          <svg viewBox="0 0 358 170" role="img" aria-label="Diagram: corner from the right at 58:03, headed goal inside the six-yard box at 58:17">
            <rect width="358" height="170" fill="var(--md-pitch)" />
            <g fill="none" stroke="var(--md-pitch-line)" strokeWidth="1.2"><path d="M120 0v170" /><circle cx="120" cy="85" r="34" /><rect x="268" y="32" width="90" height="106" /><rect x="326" y="62" width="32" height="46" /></g>
            <path d="M354 4C318 22 312 52 330 78" stroke="var(--md-accent-soft)" strokeWidth="2.2" strokeDasharray="6 5" fill="none" />
            <circle cx="352" cy="5" r="5" fill="var(--md-accent-soft)" />
            <circle cx="330" cy="78" r="9" fill="var(--md-home)" stroke="var(--md-text)" strokeWidth="2" />
            <g fontFamily="var(--md-font-mono)" fontSize="12" fontWeight="600"><text x="246" y="18" fill="var(--md-accent-soft)">① 58:03</text><text x="252" y="104" fill="var(--md-text)">② 58:17</text></g>
          </svg>
          <figcaption>{copy.caption}</figcaption>
        </figure>
        <details className="md-panel md-checks" open>
          <summary>{copy.title}</summary>
          <ul>
            <li><span>{copy.checks[0]}</span><span className="md-ok">✓ {copy.matches}</span></li>
            <li><span>{copy.checks[1]}</span><span className="md-ok">✓ {copy.matches}</span></li>
            <li><span>{copy.checks[2]}</span><span className="md-muted">○ {copy.notChecked}</span></li>
          </ul>
          <p className="md-muted md-small">{copy.note}</p>
        </details>
        <TourStep step={6} />
      </main>
    </div>
  );
}
