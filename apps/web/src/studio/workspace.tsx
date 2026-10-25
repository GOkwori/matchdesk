/** Activity & Audit and Settings: the audit trail and per-device preferences. */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon } from "./icons";
import { loadD031 } from "./composer";
import { draftEligibility } from "./data";
import { MyMatchSettings } from "./my-match";
import { DEFAULT_VIEWER, saveViewer } from "./viewer";

type Row = { time: string; actor: string; initials: string; action: string; detail: string; kind: "verification" | "editorial" | "system" };

const BASE_ROWS: Row[] = [
  { time: "18:32", actor: "Priya Shah", initials: "PS", action: "Saved D-031 v3", detail: "4 claims linked", kind: "editorial" },
  { time: "18:30", actor: "MatchDesk", initials: "MD", action: "Verified CL-0214", detail: "possession_time.v1 · 57.96% → 58%", kind: "verification" },
  { time: "18:29", actor: "MatchDesk", initials: "MD", action: "Failed CL-0216", detail: "No season history in the log", kind: "verification" },
  { time: "18:27", actor: "Sam Reed", initials: "SR", action: "Reviewed CL-0213", detail: "Goals E-0688, E-1366", kind: "verification" },
  { time: "18:20", actor: "MatchDesk", initials: "MD", action: "Detected goal M-05", detail: "E-1366 at 58:17", kind: "system" },
  { time: "17:05", actor: "Priya Shah", initials: "PS", action: "Saved D-029 v2", detail: "4 of 4 claims verified", kind: "editorial" },
  { time: "17:00", actor: "MatchDesk", initials: "MD", action: "Replay loaded", detail: "Northbridge v Riverside · synthetic", kind: "system" },
];

const FILTERS = [{ id: "all", label: "All" }, { id: "verification", label: "Verification" }, { id: "editorial", label: "Editorial" }, { id: "system", label: "System" }] as const;

export function ActivityBody() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");
  const [rows, setRows] = useState<Row[]>(BASE_ROWS);
  useEffect(() => {
    const doc = loadD031();
    if (Object.keys(doc.states).length && draftEligibility(doc.states, doc.failedEdits).eligible) {
      setRows([{ time: "now", actor: "Demo visitor", initials: "DV", action: doc.submitted ? "Marked D-031 v4 for demo review" : "Checked D-031 v4", detail: "Only on this device", kind: "editorial" }, ...BASE_ROWS]);
    }
  }, []);
  const shown = rows.filter((r) => filter === "all" || r.kind === filter);
  return (
    <div className="md-split">
      <section className="md-panel md-split-main" aria-labelledby="md-act-title">
        <p className="md-muted md-small" role="note"><strong>Demonstration records.</strong> Names and past actions below are fictional. Changes you make here stay in this browser; they do not create a real audit record.</p>
        <div className="md-panel-head"><h2 id="md-act-title">Sample activity · 11 Oct 2026</h2>
          <div role="group" aria-label="Filter activity" className="md-seg">
            {FILTERS.map((f) => <button key={f.id} type="button" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>{f.label}</button>)}
          </div>
        </div>
        <table className="md-table">
          <caption className="md-visually-hidden">Audit trail, newest first</caption>
          <thead><tr><th scope="col">Time</th><th scope="col">Who</th><th scope="col">What</th><th scope="col">Detail</th></tr></thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={`${r.time}-${i}`}>
                <td className="md-mono">{r.time}</td>
                <td><span className="md-who"><span className={`md-avatar-sm md-av-${r.initials}`} aria-hidden="true">{r.initials}</span>{r.actor}</span></td>
                <td>{r.action}</td>
                <td className="md-muted">{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <aside className="md-split-side" aria-label="Version history">
        <section className="md-panel" aria-labelledby="md-ver-title">
          <h2 id="md-ver-title">Sample draft versions</h2>
          <ol className="md-versions">
            {rows[0].actor === "Demo visitor" && <li><span className="md-mono">v4</span><span>Re-verified · eligible</span><span className="md-chip md-chip-verified">✓ Eligible</span></li>}
            <li><span className="md-mono">v3</span><span>Priya Shah · 18:32</span><span className="md-chip md-chip-failed">✕ Not eligible</span></li>
            <li><span className="md-mono">v2</span><span>Priya Shah · 18:10</span><span className="md-chip md-chip-not-yet">Superseded</span></li>
            <li><span className="md-mono">v1</span><span>Priya Shah · 17:52</span><span className="md-chip md-chip-not-yet">Superseded</span></li>
          </ol>
          <p className="md-muted md-small">No version has been published.</p>
        </section>
      </aside>
    </div>
  );
}

