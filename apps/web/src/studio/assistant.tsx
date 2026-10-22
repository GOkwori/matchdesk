/** Ask MatchDesk: a question box that guides people round the studio and answers about the match with proof. */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { useViewer } from "./viewer";
import { answerPlan, describePlan, needsEvents, parseQuestion, SUGGESTIONS, validatePlan, type Answer, type CheckedLine, type MatchContext, type Plan } from "./ask";
import { expandLog, type CompactLog, type Status } from "./verifier";
import exportData from "./generated/nbr-riv.json";

const NAMES = exportData.display_names as Record<string, string>;
const TEAMS: Record<string, string> = { nbr: NAMES.nbr ?? "Northbridge", riv: NAMES.riv ?? "Riverside" };
const MAX_QUESTION = 300;
const PLANNER_TIMEOUT_MS = 8000;

type Entry = { id: number; question: string; answer: Answer; via: "rules" | "foundry"; readAs?: string };
const LOOKUP = { names: NAMES, teams: TEAMS };

const STATUS: Record<Status, { label: string; tone: string }> = {
  verified: { label: "Verified", tone: "verified" },
  supported_inference: { label: "Supported inference", tone: "pending" },
  needs_revision: { label: "Not verified", tone: "failed" },
  blocked: { label: "Blocked", tone: "failed" },
};

/** Ask the optional Foundry planner to read a question the rules could not. Null when unavailable. */
async function planWithFoundry(question: string): Promise<unknown | null> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), PLANNER_TIMEOUT_MS);
  try {
    const response = await fetch("/api/assistant/plan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
      credentials: "same-origin",
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { plan?: unknown };
    return body.plan ?? null;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timer);
  }
}

/** The verifier's outcome in plain words; the technical reason stays one click deeper. */
function plainResult(line: CheckedLine): string {
  const { status, reason } = line.result;
  if (status === "verified") {
    return line.claim.fact ? "The recorded goal event names this scorer." : "Recalculated from the events: the figure in the sentence matches.";
  }
  return reason;
}

function Line({ line }: { line: CheckedLine }) {
  const status = STATUS[line.result.status];
  const a = line.claim.assertion;
  const cited = line.claim.evidence_event_ids;
  return (
    <li className="md-ask-line">
      <span className={`md-chip md-chip-${status.tone}`}>{status.label}</span>
      <span className="md-ask-sentence">{line.claim.text}</span>
      <details className="md-ask-proof">
        <summary>How this was checked</summary>
        <dl>
          {a && <><dt>Metric</dt><dd><code>{a.metric}</code>, recalculated from the event log</dd></>}
          {line.claim.fact && <><dt>Event check</dt><dd><code>{line.claim.fact.query}</code> on <code>{line.claim.fact.event_id}</code></dd></>}
          {a && line.result.observed != null && <><dt>Recalculated</dt><dd>{line.result.observed}</dd></>}
          <dt>Result</dt><dd>{plainResult(line)}</dd>
          <dt>Cited events</dt><dd>{cited.length ? cited.slice(0, 8).join(", ") + (cited.length > 8 ? ` and ${cited.length - 8} more` : "") : "All events in the window"}</dd>
          <dt>Check</dt><dd><code>{line.result.query_id}</code>: {line.result.reason}</dd>
        </dl>
      </details>
    </li>
  );
}

function Reply({ entry, onLink }: { entry: Entry; onLink: () => void }) {
  const { answer } = entry;
  if (answer.kind === "match") {
    return (
      <div className="md-ask-answer">
        <p className="md-ask-scope">{answer.scope}</p>
        {entry.via === "foundry" && <p className="md-ask-via">Question read by Azure AI Foundry as: {entry.readAs}</p>}
        <ul className="md-ask-lines">{answer.lines.map((line) => <Line key={line.claim.claim_id} line={line} />)}</ul>
        {answer.derived && <p className="md-ask-derived"><span className="md-visually-hidden">Conclusion: </span>{answer.derived} <span className="md-ask-muted">(from the checked figures above)</span></p>}
        {answer.note && <p className="md-ask-muted">{answer.note}</p>}
      </div>
    );
  }
  return (
    <div className="md-ask-answer">
      <p>{answer.text}</p>
      {answer.kind === "help" && answer.link && (
        <Link className="md-ask-link" href={answer.link.href} onClick={onLink}>{answer.link.label} <Icon name="arrow" size={16} /></Link>
      )}
    </div>
  );
}

