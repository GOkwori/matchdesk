/** Isolated synthetic judge experience; no authenticated producer actions. */
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import "./judge.css";

type JudgeSession = {
  session_id: string; token: string; generation: number;
  ttl_seconds: number; mode: "synthetic_local_read_only";
};
type Claim = { status: string; observed: number; expected: number; evidence_digest: string };
type Variant = {
  output_id: string; language: string; persona: string; text: string;
  semantic_language_review: "NOT_RUN"; publishable: false;
};
type JudgeReplay = {
  mode: "synthetic_local_read_only"; scenario: string; match_id: string;
  source_events: Array<{ event_id: string; type: string; period: number; match_clock_ms: number }>;
  detected_moments: Array<{ moment_id: string; kind: string; event_ids: string[] }>;
  scripted_specialist_proposal: { runtime: string; text: string; claim_id: string };
  registered_metric: { id: string; observed: number };
  verified_claim: Claim; controlled_error: { status: string; published: false };
  producer_review: { status: string; authenticated: false; approval_enabled: false; publication_enabled: false };
  audience_variants: Variant[];
  human_language_review: "NOT_RUN"; live_model_executed: false; real_publication: false;
};
type ReplayEnvelope = { session_id: string; generation: number; replay: JudgeReplay };

/** Validate untrusted API responses before exposing their contents to the screen. */
function isSession(value: unknown): value is JudgeSession {
  if (!value || typeof value !== "object") return false;
  const s = value as Record<string, unknown>;
  return typeof s.session_id === "string" && /^[A-Za-z0-9_-]{32}$/.test(s.session_id) &&
    typeof s.token === "string" && /^[A-Za-z0-9_-]{43}$/.test(s.token) &&
    Number.isSafeInteger(s.generation) && s.generation as number > 0 &&
    s.ttl_seconds === 900 && s.mode === "synthetic_local_read_only";
}

/** Reject malformed or falsely authoritative fixture results without rendering. */
function isReplay(value: unknown): value is ReplayEnvelope {
  if (!value || typeof value !== "object") return false;
  const data = value as Record<string, unknown>;
  if (!data.replay || typeof data.replay !== "object") return false;
  const r = data.replay as Record<string, unknown>;
  const claim = r.verified_claim as Record<string, unknown> | undefined;
  const error = r.controlled_error as Record<string, unknown> | undefined;
  const review = r.producer_review as Record<string, unknown> | undefined;
  return typeof data.session_id === "string" &&
    Number.isSafeInteger(data.generation) &&
    r.mode === "synthetic_local_read_only" &&
    typeof r.match_id === "string" &&
    Array.isArray(r.source_events) && r.source_events.length > 0 &&
    Array.isArray(r.detected_moments) &&
    Array.isArray(r.audience_variants) && r.audience_variants.length === 9 &&
    r.audience_variants.every((v: Variant) => v && v.publishable === false && v.semantic_language_review === "NOT_RUN") &&
    claim?.status === "verified" && typeof claim.evidence_digest === "string" &&
    error?.status === "needs_revision" && error.published === false &&
    review?.authenticated === false && review.approval_enabled === false &&
    review.publication_enabled === false && r.human_language_review === "NOT_RUN" &&
    r.live_model_executed === false && r.real_publication === false;
}

