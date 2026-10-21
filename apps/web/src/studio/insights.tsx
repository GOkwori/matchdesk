/** AI insights: replays of the four-specialist workflow on the 58′ goal.
 *
 * The screen reads generated/*.view.json, compact views export_demo_data derives from
 * the recorded traces. generated/agent-trace.json is the run shown first: a recorded live Microsoft Foundry
 * run once there is one (scripts/record_agent_run.py --provider foundry). The
 * deterministic rehearsal (no model) is always available beside it, from
 * generated/agent-trace-rehearsal.json; it is the run in which the verifier sends a
 * misstated claim back. Every verdict in both comes from the real verifier and is
 * re-checked by the backend test suite.
 */
"use client";

import Link from "next/link";
import { useState } from "react";
import traceData from "./generated/agent-trace.view.json";
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
type Withheld = { type: "withheld"; round: number; claim_ids: string[]; reason: string };
type Step = Specialist | Verification | Rejected | Withheld;
type Role = "tactical_analyst" | "narrative_composer" | "editorial_reviewer" | "audience_adapter";
type Trace = {
  provider: { kind: "rehearsal" | "foundry"; label: string }; recorded_on?: string; status: string;
  steps: Step[]; verified_claims: Claim[];
  variants: { language: string; persona: string; text: string; claim_ids: string[] }[];
  totals: { specialist_turns: number; tool_calls: number; verification_rounds: number; tokens: number | null };
};

const shownTrace = traceData as unknown as Trace;
// When a live run is recorded it comes first; the rehearsal stays one click away and is
// fetched only when asked for, which keeps this page inside its JavaScript budget.
const hasLiveRun = shownTrace.provider.kind === "foundry";
const ROLE_NAME: Record<Role, string> = {
  tactical_analyst: "Tactical Analyst", narrative_composer: "Narrative Composer",
  editorial_reviewer: "Editorial Reviewer", audience_adapter: "Audience Adapter",
};
const LANGUAGE: Record<string, string> = { en: "English", es: "Español", fr: "Français" };
const PERSONA: Record<string, string> = { analyst: "Analyst", casual_fan: "Fan", broadcast_caption: "Caption" };

type Decision = "open" | "kept" | "dismissed";