const PREF_KEY = "md.prefs";
export type Prefs = { motion: "system" | "reduce"; text: "default" | "large" };
const DEFAULT_PREFS: Prefs = { motion: "system", text: "default" };

export function readPrefs(): Prefs {
  try { return { ...DEFAULT_PREFS, ...(JSON.parse(window.localStorage.getItem(PREF_KEY) ?? "{}") as Partial<Prefs>) }; } catch { return DEFAULT_PREFS; }
}

/** Apply preferences to the document so CSS can honour them on every screen. */
export function applyPrefs(prefs: Prefs) {
  document.documentElement.dataset.mdMotion = prefs.motion;
  document.documentElement.dataset.mdText = prefs.text;
}

export function SettingsBody() {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [reset, setReset] = useState(false);
  useEffect(() => { setPrefs(readPrefs()); }, []);
  const update = (next: Prefs) => {
    setPrefs(next);
    applyPrefs(next);
    try { window.localStorage.setItem(PREF_KEY, JSON.stringify(next)); } catch { /* preference applies for this visit only */ }
  };
  const resetDemo = () => {
    try { for (const key of ["md.d031", "md.d031.approval", "md.lastPath", "md.tourDone", "md.viewer"]) window.localStorage.removeItem(key); } catch { /* nothing stored */ }
    saveViewer(DEFAULT_VIEWER);
    setReset(true);
  };
  return (
    <div className="md-ds">
      <MyMatchSettings />
      <section className="md-panel" aria-labelledby="md-set-display">
        <h2 id="md-set-display">Display</h2>
        <label className="md-switch">
          <input type="checkbox" role="switch" checked={prefs.motion === "reduce"} onChange={(e) => update({ ...prefs, motion: e.target.checked ? "reduce" : "system" })} />
          <span><strong>Reduce motion</strong><span className="md-muted md-small">Turns off animations. Your system setting is always respected.</span></span>
        </label>
        <label className="md-switch">
          <input type="checkbox" role="switch" checked={prefs.text === "large"} onChange={(e) => update({ ...prefs, text: e.target.checked ? "large" : "default" })} />
          <span><strong>Larger text</strong><span className="md-muted md-small">Scales the interface up by about an eighth.</span></span>
        </label>
        <p className="md-muted md-small">Theme: Sunset Studio (dark).</p>
      </section>
      <section className="md-panel" aria-labelledby="md-set-demo">
        <h2 id="md-set-demo">Demo</h2>
        <div className="md-btn-row">
          <Link href="/match/nbr-riv?tour=1" className="md-btn md-btn-primary">Restart guided tour <Icon name="arrow" size={16} /></Link>
          <button type="button" className="md-btn md-btn-secondary" onClick={resetDemo}>Reset demo data</button>
        </div>
        <p className="md-muted md-small" role="status">{reset ? "Done. D-031 is back to v3, the resume card is cleared and My match is back to its defaults." : "Clears composer changes, your resume point and My match on this device."}</p>
      </section>
      <section className="md-panel md-ds-wide" aria-labelledby="md-set-more">
        <h2 id="md-set-more">More places to explore</h2>
        <ul className="md-more-links">
          <li><Link href="/workspace/activity"><Icon name="pulse" /> Demo activity</Link></li>
          <li><Link href="/producer/publish/D-031"><Icon name="inbox" /> Try demo publishing</Link></li>
          <li><Link href="/match/nbr-riv/insights"><Icon name="sparkle" /> How AI helps</Link></li>
          <li><Link href="/match/nbr-riv/tactical"><Icon name="pitch" /> Match analysis</Link></li>
          <li><Link href="/design-system"><Icon name="grid" /> Design guide (for developers)</Link></li>
          <li><Link href="/about"><Icon name="info" /> How facts are checked</Link></li>
        </ul>
      </section>
    </div>
  );
}
