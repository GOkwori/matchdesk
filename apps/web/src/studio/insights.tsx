/** AI insights: scripted specialist proposals a producer keeps or dismisses, with a recoverable error. */
"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "./icons";
import { VerdictChip } from "./ui";
import { matchExport, possessionSeries, STORY_SLUG } from "./data";

type Decision = "open" | "kept" | "dismissed";

const ROLES = ["Tactical Analyst", "Narrative Composer", "Editorial Reviewer", "Audience Adapter", "Human decision"] as const;

export function InsightsBody() {
  const lowest = possessionSeries.reduce((m, p) => (p.share < m.share ? p : m));
  const insights = [
    { id: "IN-1", role: "Tactical Analyst", tone: "pending" as const, chip: "Interpretation · needs review", title: "Riverside’s best spell came before the break", body: `Northbridge’s possession fell to ${lowest.share}% between ${lowest.minute}′ and ${lowest.minute + 5}′ (possession_time.v1).`, href: "/match/nbr-riv/evidence/CL-0215", cite: "CL-0215" },
    { id: "IN-2", role: "Narrative Composer", tone: "verified" as const, chip: "Source facts verified", title: "Headline: “Okafor double restores Northbridge lead”", body: "Both Northbridge goals are logged to Okafor (E-0688, E-1366).", href: "/match/nbr-riv/evidence/CL-0213", cite: "CL-0213" },
    { id: "IN-3", role: "Editorial Reviewer", tone: "failed" as const, chip: "Unsupported · remove", title: "“First brace of the season” can’t be checked", body: "The log covers this match only; there is no season history to verify it.", href: "/match/nbr-riv/evidence/CL-0216", cite: "CL-0216" },
  ];
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [retry, setRetry] = useState<"error" | "loading" | "done">("error");
  const open = insights.filter((i) => (decisions[i.id] ?? "open") === "open").length;
  const decide = (id: string, d: Decision) => setDecisions((s) => ({ ...s, [id]: d }));
  const counterGoals = matchExport.detected_moments.by_kind as Record<string, number>;

  return (
    <>
      <ol className="md-roles" aria-label="Specialist pipeline">
        {ROLES.map((r, i) => (
          <li key={r} className={i === ROLES.length - 1 ? "md-role-human" : "md-role-done"}>
            <span className="md-role-num" aria-hidden="true">{i === ROLES.length - 1 ? <Icon name="pen" size={14} /> : "✓"}</span>
            <span><strong>{r}</strong><span className="md-muted md-small">{i === ROLES.length - 1 ? "You decide" : "Proposal ready"}</span></span>
          </li>
        ))}
      </ol>
      <div className="md-split">
        <section className="md-panel md-split-main" aria-labelledby="md-ins-title">
          <div className="md-panel-head"><h2 id="md-ins-title">Proposals to review</h2><span className="md-muted" aria-live="polite">{open} left to review</span></div>
          <ul className="md-insight-list">
            {insights.map((i) => {
              const d = decisions[i.id] ?? "open";
              return (
                <li key={i.id} className={`md-insight md-insight-${d}`}>
                  <span className="md-insight-top"><span className="md-eyebrow">{i.role}</span><VerdictChip verdict={i.tone} label={i.chip} /></span>
                  <strong>{i.title}</strong>
                  <p>{i.body}</p>
                  <span className="md-btn-row">
                    <Link href={i.href} className="md-link">Evidence · {i.cite} <Icon name="arrow" size={14} /></Link>
                    {d === "open" ? (
                      <>
                        <button type="button" className="md-mini-btn" onClick={() => decide(i.id, "kept")}>Keep for producer</button>
                        <button type="button" className="md-mini-btn" onClick={() => decide(i.id, "dismissed")}>Dismiss</button>
                      </>
                    ) : (
                      <span className="md-decision">{d === "kept" ? "Kept for producer" : "Dismissed"} · <button type="button" className="md-text-btn" onClick={() => decide(i.id, "open")}>Undo</button></span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
        <aside className="md-split-side" aria-label="More proposals">
          <section className="md-panel" aria-labelledby="md-aud-title">
            <span className="md-eyebrow">Audience Adapter</span>
            <h2 id="md-aud-title" className="md-sel-title">9 versions of the 58′ story</h2>
            <p className="md-muted">English, Spanish and French, each for analysts, casual fans and broadcast captions. All are bound to the same verified evidence.</p>
            <Link href={`/story/${STORY_SLUG}`} className="md-btn md-btn-secondary">Preview the fan story</Link>
          </section>
          <section className={`md-panel ${retry === "error" ? "md-panel-error" : ""}`} aria-labelledby="md-retry-title" aria-live="polite">
            <span className="md-eyebrow">Tactical Analyst</span>
            <h2 id="md-retry-title" className="md-sel-title">{retry === "done" ? "Counter-attack check complete" : "Counter-attack insight"}</h2>
            {retry === "error" && <><p className="md-muted">We couldn’t generate this proposal just now. Nothing was lost. <code>ref: req-7f3a</code></p><button type="button" className="md-btn md-btn-secondary" onClick={() => { setRetry("loading"); window.setTimeout(() => setRetry("done"), 700); }}>Try again</button></>}
            {retry === "loading" && <p className="md-muted">Checking the counter_attack_goal detector…</p>}
            {retry === "done" && <p className="md-muted">No counter-attack goals in this log ({counterGoals.counter_attack_goal ?? 0} detected), so there is nothing to propose.</p>}
          </section>
        </aside>
      </div>
    </>
  );
}