function args(call: ToolCall): string {
  return Object.entries(call.args).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("|") : String(v)}`).join(", ");
}

function result(call: ToolCall): string {
  if (typeof call.result === "number") return String(call.result);
  if (Array.isArray(call.result)) return `${call.result.length} events`;
  if (call.result && typeof call.result === "object") {
    const r = call.result as Record<string, unknown>;
    if (typeof r.events === "number") return `${r.events} events`;
    return [r.event_id ?? r.claim_id, r.type ?? r.status, r.clock].filter(Boolean).join(" · ");
  }
  return "none";
}

function percent(value: number | null): string {
  return value == null ? "—" : value <= 1 ? `${(value * 100).toFixed(2)}%` : String(value);
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** Why an attempt failed, in plain words: the host classifies it, the model does not. */
function failureNote(failures: string[]): string | null {
  if (!failures.length) return null;
  const rejected = failures.filter((f) => f === "retryable_failure").length;
  const late = failures.filter((f) => f === "timeout").length;
  const parts = [];
  if (rejected) parts.push(`${rejected === 1 ? "An answer was" : `${rejected} answers were`} rejected by the claim contract`);
  if (late) parts.push(`${late === 1 ? "an attempt" : `${late} attempts`} ran past the host deadline`);
  return `${parts.join("; ")}, so the host retried. Nothing from a rejected answer was used.`.replace(/^./, (c) => c.toUpperCase());
}

function SpecialistCard({ step, revision, variants }: { step: Specialist; revision: boolean; variants: number }) {
  const draft = step.role === "narrative_composer" && revision;
  const note = failureNote(step.failures);
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
      {note && <p className="md-muted md-small">{note}</p>}
      {step.content && step.role !== "audience_adapter" && <p>{step.content.split("\n")[0]}</p>}
      {step.content.includes("[rehearsal]") && <p className="md-muted md-small">{step.content.split("\n").find((l) => l.startsWith("[rehearsal]"))}</p>}
      {step.claims.length > 0 && (
        <ul className="md-trace-claims" aria-label={`Claims from ${ROLE_NAME[step.role]}`}>
          {step.claims.map((c) => <li key={c.claim_id}><span className="md-mono">{c.claim_id}</span> {c.text}</li>)}
        </ul>
      )}
      {step.role === "audience_adapter" && <p>{variants} versions, each citing only verified claims.</p>}
      {step.tool_calls.length > 0 && (
        <details className="md-trace-tools">
          <summary>Tool calls</summary>
          <ol>{step.tool_calls.map((call, i) => <li key={i}><code>{call.tool}({args(call)})</code> → {result(call)}</li>)}</ol>
        </details>
      )}
    </li>
  );
}

/** What the log recorded against what the claim said, in the claim's own unit. */
function mismatch(r: VerdictRow): string {
  if (r.query_id === "event-sequence-gap-v1") return `The log records ${r.observed} seconds; the claim said ${r.expected}.`;
  return `Observed ${percent(r.observed)}, claimed ${percent(r.expected)}.`;
}

function VerificationCard({ step, last }: { step: Verification; last: boolean }) {
  const failedText = last
    ? "A claim failed when recomputed from the event log, and no revision round was left."
    : "A claim failed when recomputed from the event log, so the workflow sent the draft back to the composer.";
  return (
    <li className={`md-insight ${step.passed ? "md-insight-kept" : "md-trace-failed"}`}>
      <span className="md-insight-top">
        <span className="md-eyebrow">Verifier · round {step.round}</span>
        <VerdictChip verdict={step.passed ? "verified" : "failed"} label={step.passed ? "Passed" : last ? "Failed" : "Sent back"} />
      </span>
      <p>{step.passed ? "Every claim recomputed from the event log. Code, not an agent, made this call." : failedText}</p>
      <ul className="md-trace-claims" aria-label={`Verification round ${step.round}`}>
        {step.results.map((r) => (
          <li key={r.claim_id}>
            <span className="md-mono">{r.claim_id}</span> <VerdictChip verdict={toVerdict(r.status)} />
            <span className="md-small"> {r.text}</span>
            {r.status === "needs_revision" && r.observed != null && <span className="md-muted md-small"> {mismatch(r)}</span>}
          </li>
        ))}
      </ul>
    </li>
  );
}

export function InsightsBody() {
  const [rehearsal, setRehearsal] = useState<Trace | null>(null);
  const [showRehearsal, setShowRehearsal] = useState(false);
  const pickRehearsal = async () => {
    if (!rehearsal) {
      const loaded = await import("./generated/agent-trace-rehearsal.view.json");
      setRehearsal(loaded.default as unknown as Trace);
    }
    setShowRehearsal(true);
  };
  const current = showRehearsal && rehearsal ? rehearsal : shownTrace;
  return (
    <>
      {hasLiveRun && (
        <div role="group" aria-label="Which run" className="md-seg">
          <span className="md-seg-label">Which run</span>
          <button type="button" aria-pressed={!showRehearsal} onClick={() => setShowRehearsal(false)}>Recorded live run</button>
          <button type="button" aria-pressed={showRehearsal} onClick={pickRehearsal}>Rehearsal</button>
        </div>
      )}
      <RunView key={current === shownTrace ? "shown" : "rehearsal"} trace={current} />
    </>
  );
}

function RunView({ trace }: { trace: Trace }) {
  const live = trace.provider.kind === "foundry";
  const specialists = trace.steps.filter((s): s is Specialist => s.type === "specialist");
  const rounds = trace.steps.filter((s): s is Verification => s.type === "verification");
  const [shown, setShown] = useState(trace.steps.length);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const open = trace.verified_claims.filter((c) => (decisions[c.claim_id] ?? "open") === "open").length;
  const decide = (id: string, d: Decision) => setDecisions((s) => ({ ...s, [id]: d }));
  const stepping = shown < trace.steps.length;
  const pipeline = [
    { name: "Tactical Analyst", detail: `${specialists[0]?.tool_calls.length ?? 0} tool calls` },
    { name: "Narrative Composer", detail: plural(specialists.filter((s) => s.role === "narrative_composer").length, "draft") },
    { name: "Editorial Reviewer", detail: plural(specialists.filter((s) => s.role === "editorial_reviewer").length, "review") },
    { name: "Verifier (code)", detail: `${rounds.length} round${rounds.length === 1 ? "" : "s"}` },
    { name: "Audience Adapter", detail: `${trace.variants.length} versions` },
  ];

  return (
    <>
      <div className={`md-banner ${live ? "md-banner-success" : "md-banner-info"}`} role="note">
        <span className="md-banner-icon" aria-hidden="true">{live ? "✓" : "i"}</span>
        <strong>{live ? "Recorded live run" : "Rehearsal run"}</strong>
        <span>{trace.provider.label}{trace.recorded_on ? ` · ${trace.recorded_on}` : ""}. {plural(trace.totals.specialist_turns, "specialist turn")}, {plural(trace.totals.tool_calls, "tool call")}, {plural(trace.totals.verification_rounds, "verification round")}{trace.totals.tokens != null ? `, ${trace.totals.tokens.toLocaleString("en-GB")} tokens` : ""}.</span>
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
              step.type === "specialist"
                ? <SpecialistCard key={i} step={step} variants={trace.variants.length}
                    revision={specialists.slice(0, specialists.indexOf(step)).some((s) => s.role === "narrative_composer")} />
                : step.type === "verification" ? <VerificationCard key={i} step={step} last={trace.steps[i + 1]?.type === "withheld"} />
                  : step.type === "withheld"
                    ? <li key={i} className="md-insight md-trace-failed"><span className="md-insight-top"><span className="md-eyebrow">Verifier · withheld</span><VerdictChip verdict="failed" label="Withheld" /></span><p>Revision ran out, so code withheld {step.claim_ids.length === 1 ? "the claim" : `${step.claim_ids.length} claims`} that never verified ({step.claim_ids.join(", ")}). Only verified claims go on to the audience versions.</p></li>
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
