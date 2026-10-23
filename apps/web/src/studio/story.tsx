/**
 * Public fan story for one goal. The text, score and diagram come from the generated story
 * feed, whose facts the verifier passed; this page re-runs those checks in the browser, and
 * follows the viewer's language, style, club and player from My match.
 */
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Crest, Logo } from "./ui";
import { TourStep } from "./shell";
import { LANGUAGES, PERSONAS, useViewer, type ViewerLanguage } from "./viewer";
import { storyChrome, type Story, type StoryClaim, type StoryEvent, type StorySummary } from "./story-chrome";
import { useRecheck } from "./recheck";

/** Display position on a full pitch: the scoring side attacks right. */
function at(x: number, y: number): [number, number] {
  return [1 + (x / 100) * 103, 1 + (y / 100) * 66];
}

/** A numbered marker whose label stays inside the pitch. */
function Marker({ x, y, n, fill, ring }: { x: number; y: number; n: string; fill: string; ring?: boolean }) {
  const right = x > 80;
  const tx = right ? x - 3.2 : x + 3.2;
  const ty = y < 8 ? y + 6.5 : y - 2.6;
  return (
    <g>
      <circle cx={x} cy={y} r={ring ? 2.6 : 2.2} fill={fill} stroke={ring ? "var(--md-text)" : undefined} strokeWidth={ring ? 0.6 : undefined} />
      <text x={tx} y={ty} textAnchor={right ? "end" : "start"} fontSize="4.2" fontWeight="700" fill="var(--md-text)">{n}</text>
    </g>
  );
}

function MoveDiagram({ events, label, team }: { events: readonly StoryEvent[]; label: string; team: "nbr" | "riv" }) {
  const drawn = events.filter((e) => e.x != null && e.y != null);
  const first = drawn[0];
  const shot = [...drawn].reverse().find((e) => e.type === "shot" || e.type === "goal");
  return (
    <svg viewBox="0 0 105 68" role="img" aria-label={label}>
      <defs><marker id="md-story-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="3.2" markerHeight="3.2" orient="auto-start-reverse"><path d="M0 0 6 3 0 6z" fill="var(--md-accent-soft)" /></marker></defs>
      <rect width="105" height="68" fill="var(--md-pitch)" />
      <g fill="none" stroke="var(--md-pitch-line)" strokeWidth="0.35">
        <rect x="1" y="1" width="103" height="66" /><path d="M52.5 1v66" /><circle cx="52.5" cy="34" r="9.15" />
        <rect x="87.5" y="13.85" width="16.5" height="40.3" /><rect x="98.5" y="24.85" width="5.5" height="18.3" />
      </g>
      {drawn.filter((e) => e.end_x != null && e.end_y != null && (e.type === "pass" || e.type === "carry")).map((e) => {
        const [x1, y1] = at(e.x!, e.y!);
        const [x2, y2] = at(e.end_x!, e.end_y!);
        return <line key={e.id} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--md-accent-soft)" strokeWidth="0.55" strokeDasharray={e.type === "carry" ? "1.2 1" : undefined} opacity={e.outcome === "complete" ? 0.95 : 0.45} markerEnd="url(#md-story-arrow)" />;
      })}
      {first && <Marker x={at(first.x!, first.y!)[0]} y={at(first.x!, first.y!)[1]} n="①" fill="var(--md-accent-soft)" />}
      {shot && <Marker x={at(shot.x!, shot.y!)[0]} y={at(shot.x!, shot.y!)[1]} n="②" fill={team === "nbr" ? "var(--md-home)" : "var(--md-away)"} ring />}
    </svg>
  );
}