/** Keep bearer tokens in volatile component memory, never in URLs or storage. */
export default function JudgeWorkbench() {
  const [session, setSession] = useState<JudgeSession | null>(null);
  const [report, setReport] = useState<JudgeReplay | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "info" | "success" | "error"; text: string }>({
    kind: "info", text: "Start a disposable synthetic session to inspect the evidence trail.",
  });
  const revision = useRef(0);
  const sessionRef = useRef<JudgeSession | null>(null);
  const gate = useRef(false);

  useEffect(() => {
    // Do not allow a late response to rehydrate a session after page disposal.
    return () => { revision.current++; sessionRef.current = null; };
  }, []);

  /** All requests carry one disposable capability and no cookies. */
  async function request(path: string, method: "GET" | "POST" | "DELETE", token?: string): Promise<unknown> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8500);
    try {
      const response = await fetch("/api/judge-local" + path, {
        method,
        headers: {
          ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: "Bearer " + token } : {}),
        },
        ...(method === "POST" ? { body: "{}" } : {}),
        credentials: "omit",
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(
        response.status === 503 ? "Local judge host is unavailable. Start the opt-in Python host." :
          response.status === 429 ? "Eight sessions are already active. Try again after expiry." :
            "The session was denied or expired. Start a fresh synthetic run.",
      );
      if (response.status === 204) return null;
      return response.json() as Promise<unknown>;
    } finally {
      clearTimeout(timeout);
    }
  }

  /** Serialize actions so reset, close and replay cannot race the UI. */
  async function execute(action: "start" | "replay" | "reset" | "close") {
    if (gate.current) return;
    gate.current = true;
    setBusy(true);
    const currentRevision = ++revision.current;
    const live = sessionRef.current;
    try {
      if (action === "start") {
        if (live) throw new Error("Close or reset the current session first.");
        const created = await request("/sessions", "POST");
        if (!isSession(created)) throw new Error("The local host returned an invalid session.");
        if (revision.current !== currentRevision) return;
        sessionRef.current = created;
        setSession(created);
        const initial = await request("/sessions/" + created.session_id + "/replay", "GET", created.token);
        if (!isReplay(initial) || initial.session_id !== created.session_id ||
          initial.generation !== created.generation) {
          throw new Error("The synthetic evidence contract could not be verified.");
        }
        if (revision.current !== currentRevision) return;
        setReport(initial.replay);
        setNotice({ kind: "success", text: "Deterministic replay qualified. No live data, model or publication." });
      } else {
        if (!live) throw new Error("Start a local judge session first.");
        const prefix = "/sessions/" + live.session_id;
        if (action === "replay") {
          const result = await request(prefix + "/replay", "GET", live.token);
          if (!isReplay(result) || result.session_id !== live.session_id ||
            result.generation !== live.generation) throw new Error("Invalid synthetic replay.");
          if (revision.current !== currentRevision) return;
          setReport(result.replay);
          setNotice({ kind: "success", text: "Replay recomputed from the same synthetic fixture." });
        } else if (action === "reset") {
          const result = await request(prefix + "/reset", "POST", live.token);
          if (!isSession(result) || result.session_id !== live.session_id ||
            result.generation !== live.generation + 1 || result.token === live.token) {
            throw new Error("Reset response did not prove token rotation.");
          }
          if (revision.current !== currentRevision) return;
          sessionRef.current = result;
          setSession(result);
          setReport(null);
          setNotice({ kind: "info", text: "Previous token revoked. Run replay to inspect the new generation." });
        } else {
          await request(prefix, "DELETE", live.token);
          if (revision.current !== currentRevision) return;
          sessionRef.current = null;
          setSession(null);
          setReport(null);
          setNotice({ kind: "info", text: "Session revoked. You may start another synthetic run." });
        }
      }
    } catch (error) {
      if (revision.current === currentRevision) {
        // A failed reset may have revoked the prior token; require a new run.
        sessionRef.current = null;
        setSession(null);
        setReport(null);
        setNotice({
          kind: "error",
          text: error instanceof Error ? error.message : "Local judge request was not completed.",
        });
      }
    } finally {
      if (revision.current === currentRevision) { gate.current = false; setBusy(false); }
    }
  }

  return <main className="judge-main">
    <header className="judge-top"><Link href="/" className="judge-brand">MATCHDESK<span> / SUNSET STUDIO</span></Link>
      <span className="judge-mode">LOCAL · SYNTHETIC · READ ONLY</span></header>
    <div className="judge-hero">
      <p className="judge-eyebrow">DEMONSTRATION WORKBENCH · PHASE 5</p>
      <h1>See the evidence.<br /><em>Challenge the claim.</em></h1>
      <p>Follow one invented football moment from source events to verified commentary and nine audience variations. The deliberate false claim is rejected; nothing can be approved or published here.</p>
      <div className="judge-badges"><span>Deterministic fixture</span><span>15-minute sessions</span><span>No live AI</span></div>
    </div>
    <section className="judge-controls" aria-label="Judge session controls">
      <div><h2>Session controls</h2><p>{session ? "Generation " + session.generation + " · Expires 15 minutes after issuance" : "No active browser session"}</p></div>
      <div className="judge-actions">
        <button onClick={() => void execute("start")} disabled={busy || !!session}>Start demo</button>
        <button className="judge-secondary" onClick={() => void execute("replay")} disabled={busy || !session}>Replay</button>
        <button className="judge-secondary" onClick={() => void execute("reset")} disabled={busy || !session}>Reset</button>
        <button className="judge-danger" onClick={() => void execute("close")} disabled={busy || !session}>End session</button>
      </div>
    </section>
    <div className={"judge-notice judge-" + notice.kind} role={notice.kind === "error" ? "alert" : "status"} aria-live="polite">
      <strong>{notice.kind === "error" ? "Action required" : notice.kind === "success" ? "Verified run" : "Information"}</strong>
      <p>{notice.text}</p>
    </div>
    {report ? <>
      <section className="judge-grid" aria-label="Verified match journey">
        <article className="judge-card"><div className="judge-heading"><span>01 / SOURCE</span><strong>{report.source_events.length} events</strong></div>
          <h2>Match evidence</h2><p className="judge-description">Recorded synthetic events are the sole source of this replay.</p>
          <div className="judge-events">{report.source_events.slice(0, 5).map((e) =>
            <p key={e.event_id}><span>{e.period === 1 ? "1H" : "2H"} · {Math.floor(e.match_clock_ms / 60000)}&prime;</span><strong>{e.type}</strong><small>{e.event_id}</small></p>)}</div>
          <p className="judge-foot">Match ID: <code>{report.match_id}</code> · Fixture seed is fixed.</p>
        </article>
        <article className="judge-card"><div className="judge-heading"><span>02 / DETECTION</span><strong>{report.detected_moments.length} moments</strong></div>
          <h2>What matters</h2><p className="judge-description">Deterministic detection references the original event IDs.</p>
          {report.detected_moments.slice(0, 5).map((m) =>
            <div className="judge-moment" key={m.moment_id}><strong>{m.kind.replaceAll("_", " ")}</strong><small>{m.event_ids.join(", ")}</small></div>)}
        </article>
        <article className="judge-card judge-emphasis"><div className="judge-heading"><span>03 / VERIFICATION</span><strong className="judge-ok">EVIDENCE-BOUND</strong></div>
          <h2>Can we say this?</h2><blockquote>{report.scripted_specialist_proposal.text}</blockquote>
          <p className="judge-description">Scripted illustrative proposal, not a live agent execution.</p>
          <dl><dt>Recorded metric</dt><dd>{report.registered_metric.id}: {report.registered_metric.observed}</dd>
            <dt>Claim verdict</dt><dd className="judge-ok">{report.verified_claim.status}</dd>
            <dt>False claim test</dt><dd className="judge-fail">{report.controlled_error.status}</dd></dl>
          <p className="judge-foot">Evidence SHA-256 <code>{report.verified_claim.evidence_digest}</code></p>
        </article>
      </section>
      <section className="judge-lower">
        <article className="judge-card"><div className="judge-heading"><span>04 / PRODUCER DESK</span><strong>REVIEW ONLY</strong></div>
          <h2>Human authority remains closed</h2><p>The review presentation is inspectable; there is no authenticated producer, approval action, or publication path.</p>
          <div className="judge-lock"><strong>Approval disabled</strong><span>Publication disabled</span></div>
          <p className="judge-foot">Producer status: {report.producer_review.status}</p>
        </article>
        <article className="judge-card"><div className="judge-heading"><span>05 / AUDIENCE</span><strong>9 VARIANTS</strong></div>
          <h2>Different formats, same evidence</h2>
          <div className="judge-variants">{report.audience_variants.map((v) =>
            <div key={v.output_id}><span>{v.language.toUpperCase()} · {v.persona.replaceAll("_", " ")}</span>
              <p>{v.text}</p><small>Scripted · language review not run · not publishable</small></div>)}</div>
        </article>
      </section>
    </> : <section className="judge-empty" aria-label="Awaiting synthetic replay">
      <span aria-hidden="true">◎</span><h2>No active replay evidence</h2>
      <p>Start the demo, or replay after a token reset. Nothing shown here is a live match.</p>
    </section>}
    <footer className="judge-footer">MatchDesk · Synthetic-only competition workbench · No real data, real producer approval, or broadcast publishing · <Link href="/">Back to Sunset Studio</Link></footer>
  </main>;
}
