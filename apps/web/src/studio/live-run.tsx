/**
 * Start a live run of the four specialists on Microsoft Foundry and watch it step by step.
 * Loaded only where an API with live runs sits behind /api (the Azure deployment). The
 * finished run is handed to AI insights, which draws it exactly like a recorded one.
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Step = { type: string; role?: string; outcome?: string; tool_calls?: unknown[]; passed?: boolean; round?: number; results?: { status: string }[] };
type Report = {
  run_id: string | null; status: "idle" | "running" | "completed" | "stopped" | "failed"; started_at: string | null;
  elapsed_ms: number | null; steps: Step[]; trace: unknown | null; error: string | null; next_run_in_s: number | null;
};

const ROLE: Record<string, string> = {
  tactical_analyst: "Tactical Analyst", narrative_composer: "Narrative Composer",
  editorial_reviewer: "Editorial Reviewer", audience_adapter: "Audience Adapter",
};

function describe(step: Step): string {
  if (step.type === "specialist") return `${ROLE[step.role ?? ""] ?? step.role} · ${step.outcome ?? "working"} · ${step.tool_calls?.length ?? 0} tool call${step.tool_calls?.length === 1 ? "" : "s"}`;
  if (step.type === "verification") {
    const passed = step.results?.filter((r) => r.status === "verified" || r.status === "supported_inference").length ?? 0;
    return `Verifier (code) · round ${step.round} · ${passed} of ${step.results?.length ?? 0} claims pass${step.passed ? "" : " · sent back"}`;
  }
  if (step.type === "rejected_output") return `${ROLE[step.role ?? ""] ?? "Specialist"} · answer rejected by the claim contract`;
  if (step.type === "withheld") return "Verifier (code) · claims withheld";
  return step.type;
}

export default function LiveRunPanel({ onTrace }: { onTrace: (trace: unknown) => void }) {
  const [report, setReport] = useState<Report | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const handed = useRef<string | null>(null);
  const deliver = useRef(onTrace);
  deliver.current = onTrace;

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/agents/run", { cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      const next = (await response.json()) as Report;
      setReport(next);
      setProblem(null);
      if ((next.status === "completed" || next.status === "stopped") && next.trace && handed.current !== next.run_id) {
        handed.current = next.run_id;
        deliver.current(next.trace);
      }
    } catch {
      setProblem("Live runs are not reachable from here right now.");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (report?.status !== "running") return;
    const id = window.setInterval(() => { void refresh(); }, 2000);
    return () => window.clearInterval(id);
  }, [report?.status, refresh]);

  const start = async () => {
    const response = await fetch("/api/agents/run", { method: "POST" });
    if (response.status === 429) {
      const body = (await response.json()) as { retry_after_s?: number };
      setProblem(`Live runs are spaced out to bound cost. The next one can start in about ${Math.ceil((body.retry_after_s ?? 60) / 60)} minutes.`);
    } else if (!response.ok && response.status !== 409) {
      setProblem("The run could not start.");
    }
    await refresh();
  };

  const running = report?.status === "running";
  const wait = report?.next_run_in_s ?? 0;
  return (
    <section className="md-panel md-live-run" aria-labelledby="md-live-run-title">
      <div className="md-panel-head">
        <h2 id="md-live-run-title">Run the four specialists live</h2>
        {running && <span className="md-chip md-chip-pending" role="status">Running · {Math.round((report?.elapsed_ms ?? 0) / 1000)} s</span>}
      </div>
      <p className="md-muted md-small">
        A fresh run on Microsoft Foundry for the 58′ goal: the same role-scoped tools, claim contract and verifier as the recorded run. It takes a few minutes (at most six). Runs make billable model calls, so they are five minutes apart and at most twelve a day.
      </p>
      <div className="md-btn-row">
        <button type="button" className="md-btn md-btn-primary" onClick={() => void start()} disabled={!report || running || wait > 0}>
          {running ? "Run in progress…" : wait > 0 ? `Next run in ${Math.ceil(wait / 60)} min` : "Start a live run"}
        </button>
      </div>
      {problem && <p className="md-small md-bad" role="alert">{problem}</p>}
      {report && report.steps.length > 0 && (
        <ol className="md-ticker" aria-label="Steps so far">
          {report.steps.map((step, i) => <li key={i}><span className="md-mono md-subtle">{i + 1}</span><span>{describe(step)}</span></li>)}
        </ol>
      )}
      {report?.status === "completed" && <p className="md-small md-ok" role="status">✓ Finished. The run is shown below.</p>}
      {report?.status === "stopped" && <p className="md-small md-muted" role="status">The run stopped before the audience versions: the verifier withheld the claims that never passed. Shown below.</p>}
      {report?.status === "failed" && <p className="md-small md-bad" role="alert">The run failed: {report.error}</p>}
    </section>
  );
}