export function StoryBody({ story, claims, others, names, matchId, replayEndMs }: {
  story: Story; claims: readonly StoryClaim[]; others: readonly StorySummary[]; names: Record<string, string>; matchId: string; replayEndMs: number;
}) {
  const params = useSearchParams();
  const { viewer, ready, update } = useViewer();
  const asked = params.get("lang");
  const lang: ViewerLanguage = asked === "en" || asked === "es" || asked === "fr" ? asked : viewer.language;
  const persona = viewer.persona;
  const copy = storyChrome[lang];
  const text = story.text[persona][lang];
  const recheck = useRecheck(claims, matchId, replayEndMs, names);
  const status = new Map(claims.map((c) => [c.claim_id, c.status]));
  const allVerified = claims.every((c) => c.status === "verified") && recheck !== "disagrees";
  const team = names[story.team] ?? story.team;
  const home = story.score.after.nbr ?? 0;
  const away = story.score.after.riv ?? 0;
  const ordered = [...others].sort((a, b) => Number(b.team === viewer.club) - Number(a.team === viewer.club));
  const setLang = (l: ViewerLanguage) => {
    update({ language: l });
    if (asked) {
      const query = new URLSearchParams(window.location.search);
      query.delete("lang");
      window.history.replaceState(null, "", `${window.location.pathname}${query.size ? `?${query}` : ""}`);
    }
  };
  return (
    <div className="md-story">
      <a className="md-skip" href="#main">Skip to main content</a>
      <header className="md-story-top">
        <Logo size={30} />
        <div role="group" aria-label="Language" className="md-lang">
          {LANGUAGES.map((l) => (
            <button key={l.id} type="button" aria-pressed={lang === l.id} lang={l.id} onClick={() => setLang(l.id)} aria-label={l.label}>{l.id.toUpperCase()}</button>
          ))}
        </div>
      </header>
      <main id="main" tabIndex={-1} lang={lang} className="md-story-main" aria-busy={!ready}>
        {allVerified
          ? <div className="md-banner md-banner-success"><span className="md-banner-icon" aria-hidden="true">✓</span><span><strong>{copy.verified[0]}</strong> · {copy.verified[1]}</span></div>
          : <div className="md-banner md-banner-error" role="alert"><span className="md-banner-icon" aria-hidden="true">✕</span><span>{copy.recheckFailed}</span></div>}
        <div role="group" aria-label={copy.style} className="md-seg md-story-personas">
          {PERSONAS.map((p) => <button key={p.id} type="button" aria-pressed={persona === p.id} onClick={() => update({ persona: p.id })}>{copy.personas[p.id]}</button>)}
        </div>
        <h1 className={`md-story-h1 md-story-h1-${persona}`}>{text.headline}</h1>
        <p className="md-story-body">{text.body}</p>
        {ready && (viewer.club || viewer.player === story.scorer) && (
          <p className={`md-story-yours${viewer.club === story.team || viewer.player === story.scorer ? " md-story-yours-mine" : ""}`}>
            {viewer.player === story.scorer ? copy.yourPlayer(names[story.scorer] ?? story.scorer) : copy.yourClub(names[viewer.club!] ?? viewer.club!, team, viewer.club === story.team)}
          </p>
        )}
        <div className="md-story-score" aria-label={copy.score(home, away, story.clock)}>
          <span><Crest team="NBR" size={26} />NBR</span>
          <span className="md-story-num"><span>{home} – {away}</span><span className="md-mono md-accent-soft-text">{story.clock}</span></span>
          <span>RIV<Crest team="RIV" size={26} /></span>
        </div>
        <figure className="md-story-fig">
          <MoveDiagram events={story.buildup} team={story.team} label={`${copy.diagram}: ${story.diagram[lang]}`} />
          <figcaption>{story.diagram[lang]}</figcaption>
        </figure>
        <details className="md-panel md-checks" open>
          <summary>{copy.title}</summary>
          <ul>
            {story.checks.map((check) => {
              const ok = check.claim_ids.every((id) => status.get(id) === "verified");
              return <li key={check.claim_ids.join()}><span>{check.label[lang]}</span>{ok ? <span className="md-ok">✓ {copy.matches}</span> : <span className="md-bad">✕ {copy.failed}</span>}</li>;
            })}
            {story.unchecked.map((row) => <li key={row.en}><span>{row[lang]}</span><span className="md-muted">○ {copy.notChecked}</span></li>)}
          </ul>
          {recheck === "agrees" && <p className="md-small md-ok" role="status">✓ {copy.rechecked}</p>}
          <p className="md-muted md-small">{copy.note}</p>
          {copy.translation && <p className="md-muted md-small">{copy.translation}</p>}
        </details>
        {ordered.length > 0 && (
          <nav aria-labelledby="md-more-goals" className="md-story-more">
            <h2 id="md-more-goals">{copy.more}</h2>
            <ul>
              {ordered.map((o) => (
                <li key={o.slug}><Link href={`/story/${o.slug}`}><span className="md-mono">{o.clock}</span><span>{o.headline[lang]}</span>{o.team === viewer.club && <span className="md-chip md-chip-pill">★</span>}</Link></li>
              ))}
            </ul>
          </nav>
        )}
        <TourStep step={7} />
      </main>
    </div>
  );
}
