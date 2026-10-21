/** AI insights: a replay of one recorded run of the four-specialist workflow on the 58′ goal.
 *
 * Everything here comes from generated/agent-trace.json, written by
 * scripts/record_agent_run.py. The trace says which provider produced it: the
 * deterministic rehearsal (no model) or a recorded live Microsoft Foundry run. Verdicts in
 * it come from the real verifier and are re-checked by the backend test suite.
 */
"use client";

import Link from "next/link";
import { useState } from "react";
import traceData from "./generated/agent-trace.json";
import { Icon } from "./icons";
import { VerdictChip } from "./ui";
import { TourStep } from "./shell";
import { STORY_SLUG, toVerdict } from "./data";
import type { Claim, Status } from "./verifier";

type ToolCall = { tool: string; args: Record<string, unknown>; result: unknown };
type Specialist = {
  type: "specialist"; role: Role; attempts: number; failures: string[]; outcome: string;
  tool_calls: ToolCall[]; claims: Claim[]; content: string; tokens: number | null; duration_ms: number | null;
};
type VerdictRow = { claim_id: string; text: string; status: Status; query_id: string; reason: string; expected: number | null; observed: number | null };
type Verification = { type: "verification"; round: number; passed: boolean; results: VerdictRow[] };
type Rejected = { type: "rejected_output"; role: Role; reason: string };
type Step = Specialist | Verification | Rejected;
type Role = "tactical_analyst" | "narrative_composer" | "editorial_reviewer" | "audience_adapter";
type Trace = {
  provider: { kind: "rehearsal" | "foundry"; label: string }; recorded_on?: string; status: string;
  steps: Step[]; verified_claims: Claim[];
  variants: { language: string; persona: string; text: string; claim_ids: string[] }[];
  totals: { specialist_turns: number; tool_calls: number; verification_rounds: number; tokens: number | null };
};

const trace = traceData as unknown as Trace;
const ROLE_NAME: Record<Role, string> = {
  tactical_analyst: "Tactical Analyst", narrative_composer: "Narrative Composer",
  editorial_reviewer: "Editorial Reviewer", audience_adapter: "Audience Adapter",
};
const LANGUAGE: Record<string, string> = { en: "English", es: "Español", fr: "Français" };
const PERSONA: Record<string, string> = { analyst: "Analyst", casual_fan: "Fan", broadcast_caption: "Caption" };
const live = trace.provider.kind === "foundry";
const specialists = trace.steps.filter((s): s is Specialist => s.type === "specialist");
const rounds = trace.steps.filter((s): s is Verification => s.type === "verification");

type Decision = "open" | "kept" | "dismissed";