export function Assistant({ request }: { request: { id: number; question: string | null } }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const [ctx, setCtx] = useState<MatchContext | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [pending, setPending] = useState<string | null>(null);
  const pathname = usePathname();
  const { viewer } = useViewer();
  const suggestions = viewer.player ? [`How did ${NAMES[viewer.player] ?? viewer.player} play?`, ...SUGGESTIONS.slice(0, -1)] : SUGGESTIONS;

  useEffect(() => {
    let live = true;
    import("./generated/nbr-riv-events.json").then((module) => {
      if (!live) return;
      setCtx({
        events: expandLog(module.default as unknown as CompactLog),
        names: NAMES,
        teams: TEAMS,
        replayEndMs: exportData.replay_end_ms,
        matchId: exportData.match_id,
      });
    }).catch(() => { if (live) setLoadFailed(true); });
    return () => { live = false; };
  }, []);

  const add = useCallback((entry: Omit<Entry, "id">) => {
    setEntries((current) => [...current, { ...entry, id: (current.at(-1)?.id ?? 0) + 1 }].slice(-12));
  }, []);

  const submit = useCallback(async (raw: string) => {
    const text = raw.trim().slice(0, MAX_QUESTION);
    if (!text || busyRef.current) return;
    setQuestion("");
    input.current?.focus();
    let plan: Plan = parseQuestion(text, LOOKUP);
    let via: Entry["via"] = "rules";
    if (plan.intent === "unknown") {
      busyRef.current = true;
      setBusy(true);
      const proposed = await planWithFoundry(text);
      busyRef.current = false;
      setBusy(false);
      const checked = proposed === null ? null : validatePlan(proposed, LOOKUP);
      if (checked && checked.intent !== "unknown") { plan = checked; via = "foundry"; }
    }
    if (needsEvents(plan) && !ctx) {
      if (loadFailed) {
        add({ question: text, via, answer: { kind: "decline", text: "The match data couldn't be loaded, so I can't check figures right now. Questions about the app still work." } });
      } else {
        setPending(text);
      }
      return;
    }
    add({ question: text, via, answer: answerPlan(plan, ctx), readAs: via === "foundry" ? describePlan(plan, LOOKUP) : undefined });
  }, [add, ctx, loadFailed]);

  // Open (again) whenever the host forwards a request, and ask its question if it carried one.
  useEffect(() => {
    const el = dialog.current;
    if (el && !el.open) el.showModal();
    if (request.question) void submit(request.question);
    else input.current?.focus();
  }, [request.id]);

  // A figure asked for while the log was still loading is answered as soon as it arrives.
  useEffect(() => {
    if ((ctx || loadFailed) && pending) { const text = pending; setPending(null); void submit(text); }
  }, [ctx, loadFailed, pending, submit]);

  // Leaving the page (a link, the palette, Back) closes the panel rather than covering the new page.
  const shownOn = useRef(pathname);
  useEffect(() => {
    if (pathname !== shownOn.current) { shownOn.current = pathname; dialog.current?.close(); }
  }, [pathname]);

  const lastId = entries.at(-1)?.id;
  useEffect(() => {
    const last = log.current?.lastElementChild;
    if (last instanceof HTMLElement) last.scrollIntoView({ block: "nearest" });
  }, [lastId]);

  const close = () => dialog.current?.close();

  return (
    <dialog ref={dialog} className="md-ask" aria-labelledby="md-ask-title" aria-describedby="md-ask-sub">
      <div className="md-ask-head">
        <div>
          <h2 id="md-ask-title"><Icon name="sparkle" size={18} /> Ask MatchDesk</h2>
          <p id="md-ask-sub">About the app, or about this match. Every figure is recalculated from the event log and checked before you see it.</p>
        </div>
        <button type="button" className="md-ask-close" onClick={close} aria-label="Close Ask MatchDesk"><Icon name="close" size={18} /></button>
      </div>
      <div ref={log} className="md-ask-log" role="log" aria-live="polite" aria-relevant="additions" aria-label="Answers">
        {entries.length === 0 && (
          <div className="md-ask-empty">
            <p>Try one of these:</p>
            <ul className="md-ask-suggest">
              {suggestions.map((s) => <li key={s}><button type="button" onClick={() => void submit(s)}>{s}</button></li>)}
            </ul>
          </div>
        )}
        {entries.map((entry) => (
          <article key={entry.id} className="md-ask-turn" aria-label={`Answer to: ${entry.question}`}>
            <p className="md-ask-q"><span className="md-visually-hidden">You asked: </span>{entry.question}</p>
            <Reply entry={entry} onLink={close} />
          </article>
        ))}
        {busy && <p className="md-ask-muted" role="status">Reading your question…</p>}
        {!busy && pending && !ctx && <p className="md-ask-muted" role="status">Loading the event log. Your question will be answered as soon as it arrives.</p>}
      </div>
      <form className="md-ask-form" onSubmit={(e) => { e.preventDefault(); void submit(question); }}>
        <label htmlFor="md-ask-input" className="md-visually-hidden">Your question</label>
        <input
          id="md-ask-input" ref={input} value={question} maxLength={MAX_QUESTION} autoComplete="off"
          onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. Who had more shots in the second half?"
        />
        <button type="submit" className="md-ask-send" disabled={!question.trim() || busy}>Ask</button>
      </form>
      {!ctx && !loadFailed && <p className="md-ask-muted md-ask-loading" role="status">Loading the event log…</p>}
      {loadFailed && <p className="md-ask-muted md-ask-loading" role="status">The match data couldn't be loaded. Questions about the app still work.</p>}
    </dialog>
  );
}
