/**
 * Automated match recaps: half-time and the replay point. Every figure comes from the generated
 * recap feed, whose claims the verifier passed; this page re-runs those checks in the browser and
 * follows the viewer's language, style and club from My match.
 */
"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Crest, Logo } from "./ui";
import { LANGUAGES, PERSONAS, useViewer, type ViewerLanguage } from "./viewer";
import { recapChrome, type Recap, type RecapClaim } from "./recap-chrome";
import { useRecheck } from "./recheck";
import { ListenButton } from "./voice";

const minute = (ms: number) => `${Math.floor(ms / 60_000) + 1}′`;

export function RecapBody({ recaps, claims, names, matchId, replayEndMs }: {
  recaps: readonly Recap[]; claims: readonly RecapClaim[]; names: Record<string, string>; matchId: string; replayEndMs: number;
}) {
  const params = useSearchParams();
  const { viewer, ready, update } = useViewer();
  const asked = params.get("lang");
  const lang: ViewerLanguage = asked === "en" || asked === "es" || asked === "fr" ? asked : viewer.language;
  const at = params.get("at") === "half-time" ? "half-time" : "latest";
  const recap = recaps.find((r) => r.id === at) ?? recaps[recaps.length - 1];
  const copy = recapChrome[lang];
  const persona = viewer.persona;
  const text = recap.text[persona][lang];
  const ids = new Set([...recap.checks.flatMap((c) => c.claim_ids), ...recap.milestones.flatMap((m) => m.claim_ids)]);
  const mine = claims.filter((c) => ids.has(c.claim_id));
  const recheck = useRecheck(mine, matchId, replayEndMs, names);
  const status = new Map(mine.map((c) => [c.claim_id, c.status]));
  const allVerified = mine.every((c) => c.status === "verified") && recheck !== "disagrees";
  const home = recap.score.nbr ?? 0;
  const away = recap.score.riv ?? 0;
  const club = viewer.club;
  const ahead = club ? (home === away ? null : (club === "nbr") === home > away) : null;
  const f = recap.figures;
  const decimal = (v: number) => (lang === "en" ? v.toFixed(1) : v.toFixed(1).replace(".", ","));
  const pct = (v: number) => (lang === "en" ? `${v}%` : `${v} %`);
  const query = (next: string) => {
    const q = new URLSearchParams(params.toString());
    q.set("at", next);
    q.delete("lang");
    return `?${q}`;
  };
  const setLang = (l: ViewerLanguage) => {
    update({ language: l });
    if (asked) {
      const q = new URLSearchParams(window.location.search);
      q.delete("lang");
      window.history.replaceState(null, "", `${window.location.pathname}${q.size ? `?${q}` : ""}`);
    }
  };
  const rows: [string, string, string][] = [
    [copy.possession, pct(f.possession.nbr), pct(f.possession.riv)],
    [copy.shots, String(f.shots.nbr), String(f.shots.riv)],
    [copy.passing, pct(f.pass_accuracy.nbr), pct(f.pass_accuracy.riv)],
    [copy.xg, decimal(f.synthetic_xg.nbr), decimal(f.synthetic_xg.riv)],
  ];
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
        <nav aria-label={copy.recaps} className="md-seg md-recap-tabs">
          {recaps.map((r) => (
            <Link key={r.id} href={query(r.id)} aria-current={r.id === recap.id ? "page" : undefined} replace scroll={false}>{r.title[lang]}</Link>
          ))}
        </nav>
        {allVerified
          ? <div className="md-banner md-banner-success"><span className="md-banner-icon" aria-hidden="true">✓</span><span><strong>{copy.verified[0]}</strong> · {copy.verified[1]}</span></div>
          : <div className="md-banner md-banner-error" role="alert"><span className="md-banner-icon" aria-hidden="true">✕</span><span>{copy.recheckFailed}</span></div>}
        <div role="group" aria-label={copy.style} className="md-seg md-story-personas">
          {PERSONAS.map((p) => <button key={p.id} type="button" aria-pressed={persona === p.id} onClick={() => update({ persona: p.id })}>{copy.personas[p.id]}</button>)}
        </div>
        <h1 className={`md-story-h1 md-story-h1-${persona}`}>{text.headline}</h1>
        <p className="md-story-body">{text.body}</p>
        {allVerified && <ListenButton item={{ kind: "recap", id: recap.id, lang, text: recap.text.fan[lang].body }} />}
        {ready && club && (
          <p className={`md-story-yours${ahead ? " md-story-yours-mine" : ""}`}>{copy.yourClub(names[club] ?? club, ahead)}</p>
        )}
        <div className="md-story-score" aria-label={copy.score(home, away, recap.title[lang])}>
          <span><Crest team="NBR" size={26} />NBR</span>
          <span className="md-story-num"><span>{home} – {away}</span><span className="md-mono md-accent-soft-text">{recap.half ? { en: "HT", es: "DESC", fr: "MT" }[lang] : recap.clock}</span></span>
          <span>RIV<Crest team="RIV" size={26} /></span>
        </div>
        <section aria-labelledby="md-recap-figs" className="md-panel md-recap-figs">
          <h2 id="md-recap-figs">{copy.figures}</h2>
          <table className="md-table">
            <thead><tr><th scope="col"><span className="md-visually-hidden">{copy.figures}</span></th><th scope="col">NBR</th><th scope="col">RIV</th></tr></thead>
            <tbody>
              {rows.map(([label, h, a]) => <tr key={label}><th scope="row">{label}</th><td className="md-mono">{h}</td><td className="md-mono">{a}</td></tr>)}
              <tr><th scope="row">{copy.tackles}</th><td colSpan={2}>{names[f.tackles_leader.player] ?? f.tackles_leader.player} · {f.tackles_leader.tackles}</td></tr>
            </tbody>
          </table>
        </section>
        <section aria-labelledby="md-recap-ms" className="md-story-more">
          <h2 id="md-recap-ms">{copy.milestones}</h2>
          <ol className="md-recap-milestones">
            {recap.milestones.map((m) => {
              const ok = m.claim_ids.every((id) => status.get(id) === "verified");
              const story = m.kind === "goal" ? recap.goals.find((g) => g.event_id === m.event_id)?.story : null;
              const body = <><span className="md-mono">{minute(m.t_ms)}</span><span>{m.label[lang]}</span><span className={ok ? "md-ok" : "md-bad"} aria-label={ok ? copy.matches : copy.failed}>{ok ? "✓" : "✕"}</span></>;
              return (
                <li key={`${m.kind}-${m.event_id}`} className={club === m.team ? "md-recap-mine" : undefined}>
                  {story ? <Link href={`/story/${story}`} aria-label={`${m.label[lang]}. ${copy.story}`}>{body}</Link> : <span className="md-recap-row">{body}</span>}
                </li>
              );
            })}
          </ol>
        </section>
        <details className="md-panel md-checks" open>
          <summary>{copy.title}</summary>
          <ul>
            {recap.checks.map((check) => {
              const ok = check.claim_ids.every((id) => status.get(id) === "verified");
              return <li key={check.claim_ids.join()}><span>{check.label[lang]}</span>{ok ? <span className="md-ok">✓ {copy.matches}</span> : <span className="md-bad">✕ {copy.failed}</span>}</li>;
            })}
            {recap.unchecked.map((row) => <li key={row.en}><span>{row[lang]}</span><span className="md-muted">○ {copy.notChecked}</span></li>)}
          </ul>
          {recheck === "agrees" && <p className="md-small md-ok" role="status">✓ {copy.rechecked}</p>}
          <p className="md-muted md-small">{copy.note}</p>
          {copy.translation && <p className="md-muted md-small">{copy.translation}</p>}
          <p className="md-small"><a href="/recaps/nbr-riv.json">{copy.feed}</a></p>
        </details>
      </main>
    </div>
  );
}