function args(call: ToolCall): string {
  return Object.entries(call.args).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("|") : String(v)}`).join(", ");
}

function result(call: ToolCall): string {
  if (typeof call.result === "number") return String(call.result);
  if (Array.isArray(call.result)) return `${call.result.length} events`;
  if (call.result && typeof call.result === "object") {
    const r = call.result as Record<string, unknown>;
    return [r.event_id ?? r.claim_id, r.type ?? r.status, r.clock].filter(Boolean).join(" · ");
  }
  return "none";
}

function percent(value: number | null): string {
  return value == null ? "—" : value <= 1 ? `${(value * 100).toFixed(2)}%` : String(value);
}

function SpecialistCard({ step, index }: { step: Specialist; index: number }) {
  const draft = step.role === "narrative_composer" && specialists.slice(0, index).some((s) => s.role === "narrative_composer");
  return (
    <li className="md-insight">
      <span className="md-insight-top">
        <span className="md-eyebrow">{ROLE_NAME[step.role]}{draft ? " · revision" : ""}</span>
        <span className="md-muted md-small">
          {step.tool_calls.length} tool call{step.tool_calls.length === 1 ? "" : "s"}
          {step.tokens != null ? ` · ${step.tokens.toLocaleString("en-GB")} tokens` : ""}
          {step.failures.length ? ` · ${step.failures.length} failed attempt${step.failures.length === 1 ? "" : "s"}` : ""}
        </span>
      </span>
      {step.content && step.role !== "audience_adapter" && <p>{step.content.split("\n")[0]}</p>}
      {step.content.includes("[rehearsal]") && <p className="md-muted md-small">{step.content.split("\n").find((l) => l.startsWith("[rehearsal]"))}</p>}
      {step.claims.length > 0 && (
        <ul className="md-trace-claims" aria-label={`Claims from ${ROLE_NAME[step.role]}`}>
          {step.claims.map((c) => <li key={c.claim_id}><span className="md-mono">{c.claim_id}</span> {c.text}</li>)}
        </ul>
      )}
      {step.role === "audience_adapter" && <p>{trace.variants.length} versions, each citing only verified claims.</p>}
      {step.tool_calls.length > 0 && (
        <details className="md-trace-tools">
          <summary>Tool calls</summary>
          <ol>{step.tool_calls.map((call, i) => <li key={i}><code>{call.tool}({args(call)})</code> → {result(call)}</li>)}</ol>
        </details>
      )}
    </li>
  );
}

function VerificationCard({ step }: { step: Verification }) {
  return (
    <li className={`md-insight ${step.passed ? "md-insight-kept" : "md-trace-failed"}`}>
      <span className="md-insight-top">
        <span className="md-eyebrow">Verifier · round {step.round}</span>
        <VerdictChip verdict={step.passed ? "verified" : "failed"} label={step.passed ? "Passed" : "Sent back"} />
      </span>
      <p>{step.passed ? "Every claim recomputed from the event log. Code, not an agent, made this call." : "A claim failed when recomputed from the event log, so the workflow sent the draft back to the composer."}</p>
      <ul className="md-trace-claims" aria-label={`Verification round ${step.round}`}>
        {step.results.map((r) => (
          <li key={r.claim_id}>
            <span className="md-mono">{r.claim_id}</span> <VerdictChip verdict={toVerdict(r.status)} />
            <span className="md-small"> {r.text}</span>
            {r.status === "needs_revision" && r.observed != null && <span className="md-muted md-small"> Observed {percent(r.observed)}, claimed {percent(r.expected)}.</span>}
          </li>
        ))}
      </ul>
    </li>
  );
}

export function InsightsBody() {
  const [shown, setShown] = useState(trace.steps.length);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const open = trace.verified_claims.filter((c) => (decisions[c.claim_id] ?? "open") === "open").length;
  const decide = (id: string, d: Decision) => setDecisions((s) => ({ ...s, [id]: d }));
  const stepping = shown < trace.steps.length;
  const pipeline = [
    { name: "Tactical Analyst", detail: `${specialists[0]?.tool_calls.length ?? 0} tool calls` },
    { name: "Narrative Composer", detail: `${specialists.filter((s) => s.role === "narrative_composer").length} drafts` },
    { name: "Editorial Reviewer", detail: `${specialists.filter((s) => s.role === "editorial_reviewer").length} reviews` },
    { name: "Verifier (code)", detail: `${rounds.length} round${rounds.length === 1 ? "" : "s"}` },
    { name: "Audience Adapter", detail: `${trace.variants.length} versions` },
  ];

  return (
    <>
      <div className={`md-banner ${live ? "md-banner-success" : "md-banner-info"}`} role="note">
        <span className="md-banner-icon" aria-hidden="true">{live ? "✓" : "i"}</span>
        <strong>{live ? "Recorded live run" : "Rehearsal run"}</strong>
        <span>{trace.provider.label}{trace.recorded_on ? ` · ${trace.recorded_on}` : ""}. {trace.totals.specialist_turns} specialist turns, {trace.totals.tool_calls} tool calls, {trace.totals.verification_rounds} verification rounds{trace.totals.tokens != null ? `, ${trace.totals.tokens.toLocaleString("en-GB")} tokens` : ""}.</span>
      </div>
      <ol className="md-roles" aria-label="Workflow">
        {pipeline.map((p) => (
          <li key={p.name} className="md-role-done">
            <span className="md-role-num" aria-hidden="true">✓</span>
            <span><strong>{p.name}</strong><span className="md-muted md-small">{p.detail}</span></span>
          </li>
        ))}
        <li className="md-role-human">
          <span className="md-role-num" aria-hidden="true"><Icon name="pen" size={14} /></span>
          <span><strong>Human decision</strong><span className="md-muted md-small">You decide</span></span>
        </li>
      </ol>
      <div className="md-split">
        <section className="md-panel md-split-main" aria-labelledby="md-run-title">
          <div className="md-panel-head">
            <h2 id="md-run-title">How the run went</h2>
            <span className="md-btn-row">
              {stepping
                ? <><button type="button" className="md-mini-btn" onClick={() => setShown((n) => Math.min(n + 1, trace.steps.length))}>Next step</button><button type="button" className="md-mini-btn" onClick={() => setShown(trace.steps.length)}>Show all</button></>
                : <button type="button" className="md-mini-btn" onClick={() => setShown(1)}>Replay step by step</button>}
            </span>
          </div>
          <p className="md-muted md-small" aria-live="polite">Step {Math.min(shown, trace.steps.length)} of {trace.steps.length}</p>
          <TourStep step={3} />
          <ol className="md-insight-list">
            {trace.steps.slice(0, shown).map((step, i) =>
              step.type === "specialist" ? <SpecialistCard key={i} step={step} index={specialists.indexOf(step)} />
                : step.type === "verification" ? <VerificationCard key={i} step={step} />
                  : <li key={i} className="md-insight md-trace-failed"><span className="md-eyebrow">{ROLE_NAME[step.role]} · output rejected</span><p>{step.reason}</p></li>)}
          </ol>
        </section>
        <aside className="md-split-side md-stack" aria-label="What reaches the producer">
          <section className="md-panel" aria-labelledby="md-keep-title">
            <div className="md-panel-head"><h2 id="md-keep-title">Verified claims for you</h2><span className="md-muted" aria-live="polite">{open} left to review</span></div>
            <ul className="md-insight-list">
              {trace.verified_claims.map((c) => {
                const d = decisions[c.claim_id] ?? "open";
                return (
                  <li key={c.claim_id} className={`md-insight md-insight-${d}`}>
                    <span className="md-insight-top"><span className="md-mono">{c.claim_id}</span><VerdictChip verdict="verified" /></span>
                    <span>{c.text}</span>
                    <span className="md-btn-row">
                      {d === "open"
                        ? <><button type="button" className="md-mini-btn" onClick={() => decide(c.claim_id, "kept")}>Keep for producer</button><button type="button" className="md-mini-btn" onClick={() => decide(c.claim_id, "dismissed")}>Dismiss</button></>
                        : <span className="md-decision">{d === "kept" ? "Kept for producer" : "Dismissed"} · <button type="button" className="md-text-btn" onClick={() => decide(c.claim_id, "open")}>Undo</button></span>}
                    </span>
                  </li>
                );
              })}
            </ul>
          </section>
          <section className="md-panel" aria-labelledby="md-aud-title">
            <span className="md-eyebrow">Audience Adapter</span>
            <h2 id="md-aud-title" className="md-sel-title">{trace.variants.length} versions of the 58′ story</h2>
            <ul className="md-trace-claims">
              {trace.variants.filter((v) => v.persona === "casual_fan").map((v) => <li key={v.language} lang={v.language}><strong>{LANGUAGE[v.language]} · {PERSONA[v.persona]}</strong> {v.text}</li>)}
            </ul>
            <p className="md-muted md-small">Language review has not been run. Nothing is published without a producer.</p>
            <Link href={`/story/${STORY_SLUG}`} className="md-btn md-btn-secondary">Preview the fan story</Link>
          </section>
        </aside>
      </div>
    </>
  );
}
